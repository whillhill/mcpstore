

<div align="center">


```text
███    ███  ██████  ███████  ██████  ████████  ██████  ██████  ███████
████  ████ ██      ██    ██ ██          ██    ██    ██ ██   ██ ██
██ ████ ██ ██      ███████   ██████     ██    ██    ██ ██████  █████
██  ██  ██ ██      ██             ██    ██    ██    ██ ██  ██  ██
██      ██  ██████ ██        ██████     ██     ██████  ██   ██ ███████
```


---

![GitHub stars](https://img.shields.io/github/stars/whillhill/mcpstore) ![GitHub forks](https://img.shields.io/github/forks/whillhill/mcpstore) ![GitHub license](https://img.shields.io/github/license/whillhill/mcpstore)  ![Python versions](https://img.shields.io/pypi/pyversions/mcpstore)



[English](README_en.md) | [简体中文](README_zh.md)


[在线体验](https://web.mcpstore.wiki) | [详细文档](https://doc.mcpstore.wiki/) | [快速使用](###简单示例)

</div>

### mcpstore 是什么？

开发者最佳的mcp管理包 快速维护mcp服务并应用

### 快速开始

```bash
pip install mcpstore
```

### 简单示例

一切的开始：初始化一个store 

```python
from mcpstore import MCPStore
store = MCPStore.setup_store()
```

现在你获得了一个 `store`，利用`store`去使用你的MCP服务，`store` 会维护和管理这些 MCP 服务。

#### 给store添加第一个服务

```python
#在上面的代码下面加入
store.for_store().add_service({"mcpServers": {"mcpstore_wiki": {"url": "https://www.mcpstore.wiki/mcp"}}})
store.for_store().wait_service("mcpstore_wiki")
```

`add_service`方法支持多种mcp服务配置格式，。`wait_service`用来等待服务就绪。

#### 将mcp适配转为langchain需要的对象

```python
#在上面的代码下面加入
tools = store.for_store().for_langchain().list_tools()
print("loaded langchain tools:", len(tools))
```

轻松将mcp服务转为langchain可以直接使用的tools列表

##### 框架适配

积极支持更多的框架

| 已支持框架 | 获取工具 |
| --- | --- |
| LangChain | `tools = store.for_store().for_langchain().list_tools()` |
| LangGraph | `tools = store.for_store().for_langgraph().list_tools()` |
| AutoGen | `tools = store.for_store().for_autogen().list_tools()` |
| CrewAI | `tools = store.for_store().for_crewai().list_tools()` |
| LlamaIndex | `tools = store.for_store().for_llamaindex().list_tools()` |

#### 代码中使用 以langchain为例

```python
#添加上面的代码
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(
    temperature=0, 
    model="your-model",
    api_key="sk-*****",
    base_url="https://api.xxx.com"
)
agent = create_agent(model=llm, tools=tools, system_prompt="你是一个助手，回答的时候带上表情")
events = agent.invoke({"messages": [{"role": "user", "content": "mcpstore怎么添加服务？"}]})
print(events)
```
如你所见。这里的langchain的agent可以正常的调用你通过`sotre`管理的mcp服务了。




#### 为 Agent 分组

使用 `for_agent(agent_id)`  实现分组

```python
#不同的agent需要不同的mcp的集合

agent_id1 = "agent1"
store.for_agent(agent_id1).add_service({"name": "mcpstore_wiki", "url": "https://www.mcpstore.wiki/mcp"})

agent_id2 = "agent2"
store.for_agent(agent_id2).add_service({"name": "gitodo", "command": "uvx", "args": ["gitodo"]})

agent1_tools = store.for_agent(agent_id1).list_tools()

agent2_tools = store.for_agent(agent_id2).list_tools()
```

`store.for_agent(agent_id)` 与 `store.for_store()` 镜像大部分函数接口， `agent` 的分组是 `store` 的逻辑子集。

通过为不同 `agent` 隔离mcp服务，避免上下文过长,并由 `sotre` 统一维护。

#### 聚合服务

`hub_service` 是把当前对象（Store / Agent / Service）再暴露成一个 MCP 服务的桥接器，便于把管理面包装成新的 MCP 端点给外部使用。支持 HTTP / SSE / stdio ：

```python
store = MCPStore.setup_store()

# 将全局 Store 暴露为 HTTP MCP
hub = store.for_store().hub_http(port=8000, host="0.0.0.0", path="/mcp", block=False)

# 仅暴露某个 Agent 视角的工具 
agent_hub = store.for_agent("agent1").hub_sse(port=8100, host="0.0.0.0", path="/sse", block=False)

# 将单个服务暴露为 stdio MCP (因为支持关闭单个服务内的某个工具)
service_hub = store.for_agent("agent1").find_service("demo").hub_stdio(block=False)
```

- 选择 `hub_http` / `hub_sse` / `hub_stdio` 即可对应三种传输；`block=False` 时后台线程运行。
- 会自动按对象类型生成服务名（Store / Agent / Service），无需手写 tool 注册,可以实现studio与http的转换。




#### 常用接口

| 动作          | 命令示例                                                                                   |
|-------------|----------------------------------------------------------------------------------------|
| 定位服务        | `store.for_store().find_service("service_name")`                                       |
| 更新服务        | `store.for_store().update_service("service_name", new_config)`                         |
| 增量更新        | `store.for_store().patch_service("service_name", {"headers": {"X-API-Key": "..."}})`   |
| 删除服务        | `store.for_store().delete_service("service_name")`                                     |
| 重启服务        | `store.for_store().restart_service("service_name")`                                    |
| 断开服务        | `store.for_store().disconnect_service("service_name")`                                 |
| 健康检查        | `store.for_store().check_services()`                                                   |
| 查看配置        | `store.for_store().show_config()`                                                      |
| 服务详情        | `store.for_store().service_info("service_name")`                                   |
| 等待就绪        | `store.for_store().wait_service("service_name", timeout=30)`                           |
| 聚合服务        | `store.for_agent(agent_id).hub_services()`                                             |
| 列出agent     | `store.for_store().list_agents()` |
| 列出服务        | `store.for_store().list_services()` |
| 列出工具        | `store.for_store().list_tools()` |
| 定位工具        | `store.for_store().find_tool("tool_name")` |
| 执行工具 | `store.for_store().call_tool("tool_name", {"k": "v"})` |

#### 数据源热拔插和共享

支持使用 KV 数据库作为共享缓存后端(如redis)，用于跨进程/多实例共享服务与工具 

```bash
pip install mcpstore[redis]
#或直接 单独 pip install redis
#或者其他 pyvk 支持的数据库
```

##### 快速使用

```python
from mcpstore import MCPStore
from mcpstore.config import RedisConfig
redis_config = RedisConfig(
    host="127.0.0.1",
    port=6379,
    password=None,
    namespace="demo_namespace"  # 隔离前缀，防冲突
)
store = MCPStore.setup_store(cache=redis_config)

```
在 `cache` 定义好数据库配置的情况下，所有的数据将由数据保存，也就意味着不同实例的 `store` 只要可以访问到该数据库，就可以共享mcp服务数据以及协同.

也就意味着，你可以通过分布式的方式管理你的mcp服务，在资源受限的环境下可以共享使用由 `store` 维护好的mcp服务。

你可以在资源充足的环境启动 `RedisConfig` 配置过的 `store`。

然后在若干个资源首先的环境下，可以通过 `only_db` 的方式，放弃管理和维护mcp服务，所有的对mcp服务的操作会以事件的形式通知被共享的环境去维护 `store` 和进程。

```python
from mcpstore import MCPStore
from mcpstore.config import RedisConfig

redis_config = RedisConfig(
  host="127.0.0.1",
  port=6379,
  password=None,
  namespace="demo_namespace" #使用相同的命名空间来隔离同一个数据库里的不同键  
)
store = MCPStore.setup_store(cache=redis_config, only_db=True) #这里配置only_db 
store.for_store().list_services()
```
更多细节参考 `setup_store` 配置见文档

### API 模式

新的版本移除了 `api` 模式直接启动，带来的效果是显著的，`mcpstore`不再强依赖`fastapi`包，也可以自己灵活的定制路由和复杂的网络情况
旧版本的`api`被独立出来做成了示例的mini项目，可以快速启动。


### docker部署 

提供了一些 `docker` 的配置方便大家尝试，本项目的初衷是做一个更方便好用的 `mcp` 管理的包，并不偏向于完成一个项目的构建，所以项目设计的可能不太完善和成熟，欢迎大家提出意见谢谢


## Star History

<div align="center">

[![Star History Chart](https://api.star-history.com/svg?repos=whillhill/mcpstore&type=Date)](https://star-history.com/#whillhill/mcpstore&Date)

</div>

---

McpStore 仍在高频更新中，欢迎反馈与建议。
