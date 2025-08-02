[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/whillhill-mcpstore-badge.png)](https://mseep.ai/app/whillhill-mcpstore)

[中文](https://github.com/whillhill/mcpstore/blob/main/README_zh.md) | English

# 🚀 McpStore - Comprehensive MCP Management Package

`McpStore` is a tool management library specifically designed to solve the problem of Agents wanting to use `MCP (Model Context Protocol)` capabilities while being overwhelmed by MCP management.

MCP is developing rapidly, and we all want to add MCP capabilities to existing Agents, but introducing new tools to Agents typically requires writing a lot of repetitive "glue code", making the process cumbersome.

## Online Experience

This project has a simple Vue frontend that allows you to intuitively manage your MCP through SDK or API methods.

![image-20250721212359929](http://www.text2mcp.com/img/image-20250721212359929.png)

You can quickly start API mode with `mcpstore run api`, or you can use a simple piece of code:

```python
from mcpstore import MCPStore
prod_store = MCPStore.setup_store()
prod_store.start_api_server(
    host='0.0.0.0',
    port=18200
)
```

After quickly starting the backend, clone the project and run `npm run dev` to run the Vue frontend.

You can also quickly experience it through http://mcpstore.wiki/web_demo/dashboard



## Implement MCP Tools Ready-to-Use in Three Lines of Code ⚡

No need to worry about `mcp` protocol and configuration details, just use intuitive classes and functions with an `extremely simple` user experience.

```python
store = MCPStore.setup_store()

store.for_store().add_service({"name":"mcpstore-wiki","url":"http://mcpstore.wiki/mcp"})

tools = store.for_store().list_tools()

# store.for_store().use_tool(tools[0].name,{"query":'hi!'})
```



## A Complete Runnable Example - Direct Integration of MCP Services with LangChain 🔥

Below is a complete, directly runnable example showing how to seamlessly integrate tools obtained from `McpStore` into a standard `langChain Agent`.

```python
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from mcpstore import MCPStore
store = MCPStore.setup_store()
store.for_store().add_service({"name":"mcpstore-wiki","url":"http://mcpstore.wiki/mcp"})
tools = store.for_store().to_langchain_tools()
llm = ChatOpenAI(
    temperature=0, model="deepseek-chat",
    openai_api_key="sk-****",
    openai_api_base="https://api.deepseek.com"
)
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an assistant, answer with emojis"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
query = "How's the weather in Beijing?"
print(f"\n   🤔: {query}")
response = agent_executor.invoke({"input": query})
print(f"   🤖 : {response['output']}")
```

![image-20250721212658085](http://www.text2mcp.com/img/image-20250721212658085.png)



Or if you don't want to use `langchain` and plan to `design your own tool calls` 🛠️

```
from mcpstore import MCPStore
store = MCPStore.setup_store()
store.for_store().add_service({"name":"mcpstore-wiki","url":"http://mcpstore.wiki/mcp"})
tools = store.for_store().list_tools()
print(store.for_store().use_tool(tools[0].name,{"query":'Beijing'}))
```



## Quick Start

### Installation
```bash
pip install mcpstore
```


## Chaining Calls ⛓️

I really dislike complex and overly long function names. For intuitive code display, `McpStore` uses `chaining`. Specifically, `store` is a foundation. If you have different `agents` and want your different `agents` to be experts in different domains (using isolated different `MCPs`), you can try `for_agent`. Each `agent` is isolated, and you can determine your `agent`'s identity through a custom `agentid`, ensuring it performs better within its scope.

* `store.for_store()`: Enter `global context`, where managed services and tools are visible to all Agents.
* `store.for_agent("agent_id")`: Create an `isolated private context` for an Agent with the specified ID. Each


## Multi-Agent Isolation 🏠

The following code demonstrates how to use `context isolation` to assign `dedicated tool sets` to Agents with different functions.

```python
# Initialize Store
store = MCPStore.setup_store()

# Assign dedicated Wiki tools to "Knowledge Management Agent"
# This operation is performed in the "knowledge" agent's private context
agent_id1 = "my-knowledge-agent"
knowledge_agent_context = store.for_agent(agent_id1).add_service(
    {"name": "mcpstore-wiki", "url": "http://mcpstore.wiki/mcp"}
)

# Assign dedicated development tools to "Development Support Agent"
# This operation is performed in the "development" agent's private context
agent_id2 = "my-development-agent"
dev_agent_context = store.for_agent(agent_id2).add_service(
    {"name": "mcpstore-demo", "url": "http://mcpstore.wiki/mcp"}
)

# Each Agent's tool set is completely isolated without affecting each other
knowledge_tools = store.for_agent(agent_id1).list_tools()
dev_tools = store.for_agent(agent_id2).list_tools()
```
Intuitively, you can use almost all functions through `store.for_store()` and `store.for_agent("agent_id")` ✨


## McpStore's setup_store() 🔧


### 📋 Overview

`MCPStore.setup_store()` is MCPStore's `core initialization method`, used to create and configure MCPStore instances. This method supports `custom configuration file paths` and `debug mode`, providing `flexible configuration options` for different environments and use cases.

### 🔧 Method Signature

```python
@staticmethod
def setup_store(mcp_config_file: str = None, debug: bool = False) -> MCPStore
```

**Parameter Description**:
- `mcp_config_file`: Custom mcp.json configuration file path (optional)
- `debug`: Whether to enable debug logging mode (optional, default False)
- **Return Value**: Fully initialized MCPStore instance

### 📋 Parameter Details

#### 1. `mcp_config_file` Parameter

- **When not specified**: Uses default path `src/mcpstore/data/mcp.json`
- **When specified**: Uses the specified `mcp.json` configuration file to instantiate your store, supports `mainstream client file formats`, `ready to use` 🎯
- Note that the store actually revolves around an mcp.json file. When you specify an mcp.json file, it becomes the foundation of this store. You can achieve store import and export effects by simply moving these json files. Similarly, if your Python code calls and API calls point to the same mcp.json, it means you can modify the same store's impact in Python code through the API without modifying the code.

#### 2. `debug` Parameter

##### Basic Description
- **Type**: `bool`
- **Default Value**: `False`
- **Function**: Controls log output level and detail

##### Log Configuration Comparison

| Mode | debug=False (default) | debug=True |
|------|-------------------|------------|
| **Log Level** | ERROR | DEBUG |
| **Log Format** | `%(levelname)s - %(message)s` | `%(asctime)s - %(name)s - %(levelname)s - %(message)s` |
| **Display Content** | Only error messages | All debug information |


### 📁 Supported JSON Configuration Formats

#### Standard MCP Configuration Format

MCPStore uses `standard MCP configuration format`, supporting both `URL-based` and `command-based` service configurations:

```json
{
  "mcpServers": {
    "mcpstore-wiki": {
      "url": "http://mcpstore.wiki/mcp"
    },
    "howtocook": {
      "command": "npx",
      "args": [
        "-y",
        "howtocook-mcp"
      ]
    }
  }
}
```


#### Scenario: Multi-tenant Configuration 🏢

```python
# Tenant A configuration
tenant_a_store = MCPStore.setup_store(
    mcp_config_file="tenant_a_mcp.json",
    debug=False
)

# Tenant B configuration
tenant_b_store = MCPStore.setup_store(
    mcp_config_file="tenant_b_mcp.json",
    debug=False
)

# Provide isolated services for different tenants
tenant_a_tools = tenant_a_store.for_store().list_tools()
tenant_b_tools = tenant_b_store.for_store().list_tools()
```


## Powerful Service Registration `add_service` 💪

The core of `mcpstore` is `store`. Simply initialize a `store` through `setup_store()`, and you can register `any number` of services supporting all `MCP protocols` on this `store`. No need to worry about the `lifecycle and maintenance` of individual mcp services, no need to worry about `CRUD operations` for mcp services - `store` will `take full responsibility` for the lifecycle maintenance of these services.

When you need to integrate these services into langchain Agent, calling `store.for_store().to_langchain_tools()` provides `one-click conversion` to a tool set fully compatible with langchain `Tool` structure, convenient for direct use or `seamless integration` with existing tools.

Or you can directly use the `store.for_store().use_tool()` method to `customize your desired tool calls` 🎯.

### Service Registration Methods

All services added through `add_service` have their configurations `uniformly managed` and can optionally be persisted to the `mcp.json` file registered during setup_store. `Deduplication and updates` are `automatically handled` by mcpstore ⚙️.


### Basic Syntax
```python
store = MCPStore.setup_store()
store.for_store().add_service(config)
```

### Supported Registration Methods

#### 1. 🔄 Full Registration (No Parameters)
Register all services in the `mcp.json` configuration file.

```python
store.for_store().add_service()
```
Without passing any parameters, `add_service` will `automatically find and load` the `mcp.json` file in the project root directory, which is `compatible with mainstream formats`.

**Use Cases**:
- `One-time registration` of all pre-configured services during project initialization
- `Reload` all service configurations

---

#### 2. 🌐 URL-based Registration
Add remote MCP services through URL.

```python
store.for_store().add_service({
    "name": "mcpstore-wiki",
    "url": "http://mcpstore.wiki/mcp",
    "transport": "streamable-http"
})
```

**Fields**:
- `name`: Service name
- `url`: Service URL
- `transport`: Optional field, can `automatically infer` transport protocol (`streamable-http`, `sse`)

---

#### 3. 💻 Local Command Registration
Start local MCP service processes.

```python
# Python service
store.for_store().add_service({
    "name": "local_assistant",
    "command": "python",
    "args": ["./assistant_server.py"],
    "env": {"DEBUG": "true", "API_KEY": "your_key"},
    "working_dir": "/path/to/service"
})

# Node.js service
store.for_store().add_service({
    "name": "node_service",
    "command": "node",
    "args": ["server.js", "--port", "8080"],
    "env": {"NODE_ENV": "production"}
})

# Executable file
store.for_store().add_service({
    "name": "binary_service",
    "command": "./mcp_server",
    "args": ["--config", "config.json"]
})
```

**Required Fields**:
- `name`: Service name
- `command`: Execution command

**Optional Fields**:
- `args`: Command parameter list
- `env`: Environment variable dictionary
- `working_dir`: Working directory

---

#### 4. 📄 MCPConfig Dictionary Registration
Use standard MCP configuration format.

```python
store.for_store().add_service({
  "mcpServers": {
    "mcpstore-wiki": {
      "url": "http://mcpstore.wiki/mcp"
    },
    "howtocook": {
      "command": "npx",
      "args": [
        "-y",
        "howtocook-mcp"
      ]
    }
  }
})
```

---

#### 5. 📝 Service Name List Registration
Register specific services from existing configuration.

```python
# Register specified services
store.for_store().add_service(['mcpstore-wiki', 'howtocook'])

# Register single service
store.for_store().add_service(['howtocook'])
```

**Prerequisites**: Services must be defined in the `mcp.json` configuration file 📋.

---

#### 6. 📁 JSON File Registration
Read configuration from external JSON files.

```python
# Read configuration from file
store.for_store().add_service(json_file="./demo_config.json")

# Specify both config and json_file (json_file takes priority)
store.for_store().add_service(
    config={"name": "backup"},
    json_file="./demo_config.json"  # This will be used ⚡
)
```

**JSON File Format Examples**:
```json
{
  "mcpServers": {
    "mcpstore-wiki": {
      "url": "http://mcpstore.wiki/mcp"
    },
    "howtocook": {
      "command": "npx",
      "args": [
        "-y",
        "howtocook-mcp"
      ]
    }
  }
}
```
And other formats supported by `add_service` 📝

``` json
{
    "name": "mcpstore-wiki",
    "url": "http://mcpstore.wiki/mcp"
}
```

---


## RESTful API 🌐

In addition to being used as a `Python library`, MCPStore also provides a `complete RESTful API suite`, allowing you to seamlessly integrate `MCP tool management capabilities` into any backend service or management platform.

`One command` to start a complete Web service:
```bash
pip install mcpstore
mcpstore run api
```
Get `38` API endpoints immediately after startup 🚀

### 📡 Complete API Ecosystem

#### Store Level API 🏪

```bash
# Service Management
POST /for_store/add_service          # Add service
GET  /for_store/list_services        # Get service list
POST /for_store/delete_service       # Delete service
POST /for_store/update_service       # Update service
POST /for_store/restart_service      # Restart service

# Tool Operations
GET  /for_store/list_tools           # Get tool list
POST /for_store/use_tool             # Execute tool

# Batch Operations
POST /for_store/batch_add_services   # Batch add
POST /for_store/batch_update_services # Batch update

# Monitoring & Statistics
GET  /for_store/get_stats            # System statistics
GET  /for_store/health               # Health check
```

#### Agent Level API 🤖

```bash
# Fully corresponds to Store level, supports multi-tenant isolation
POST /for_agent/{agent_id}/add_service
GET  /for_agent/{agent_id}/list_services
# ... All Store level features are supported
```

#### Monitoring System API (3 endpoints) 📊

```bash
GET  /monitoring/status              # Get monitoring status
POST /monitoring/config              # Update monitoring configuration
POST /monitoring/restart             # Restart monitoring tasks
```

#### General API 🔧

```bash
GET  /services/{name}                # Cross-context service query
```




## Developer Documentation & Resources 📚

### Detailed API Interface Documentation
We provide `comprehensive RESTful API documentation` aimed at helping developers `quickly integrate and debug`. The documentation provides `comprehensive information` for each API endpoint, including:
* **Function Description**: Interface purpose and business logic.
* **URL & HTTP Methods**: Standard request paths and methods.
* **Request Parameters**: Detailed input parameter descriptions, types, and validation rules.
* **Response Examples**: Clear success and failure response structure examples.
* **Curl Call Examples**: Command-line call examples that can be directly copied and run.
* **Source Code Tracing**: Links to backend source code files, classes, and key functions that implement the interface, achieving `API-to-code transparency`, greatly facilitating `in-depth debugging and problem localization` 🔍.

### Source Code Level Development Documentation (LLM-Friendly) 🤖
To support `deep customization and secondary development`, we also provide a `unique source code level reference documentation`. This documentation not only `systematically organizes` all core classes, properties, and methods in the project, but more importantly, we additionally provide an `LLM-optimized` `llm.txt` version.
Developers can directly provide this `plain text format` documentation to AI models, allowing AI to assist with `code understanding`, `feature extension`, or `refactoring`, thus achieving true `AI-Driven Development` ✨.

## Contributing 🤝

MCPStore is an `open source project`, and we welcome `any form of contribution` from the community:

* ⭐ If the project helps you, please give us a Star on `GitHub`.
* 🐛 Submit bug reports or feature suggestions through `Issues`.
* 🔧 Contribute your code through `Pull Requests`.
* 💬 Join the community and share your `usage experiences` and `best practices`.

---

**MCPStore: Making MCP tool management `simple and powerful` 💪.**

![image-20250722000133533](http://www.text2mcp.com/img/image-20250722000133533.png)