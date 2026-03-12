#!/usr/bin/env python3
"""
MCPStore CLI - Command Line Interface for MCPStore
"""
import sys

import typer

from .config.commands import register_config_commands
from .mcp.commands import register_mcp_commands

# 全局注册标记，避免重复注册命令
_commands_registered = False

# Create main CLI application
app = typer.Typer(
    name="mcpstore",
    help="MCPStore - 统一管理/启动/配置 MCP 服务的命令行工具。",
    no_args_is_help=True,
    rich_markup_mode="rich"
)

@app.callback()
def callback():
    """
    MCPStore 命令行入口
    """
    pass

@app.command("version")
def version():
    """显示版本信息"""
    try:
        from mcpstore import __version__
    except Exception as e:
        typer.echo(f" Failed to get version: {e}")
        raise typer.Exit(1)

    banner = r"""
    █▀▄▀█  ▄▀▀▄  █▀▀▄  ▄▀▀▀  ▀█▀  ▄▀▀▄  █▀▀▄  █▀▀
    █ █ █  █     █▄▄▀  ▀▀▀▄   █   █  █  █▄▄▀  █▀▀
    ▀   ▀  ▀▀▀▀  █     ▀▀▀    ▀    ▀▀   ▀  ▀  ▀▀▀
    """
    typer.echo(banner)
    typer.echo(f"MCPStore version: {__version__}")

def _register_commands():
    """拆分后的命令注册"""
    global _commands_registered
    if _commands_registered:
        return
    register_config_commands(app)
    register_mcp_commands(app)
    _commands_registered = True


def main():
    """CLI entry point"""
    try:
        _register_commands()
        app()
    except KeyboardInterrupt:
        typer.echo("\n[INFO] Exited")
        sys.exit(0)
    except Exception as e:
        typer.echo(f" CLI exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
