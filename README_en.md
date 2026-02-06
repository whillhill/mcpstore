

<div align="center">


<img src="assets/logo.svg" alt="McpStore" width="400"/>

---

![GitHub stars](https://img.shields.io/github/stars/whillhill/mcpstore) ![GitHub forks](https://img.shields.io/github/forks/whillhill/mcpstore) ![GitHub license](https://img.shields.io/github/license/whillhill/mcpstore)  ![Python versions](https://img.shields.io/pypi/pyversions/mcpstore) 



[English](README_en.md) | [简体中文](README_zh.md)


[Live Demo](https://web.mcpstore.wiki) | [Documentation](https://doc.mcpstore.wiki/) | [Quick Start](###simple-example)

</div>

### What is mcpstore?

mcpstore is a ready-to-use MCP service orchestration layer for developers: manage services with a unified Store and adapt MCP for use with AI frameworks like `LangChain` and others.

### Simple Example

First, initialize a store

```python
from mcpstore import MCPStore
store = MCPStore.setup_store()
```

Now you have a `store`, and you can simply add or manage your services around this `store`. The `store` will maintain and manage these MCP services.

#### Add Your First Service to the Store

```python
# Add below the code above
store.for_store().add_service({"mcpServers": {"mcpstore_wiki": {"url": "https://www.mcpstore.wiki/mcp"}}})
store.for_store().wait_service("mcpstore_wiki")
```

Easily add services using the add method. The add_service method supports multiple MCP service configuration formats, and mainstream MCP configuration formats can be passed directly. The wait method is optional and synchronously waits for the service to be ready.

#### Adapt MCP to Objects Required by LangChain

```python
tools = store.for_store().for_langchain().list_tools()
print("loaded langchain tools:", len(tools))
```

Simply chain methods to intuitively adapt MCP to a tools list directly usable by LangChain.

##### Framework Adapters

More frameworks will be supported gradually.

| Supported Frameworks | Get Tools |
| --- | --- |
| LangChain | `tools = store.for_store().for_langchain().list_tools()` |
| LangGraph | `tools = store.for_store().for_langgraph().list_tools()` |
| AutoGen | `tools = store.for_store().for_autogen().list_tools()` |
| CrewAI | `tools = store.for_store().for_crewai().list_tools()` |
| LlamaIndex | `tools = store.for_store().for_llamaindex().list_tools()` |

#### Now You Can Use LangChain Normally

```python
# Add the code above
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(
    temperature=0, 
    model="deepseek-chat",
    api_key="sk-*****",
    base_url="https://api.deepseek.com"
)
agent = create_agent(model=llm, tools=tools, system_prompt="You are an assistant, include emoji in your responses")
events = agent.invoke({"messages": [{"role": "user", "content": "How to add services in mcpstore?"}]})
print(events)
```

### Quick Start

```bash
pip install mcpstore
```

#### Agent Grouping

Use `for_agent(agent_id)` to group MCP services

```python
agent_id1 = "agent1"
store.for_agent(agent_id1).add_service({"name": "mcpstore_wiki", "url": "https://www.mcpstore.wiki/mcp"})

agent_id2 = "agent2"
store.for_agent(agent_id2).add_service({"name": "playwright", "command": "npx", "args": ["@playwright/mcp"]})

agent1_tools = store.for_agent(agent_id1).list_tools()
agent2_tools = store.for_agent(agent_id2).list_tools()
```

`store.for_agent(agent_id)` shares most functional interfaces with `store.for_store()`. Essentially, it creates a logical subset within the global scope through a grouping mechanism.

Effectively isolate services by assigning dedicated services to different Agents, avoiding overly long contexts.

Works well with aggregated service `hub_service` (experimental) and quick generation of A2A Agent Cards (planned support).



#### Common Operations

| Action          | Command Example                                                                                   |
|-------------|----------------------------------------------------------------------------------------|
| Find Service        | `store.for_store().find_service("service_name")`                                       |
| Update Service        | `store.for_store().update_service("service_name", new_config)`                         |
| Patch Service        | `store.for_store().patch_service("service_name", {"headers": {"X-API-Key": "..."}})`   |
| Delete Service        | `store.for_store().delete_service("service_name")`                                     |
| Restart Service        | `store.for_store().restart_service("service_name")`                                    |
| Disconnect Service        | `store.for_store().disconnect_service("service_name")`                                 |
| Health Check        | `store.for_store().check_services()`                                                   |
| Show Config        | `store.for_store().show_config()`                                                      |
| Service Info        | `store.for_store().get_service_info("service_name")`                                   |
| Wait for Ready        | `store.for_store().wait_service("service_name", timeout=30)`                           |
| Hub Services        | `store.for_agent(agent_id).hub_services()`                                             |
| List Agents     | `store.for_store().list_agents()` |
| List Services        | `store.for_store().list_services()` |
| List Tools        | `store.for_store().list_tools()` |
| Find Tool        | `store.for_store().find_tool("tool_name")` |
| Execute Tool | `store.for_store().call_tool("tool_name", {"k": "v"})` |

#### Cache/Redis Backend

Supports using Redis as a shared cache backend for sharing service and tool metadata across processes/multiple instances. Install additional dependencies:

```bash
pip install mcpstore[redis]
# Or install separately: pip install redis
```

Usage: Pass in the `external_db` parameter during store initialization:

```python
from mcpstore import MCPStore
store = MCPStore.setup_store(
    external_db={
        "cache": {
            "type": "redis",
            "url": "redis://localhost:6379/0",
            "password": None,
            "namespace": "demo_namespace"
        }
    }
)
```
For more `setup_store` configurations, see the documentation.

### API Mode

#### Start API

Quick start via SDK
```python
from mcpstore import MCPStore
prod_store = MCPStore.setup_store()
prod_store.start_api_server(host="0.0.0.0", port=18200)
```

Or quick start using CLI
```bash
mcpstore run api
```
![image-20250721212359929](http://www.text2mcp.com/img/image-20250721212359929.png)

Example page: [Live Demo](https://web.mcpstore.wiki) 


#### Common API Endpoints

```bash
# Service Management
POST /for_store/add_service
GET  /for_store/list_services
POST /for_store/delete_service

# Tool Operations
GET  /for_store/list_tools
POST /for_store/use_tool

# Runtime Status
GET  /for_store/get_stats
GET  /for_store/health
```
For more, see API documentation: [Documentation](https://doc.mcpstore.wiki/)

### Web Interface

mcpstore provides a Vue.js-based visual management interface that allows you to conveniently manage MCP services, view tool lists, execute tool calls, and more through a browser.

#### Start with Docker (Recommended)

The easiest way is to use Docker Compose to start the complete service stack (including API backend and Web frontend):

```bash
# Start all services (API + Web + Docs + Wiki)
cd docker
./start-all.sh

# Or start Web and API services separately
cd docker/web && docker-compose up -d
cd docker/api && docker-compose up -d
```

After startup, access:
- **Web Interface**: http://localhost:5177
- **API Service**: http://localhost:18200

#### Local Development Mode

If you need to run the Web interface in a local development environment:

**1. Start API Backend**

```bash
# Method 1: Using CLI
mcpstore run api

# Method 2: Using Python
python -c "from mcpstore import MCPStore; store = MCPStore.setup_store(); store.start_api_server(host='0.0.0.0', port=18200)"
```

**2. Start Web Frontend**

```bash
cd vue

# Install dependencies (first time only)
npm install

# Start development server
npm run dev

# Or specify host mode
npm run dev:local    # Local access only
npm run dev:domain   # Allow LAN access
```

The Web interface will start at http://localhost:5177 and automatically connect to the local API service (http://localhost:18200).

#### Production Deployment

```bash
cd vue

# Build production version
npm run build

# Preview production build
npm run preview
```

Build artifacts are located in the `vue/dist` directory and can be deployed to any static file server (Nginx, Apache, etc.).

#### Live Demo

If you don't want to deploy locally, you can directly access the online demo: [https://web.mcpstore.wiki](https://web.mcpstore.wiki)


### Docker Deployment 



## Star History

<div align="center">

[![Star History Chart](https://api.star-history.com/svg?repos=whillhill/mcpstore&type=Date)](https://star-history.com/#whillhill/mcpstore&Date)

</div>

---

McpStore is still under active development. Feedback and suggestions are welcome.
