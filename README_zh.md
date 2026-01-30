

<div align="center">


<img src="assets/logo.svg" alt="McpStore" width="400"/>

---

![GitHub stars](https://img.shields.io/github/stars/whillhill/mcpstore) ![GitHub forks](https://img.shields.io/github/forks/whillhill/mcpstore) ![GitHub license](https://img.shields.io/github/license/whillhill/mcpstore)  ![Python versions](https://img.shields.io/pypi/pyversions/mcpstore)



[English](README_en.md) | [简体中文](README_zh.md)


[在线体验](https://web.mcpstore.wiki) | [详细文档](https://doc.mcpstore.wiki/) | [快速使用](###简单示例)

</div>

### mcpstore 是什么？

mcpstore 是面向开发者的开箱即用的 MCP 服务编排层：用一个 Store 统一管理服务，并将 MCP 适配给 AI 框架`LangChain等`使用。

### 简单示例

首先只需要需要初始化一个store

```python
from mcpstore import MCPStore
store = MCPStore.setup_store()
```

现在就有了一个 `store`，后续只需要围绕这个`store`去添加或者操作你的服务，`store` 会维护和管理这些 MCP 服务。

#### 给store添加第一个服务

```python
#在上面的代码下面加入
store.for_store().add_service({"mcpServers": {"mcpstore_wiki": {"url": "https://www.mcpstore.wiki/mcp"}}})
store.for_store().wait_service("mcpstore_wiki")
```

通过add方法便捷添加服务，add_service方法支持多种mcp服务配置格式，主流的mcp配置格式都可以直接传入。wait方法可选，是否同步等待服务就绪。

#### 将mcp适配转为langchain需要的对象

```python
tools = store.for_store().for_langchain().list_tools()
print("loaded langchain tools:", len(tools))
```

简单链上即可直观的将mcp适配为langchain直接使用的tools列表

##### 框架适配

会逐渐支持更多的框架

| 已支持框架 | 获取工具 |
| --- | --- |
| LangChain | `tools = store.for_store().for_langchain().list_tools()` |
| LangGraph | `tools = store.for_store().for_langgraph().list_tools()` |
| AutoGen | `tools = store.for_store().for_autogen().list_tools()` |
| CrewAI | `tools = store.for_store().for_crewai().list_tools()` |
| LlamaIndex | `tools = store.for_store().for_llamaindex().list_tools()` |

#### 现在就可以正常的使用langchain了

```python
#添加上面的代码
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(
    temperature=0, 
    model="deepseek-chat",
    api_key="sk-*****",
    base_url="https://api.deepseek.com"
)
agent = create_agent(model=llm, tools=tools, system_prompt="你是一个助手，回答的时候带上表情")
events = agent.invoke({"messages": [{"role": "user", "content": "mcpstore怎么添加服务？"}]})
print(events)
```

### 快速开始

```bash
pip install mcpstore
```

#### Agent 分组

使用 `for_agent(agent_id)`  实现对mcp服务进行分组

```python
agent_id1 = "agent1"
store.for_agent(agent_id1).add_service({"name": "mcpstore_wiki", "url": "https://www.mcpstore.wiki/mcp"})

agent_id2 = "agent2"
store.for_agent(agent_id2).add_service({"name": "playwright", "command": "npx", "args": ["@playwright/mcp"]})

agent1_tools = store.for_agent(agent_id1).list_tools()
agent2_tools = store.for_agent(agent_id2).list_tools()
```

`store.for_agent(agent_id)` 与 `store.for_store()` 共享大部分函数接口，本质上是通过分组机制在全局范围内创建了一个逻辑子集。

通过为不同 Agent 分配专属服务实现服务的有效隔离，避免上下文过长。

与聚合服务`hub_service`(实验性)和快速生成 A2A Agent Card (计划支持)配合较好。



#### 常用操作

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
| 服务详情        | `store.for_store().get_service_info("service_name")`                                   |
| 等待就绪        | `store.for_store().wait_service("service_name", timeout=30)`                           |
| 聚合服务        | `store.for_agent(agent_id).hub_services()`                                             |
| 列出Agent     | `store.for_store().list_agents()` |
| 列出服务        | `store.for_store().list_services()` |
| 列出工具        | `store.for_store().list_tools()` |
| 定位工具        | `store.for_store().find_tool("tool_name")` |
| 执行工具 | `store.for_store().call_tool("tool_name", {"k": "v"})` |

#### 缓存/Redis 后端

支持使用 Redis 作为共享缓存后端，用于跨进程/多实例共享服务与工具元数据。安装额外依赖：

```bash
pip install mcpstore[redis]
#或直接 单独 pip install redis
```

使用方式:在store初始化的时候通过 `external_db` 参数传入：

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
更多的`setup_store`配置见文档

### API 模式

#### 启动api

通过SDK快速启动
```python
from mcpstore import MCPStore
prod_store = MCPStore.setup_store()
prod_store.start_api_server(host="0.0.0.0", port=18200)
```

或者使用CLI快速启动
```bash
mcpstore run api
```
![image-20250721212359929](http://www.text2mcp.com/img/image-20250721212359929.png)

示例页面：[在线体验](https://web.mcpstore.wiki) 


#### 常用接口

```bash
# 服务管理
POST /for_store/add_service
GET  /for_store/list_services
POST /for_store/delete_service

# 工具操作
GET  /for_store/list_tools
POST /for_store/use_tool

# 运行状态
GET  /for_store/get_stats
GET  /for_store/health
```
更多见接口文档： [详细文档](https://doc.mcpstore.wiki/)

### Web 界面

mcpstore 提供了基于 Vue.js 的可视化管理界面，可以通过浏览器方便地管理 MCP 服务、查看工具列表、执行工具调用等操作。

#### 使用 Docker 启动（推荐）

最简单的方式是使用 Docker Compose 启动完整的服务栈（包括 API 后端和 Web 前端）：

```bash
# 启动所有服务（API + Web + 文档 + Wiki）
cd docker
./start-all.sh

# 或单独启动 Web 和 API 服务
cd docker/web && docker-compose up -d
cd docker/api && docker-compose up -d
```

启动后访问：
- **Web 界面**: http://localhost:5177
- **API 服务**: http://localhost:18200

#### 本地开发模式

如果需要在本地开发环境运行 Web 界面：

**1. 启动 API 后端**

```bash
# 方式一：使用 CLI
mcpstore run api

# 方式二：使用 Python
python -c "from mcpstore import MCPStore; store = MCPStore.setup_store(); store.start_api_server(host='0.0.0.0', port=18200)"
```

**2. 启动 Web 前端**

```bash
cd vue

# 安装依赖（首次运行）
npm install

# 启动开发服务器
npm run dev

# 或指定主机模式
npm run dev:local    # 仅本机访问
npm run dev:domain   # 允许局域网访问
```

Web 界面将在 http://localhost:5177 启动，自动连接到本地 API 服务（http://localhost:18200）。

#### 生产部署

```bash
cd vue

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

构建产物位于 `vue/dist` 目录，可部署到任何静态文件服务器（Nginx、Apache 等）。

#### 在线体验

如果不想本地部署，可以直接访问在线演示：[https://web.mcpstore.wiki](https://web.mcpstore.wiki)


### docker部署 



## Star History

<div align="center">

[![Star History Chart](https://api.star-history.com/svg?repos=whillhill/mcpstore&type=Date)](https://star-history.com/#whillhill/mcpstore&Date)

</div>

---

McpStore 仍在高频更新中，欢迎反馈与建议。
