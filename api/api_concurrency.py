"""
MCPStore API Concurrency Control
并发访问控制模块，用于防止文件操作的竞争条件
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, AsyncContextManager

# 平台检测
IS_WINDOWS = sys.platform == "win32"

# Windows 上使用 msvcrt，Unix 上使用 fcntl
if IS_WINDOWS:
    import msvcrt
else:
    import fcntl

logger = logging.getLogger(__name__)


class FileLockManager:
    """文件锁管理器，用于防止并发文件访问冲突"""
    
    def __init__(self, lock_dir: str = "/tmp/mcpstore_locks"):
        self.lock_dir = Path(lock_dir)
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self.active_locks: Dict[str, asyncio.Lock] = {}
        
    def _get_lock_path(self, file_path: str) -> str:
        """获取锁文件路径"""
        # 使用文件路径的哈希作为锁文件名
        import hashlib
        file_hash = hashlib.md5(file_path.encode()).hexdigest()
        return str(self.lock_dir / f"{file_hash}.lock")
    
    @asynccontextmanager
    async def acquire_lock(self, file_path: str, timeout: float = 30.0) -> AsyncContextManager[None]:
        """
        获取文件锁
        
        Args:
            file_path: 要锁定的文件路径
            timeout: 获取锁的超时时间
            
        Yields:
            None
            
        Raises:
            asyncio.TimeoutError: 如果在超时时间内无法获取锁
        """
        lock_path = self._get_lock_path(file_path)
        
        # 为每个文件路径创建一个专用的锁
        if lock_path not in self.active_locks:
            self.active_locks[lock_path] = asyncio.Lock()
        
        file_lock = self.active_locks[lock_path]
        
        try:
            # 尝试获取异步锁
            await asyncio.wait_for(file_lock.acquire(), timeout=timeout)
            
            # 获取系统级文件锁（防止跨进程冲突）
            try:
                with open(lock_path, 'w') as lock_file:
                    if IS_WINDOWS:
                        # Windows 使用锁定文件
                        try:
                            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                        except (IOError, OSError):
                            file_lock.release()
                            raise asyncio.TimeoutError(f"Could not acquire system lock for {file_path}")
                    else:
                        # Unix 使用 flock
                        try:
                            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        except (IOError, BlockingIOError):
                            file_lock.release()
                            raise asyncio.TimeoutError(f"Could not acquire system lock for {file_path}")
                    
                    lock_file.write(f"{datetime.now().isoformat()}\n{os.getpid()}\n")
                    lock_file.flush()
            except (IOError, BlockingIOError, OSError):
                file_lock.release()
                raise asyncio.TimeoutError(f"Could not acquire system lock for {file_path}")
            
            logger.debug(f"Acquired lock for {file_path}")
            yield
            
        finally:
            # 释放系统级文件锁
            try:
                with open(lock_path, 'r') as lock_file:
                    if IS_WINDOWS:
                        # Windows 上文件会在关闭时自动解锁
                        pass
                    else:
                        # Unix 上需要显式解锁
                        fcntl.flock(lock_file, fcntl.LOCK_UN)
            except FileNotFoundError:
                pass
            
            # 删除锁文件
            try:
                os.remove(lock_path)
            except FileNotFoundError:
                pass
            
            # 释放异步锁
            file_lock.release()
            logger.debug(f"Released lock for {file_path}")
    
    def cleanup_stale_locks(self, max_age: timedelta = timedelta(minutes=30)):
        """清理过期的锁文件"""
        now = datetime.now()
        for lock_file in self.lock_dir.glob("*.lock"):
            try:
                stat = lock_file.stat()
                if now - datetime.fromtimestamp(stat.st_mtime) > max_age:
                    lock_file.unlink()
                    logger.debug(f"Cleaned up stale lock: {lock_file}")
            except Exception as e:
                logger.warning(f"Failed to clean up lock {lock_file}: {e}")


class OperationThrottler:
    """操作节流器，用于限制高频操作"""
    
    def __init__(self, max_operations: int = 10, time_window: float = 60.0):
        self.max_operations = max_operations
        self.time_window = time_window
        self.operation_records: Dict[str, list] = {}
        
    async def check_rate_limit(self, operation_type: str, identifier: str) -> bool:
        """
        检查是否超过速率限制
        
        Args:
            operation_type: 操作类型（如 "file_reset", "config_update"）
            identifier: 操作标识符（如文件路径、服务名等）
            
        Returns:
            bool: True 表示允许操作，False 表示超过限制
        """
        key = f"{operation_type}:{identifier}"
        now = datetime.now().timestamp()
        
        if key not in self.operation_records:
            self.operation_records[key] = []
        
        # 清理过期的记录
        window_start = now - self.time_window
        self.operation_records[key] = [
            timestamp for timestamp in self.operation_records[key]
            if timestamp > window_start
        ]
        
        # 检查是否超过限制
        if len(self.operation_records[key]) >= self.max_operations:
            logger.warning(f"Rate limit exceeded for {key}")
            return False
        
        # 记录本次操作
        self.operation_records[key].append(now)
        return True
    
    def get_remaining_operations(self, operation_type: str, identifier: str) -> int:
        """获取剩余操作次数"""
        key = f"{operation_type}:{identifier}"
        if key not in self.operation_records:
            return self.max_operations
        
        now = datetime.now().timestamp()
        window_start = now - self.time_window
        active_operations = [
            timestamp for timestamp in self.operation_records[key]
            if timestamp > window_start
        ]
        
        return max(0, self.max_operations - len(active_operations))


# 全局实例
file_lock_manager = FileLockManager()
operation_throttler = OperationThrottler()


@asynccontextmanager
async def safe_file_operation(
    file_path: str,
    operation_type: str = "file_operation",
    enable_rate_limit: bool = True,
    rate_limit_max: int = 5,
    rate_limit_window: float = 60.0
) -> AsyncContextManager[None]:
    """
    安全的文件操作上下文管理器
    
    Args:
        file_path: 要操作的文件路径
        operation_type: 操作类型，用于速率限制
        enable_rate_limit: 是否启用速率限制
        rate_limit_max: 最大操作次数
        rate_limit_window: 时间窗口（秒）
        
    Yields:
        None
        
    Raises:
        asyncio.TimeoutError: 如果无法获取锁
        RuntimeError: 如果超过速率限制
    """
    # 检查速率限制
    if enable_rate_limit:
        throttler = OperationThrottler(rate_limit_max, rate_limit_window)
        if not await throttler.check_rate_limit(operation_type, file_path):
            remaining = throttler.get_remaining_operations(operation_type, file_path)
            raise RuntimeError(
                f"Rate limit exceeded for {operation_type} on {file_path}. "
                f"Remaining operations: {remaining}"
            )
    
    # 获取文件锁
    async with file_lock_manager.acquire_lock(file_path):
        yield


# 定期清理过期锁的任务
async def cleanup_task():
    """后台清理任务"""
    while True:
        try:
            file_lock_manager.cleanup_stale_locks()
            await asyncio.sleep(300)  # 每5分钟清理一次
        except Exception as e:
            logger.error(f"Lock cleanup task failed: {e}")
            await asyncio.sleep(60)  # 错误时等待1分钟再试


def start_cleanup_task():
    """启动清理任务"""
    loop = asyncio.get_event_loop()
    loop.create_task(cleanup_task())