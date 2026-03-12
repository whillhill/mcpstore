

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


[Online Demo](https://web.mcpstore.wiki) | [Detailed Documentation](https://doc.mcpstore.wiki/) | [Quick Start](###quick-start)

</div>

### What is mcpstore?

The best MCP management package for developers. Quickly maintain MCP services and apply them.

### Quick Start

```bash
pip install mcpstore
```

### Quick Start

The beginning of everything: Initialize a store

```python
from mcpstore import MCPStore
store = MCPStore.setup_store()
```

Now you have a `store`. Use the `store` to manage your MCP services. The `store` will maintain and manage these MCP services.

#### Add the First Service to the Store

```python
# Add below the code above
store.for_store().add_service({"mcpServers": {"mcpstore_wiki": {"url": "https://www.mcpstore.wiki/mcp"}}})
store.for_store().wait_service("mcpstore_wiki")
```

The `add_service` method supports multiple MCP service configuration formats. `wait_service` is used to wait for the service to be ready.

#### Convert MCP to Objects Needed by LangChain

```python
# Add below the code above
tools = store.for_store().for_langchain().list_tools()
print("loaded langchain tools:", len(tools))
```

Easily convert MCP services into a tools list that LangChain can directly use.

##### Framework Adapters

Actively supporting more frameworks

| Supported Framework | Get Tools |
| --- | --- |
| LangChain | `tools = store.for_store().for_langchain().list_tools()` |
| LangGraph | `tools = store.for_store().for_langgraph().list_tools()` |
| AutoGen | `tools = store.for_store().for_autogen().list_tools()` |
| CrewAI | `tools = store.for_store().for_crewai().list_tools()` |
| LlamaIndex | `tools = store.for_store().for_llamaindex().list_tools()` |

#### Usage in Code (Taking LangChain as an Example)

```python
# Add the code above
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(
    temperature=0,
    model="your-model",
    api_key="sk-*****",
    base_url="https://api.xxx.com"
)
agent = create_agent(model=llm, tools=tools, system_prompt="You are an assistant. Answer with emojis.")
events = agent.invoke({"messages": [{"role": "user", "content": "How to add a service in mcpstore?"}]})
print(events)
```
As you can see, the LangChain agent here can normally call the MCP services managed by your `store`.




#### Group by Agent

Use `for_agent(agent_id)` to implement grouping

```python
# Different agents need different sets of MCPs

agent_id1 = "agent1"
store.for_agent(agent_id1).add_service({"name": "mcpstore_wiki", "url": "https://www.mcpstore.wiki/mcp"})

agent_id2 = "agent2"
store.for_agent(agent_id2).add_service({"name": "gitodo", "command": "uvx", "args": ["gitodo"]})

agent1_tools = store.for_agent(agent_id1).list_tools()

agent2_tools = store.for_agent(agent_id2).list_tools()
```

`store.for_agent(agent_id)` mirrors most function interfaces with `store.for_store()`. The `agent` grouping is a logical subset of the `store`.

By isolating MCP services for different `agent`s, avoiding overly long contexts, and unified maintenance by `store`.

#### Aggregate Services

`hub_service` is a bridge that exposes the current object (Store / Agent / Service) as an MCP service, facilitating the packaging of the management interface into new MCP endpoints for external use. Supports HTTP / SSE / stdio:

```python
store = MCPStore.setup_store()

# Expose global Store as HTTP MCP
hub = store.for_store().hub_http(port=8000, host="0.0.0.0", path="/mcp", block=False)

# Only expose tools from a specific Agent's perspective
agent_hub = store.for_agent("agent1").hub_sse(port=8100, host="0.0.0.0", path="/sse", block=False)

# Expose a single service as stdio MCP (because it supports disabling certain tools within a single service)
service_hub = store.for_agent("agent1").find_service("demo").hub_stdio(block=False)
```

- Choose `hub_http` / `hub_sse` / `hub_stdio` to correspond to the three transport types; when `block=False`, it runs in a background thread.
- Automatically generates service names by object type (Store / Agent / Service), no need to manually write tool registration, enabling conversion between studio and http.




#### Common Interfaces

| Action | Command Example |
|-------------|----------------------------------------------------------------------------------------|
| Locate Service | `store.for_store().find_service("service_name")` |
| Update Service | `store.for_store().update_service("service_name", new_config)` |
| Incremental Update | `store.for_store().patch_service("service_name", {"headers": {"X-API-Key": "..."}})` |
| Delete Service | `store.for_store().delete_service("service_name")` |
| Restart Service | `store.for_store().restart_service("service_name")` |
| Disconnect Service | `store.for_store().disconnect_service("service_name")` |
| Health Check | `store.for_store().check_services()` |
| View Configuration | `store.for_store().show_config()` |
| Service Details | `store.for_store().service_info("service_name")` |
| Wait for Ready | `store.for_store().wait_service("service_name", timeout=30)` |
| Aggregate Services | `store.for_agent(agent_id).hub_services()` |
| List Agents | `store.for_store().list_agents()` |
| List Services | `store.for_store().list_services()` |
| List Tools | `store.for_store().list_tools()` |
| Locate Tool | `store.for_store().find_tool("tool_name")` |
| Execute Tool | `store.for_store().call_tool("tool_name", {"k": "v"})` |

#### Data Source Hot-swapping and Sharing

Supports using KV databases as shared cache backends (e.g., Redis) for cross-process/multi-instance sharing of services and tools.

```bash
pip install mcpstore[redis]
# Or directly install redis separately with pip install redis
# Or other databases supported by pyvk
```

##### Quick Usage

```python
from mcpstore import MCPStore
from mcpstore.config import RedisConfig
redis_config = RedisConfig(
    host="127.0.0.1",
    port=6379,
    password=None,
    namespace="demo_namespace"  # Isolation prefix, to prevent conflicts
)
store = MCPStore.setup_store(cache=redis_config)

```
With the database configuration defined in `cache`, all data will be saved by the database, meaning different instances of `store` can share MCP service data and collaborate as long as they can access this database.

This means you can manage your MCP services in a distributed manner, and in resource-constrained environments, you can share and use MCP services maintained by `store`.

You can start a `store` configured with `RedisConfig` in a resource-rich environment.

Then in several resource-constrained environments, you can use the `only_db` approach to give up managing and maintaining MCP services, and all operations on MCP services will notify the shared environment to maintain `store` and processes in the form of events.

```python
from mcpstore import MCPStore
from mcpstore.config import RedisConfig

redis_config = RedisConfig(
  host="127.0.0.1",
  port=6379,
  password=None,
  namespace="demo_namespace" # Use the same namespace to isolate different keys in the same database
)
store = MCPStore.setup_store(cache=redis_config, only_db=True) # Configure only_db here
store.for_store().list_services()
```
For more details, refer to `setup_store` configuration in the documentation.

### API Mode

The new version has removed direct startup with `api` mode. The effect is significant: `mcpstore` no longer strongly depends on the `fastapi` package, and you can also flexibly customize routing and complex network situations.
The old version's `api` has been separated into an example mini-project, which can be started quickly.


### Docker Deployment

Some `docker` configurations are provided for everyone to try. The original intention of this project is to create a more convenient and useful `mcp` management package, not biased towards completing a project construction, so the project design may not be perfect and mature. Welcome to give your opinions and suggestions. Thank you!


## Star History

<div align="center">

[![Star History Chart](https://api.star-history.com/svg?repos=whillhill/mcpstore&type=Date)](https://star-history.com/#whillhill/mcpstore&Date)

</div>

---

McpStore is still being updated frequently. Welcome feedback and suggestions.
