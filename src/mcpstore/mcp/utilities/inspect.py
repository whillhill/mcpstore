"""Utilities for inspecting MCPKit instances (mcpstore.mcp)."""

from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

import mcpstore.mcp
import pydantic_core

from mcpstore.mcp import Client
from mcpstore.mcp.server.server import MCPKit


@dataclass
class ToolInfo:
    """Information about a tool."""

    key: str
    name: str
    description: str | None
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    annotations: dict[str, Any] | None = None
    tags: list[str] | None = None
    title: str | None = None
    icons: list[dict[str, Any]] | None = None
    meta: dict[str, Any] | None = None


@dataclass
class PromptInfo:
    """Information about a prompt."""

    key: str
    name: str
    description: str | None
    arguments: list[dict[str, Any]] | None = None
    tags: list[str] | None = None
    title: str | None = None
    icons: list[dict[str, Any]] | None = None
    meta: dict[str, Any] | None = None


@dataclass
class ResourceInfo:
    """Information about a resource."""

    key: str
    uri: str
    name: str | None
    description: str | None
    mime_type: str | None = None
    annotations: dict[str, Any] | None = None
    tags: list[str] | None = None
    title: str | None = None
    icons: list[dict[str, Any]] | None = None
    meta: dict[str, Any] | None = None


@dataclass
class TemplateInfo:
    """Information about a resource template."""

    key: str
    uri_template: str
    name: str | None
    description: str | None
    mime_type: str | None = None
    parameters: dict[str, Any] | None = None
    annotations: dict[str, Any] | None = None
    tags: list[str] | None = None
    title: str | None = None
    icons: list[dict[str, Any]] | None = None
    meta: dict[str, Any] | None = None


@dataclass
class MCPStoreInfo:
    """Information extracted from a MCPStore instance."""

    name: str
    instructions: str | None
    version: str | None  # The server's own version string (if specified)
    website_url: str | None
    icons: list[dict[str, Any]] | None
    mcpstore_version: str  # Version of MCPStore generating this manifest
    mcp_version: str  # Version of MCP protocol library
    server_generation: int  # Server generation: 1 (mcp package) or 2 (mcpstore)
    tools: list[ToolInfo]
    prompts: list[PromptInfo]
    resources: list[ResourceInfo]
    templates: list[TemplateInfo]
    capabilities: dict[str, Any]


async def inspect_mcpstore(mcp: MCPKit[Any]) -> MCPStoreInfo:
    """Extract information from a MCPKit instance.

    Args:
        mcp: The MCPKit instance to inspect

    Returns:
        MCPStoreInfo dataclass containing the extracted information
    """
    # Get all components (list_* includes middleware, enabled/auth filtering)
    tools_list = await mcp.list_tools()
    prompts_list = await mcp.list_prompts()
    resources_list = await mcp.list_resources()
    templates_list = await mcp.list_resource_templates()

    # Extract detailed tool information
    tool_infos = []
    for tool in tools_list:
        mcp_tool = tool.to_mcp_tool(name=tool.name)
        tool_infos.append(
            ToolInfo(
                key=tool.key,
                name=tool.name or tool.key,
                description=tool.description,
                input_schema=mcp_tool.inputSchema if mcp_tool.inputSchema else {},
                output_schema=tool.output_schema,
                annotations=tool.annotations.model_dump() if tool.annotations else None,
                tags=list(tool.tags) if tool.tags else None,
                title=tool.title,
                icons=[icon.model_dump() for icon in tool.icons]
                if tool.icons
                else None,
                meta=tool.meta,
            )
        )

    # Extract detailed prompt information
    prompt_infos = []
    for prompt in prompts_list:
        prompt_infos.append(
            PromptInfo(
                key=prompt.key,
                name=prompt.name or prompt.key,
                description=prompt.description,
                arguments=[arg.model_dump() for arg in prompt.arguments]
                if prompt.arguments
                else None,
                tags=list(prompt.tags) if prompt.tags else None,
                title=prompt.title,
                icons=[icon.model_dump() for icon in prompt.icons]
                if prompt.icons
                else None,
                meta=prompt.meta,
            )
        )

    # Extract detailed resource information
    resource_infos = []
    for resource in resources_list:
        resource_infos.append(
            ResourceInfo(
                key=resource.key,
                uri=str(resource.uri),
                name=resource.name,
                description=resource.description,
                mime_type=resource.mime_type,
                annotations=resource.annotations.model_dump()
                if resource.annotations
                else None,
                tags=list(resource.tags) if resource.tags else None,
                title=resource.title,
                icons=[icon.model_dump() for icon in resource.icons]
                if resource.icons
                else None,
                meta=resource.meta,
            )
        )

    # Extract detailed template information
    template_infos = []
    for template in templates_list:
        template_infos.append(
            TemplateInfo(
                key=template.key,
                uri_template=template.uri_template,
                name=template.name,
                description=template.description,
                mime_type=template.mime_type,
                parameters=template.parameters,
                annotations=template.annotations.model_dump()
                if template.annotations
                else None,
                tags=list(template.tags) if template.tags else None,
                title=template.title,
                icons=[icon.model_dump() for icon in template.icons]
                if template.icons
                else None,
                meta=template.meta,
            )
        )

    # Basic MCP capabilities that MCPStore supports
    capabilities = {
        "tools": {"listChanged": True},
        "resources": {"subscribe": False, "listChanged": False},
        "prompts": {"listChanged": False},
        "logging": {},
    }

    # Extract server-level icons and website_url
    server_icons = (
        [icon.model_dump() for icon in mcp._mcp_server.icons]
        if hasattr(mcp._mcp_server, "icons") and mcp._mcp_server.icons
        else None
    )
    server_website_url = (
        mcp._mcp_server.website_url if hasattr(mcp._mcp_server, "website_url") else None
    )

    return MCPStoreInfo(
        name=mcp.name,
        instructions=mcp.instructions,
        version=(mcp.version if hasattr(mcp, "version") else mcp._mcp_server.version),
        website_url=server_website_url,
        icons=server_icons,
        mcpstore_version=mcpstore.mcp.__version__,
        mcp_version=importlib.metadata.version("mcp"),
        server_generation=2,  # MCPStore v2
        tools=tool_infos,
        prompts=prompt_infos,
        resources=resource_infos,
        templates=template_infos,
        capabilities=capabilities,
    )


class InspectFormat(str, Enum):
    """Output format for inspect command."""

    MCPSTORE = "mcpstore"
    MCP = "mcp"


def format_mcpstore_info(info: MCPStoreInfo) -> bytes:
    """Format MCPStoreInfo as MCPStore-specific JSON.

    This includes MCPStore-specific fields like tags, enabled, annotations, etc.
    """
    # Build the output dict with nested structure
    result = {
        "server": {
            "name": info.name,
            "instructions": info.instructions,
            "version": info.version,
            "website_url": info.website_url,
            "icons": info.icons,
            "generation": info.server_generation,
            "capabilities": info.capabilities,
        },
        "environment": {
            "mcpstore": info.mcpstore_version,
            "mcp": info.mcp_version,
        },
        "tools": info.tools,
        "prompts": info.prompts,
        "resources": info.resources,
        "templates": info.templates,
    }

    return pydantic_core.to_json(result, indent=2)


async def format_mcp_info(mcp: MCPKit[Any]) -> bytes:
    """Format server info as standard MCP protocol JSON.

    Uses Client to get the standard MCP protocol format with camelCase fields.
    Includes version metadata at the top level.
    """
    async with Client(mcp) as client:
        # Get all the MCP protocol objects
        tools_result = await client.list_tools_mcp()
        prompts_result = await client.list_prompts_mcp()
        resources_result = await client.list_resources_mcp()
        templates_result = await client.list_resource_templates_mcp()

        # Get server info from the initialize result
        server_info = client.initialize_result.serverInfo

        # Combine into MCP protocol structure with environment metadata
        result = {
            "environment": {
                "mcpstore": mcpstore.mcp.__version__,  # Version generating this manifest
                "mcp": importlib.metadata.version("mcp"),  # MCP protocol version
            },
            "serverInfo": server_info,
            "capabilities": {},  # MCP format doesn't include capabilities at top level
            "tools": tools_result.tools,
            "prompts": prompts_result.prompts,
            "resources": resources_result.resources,
            "resourceTemplates": templates_result.resourceTemplates,
        }

        return pydantic_core.to_json(result, indent=2)


async def format_info(
    mcp: MCPKit[Any],
    format: InspectFormat | Literal["mcpstore", "mcp"],
    info: MCPStoreInfo | None = None,
) -> bytes:
    """Format server information according to the specified format.

    Args:
        mcp: The MCPStore instance
        format: Output format ("mcpstore" or "mcp")
        info: Pre-extracted MCPStoreInfo (optional, will be extracted if not provided)

    Returns:
        JSON bytes in the requested format
    """
    # Convert string to enum if needed
    if isinstance(format, str):
        format = InspectFormat(format)

    if format == InspectFormat.MCP:
        # MCP format doesn't need MCPStoreInfo, it uses Client directly
        return await format_mcp_info(mcp)
    elif format == InspectFormat.MCPSTORE:
        # For MCPStore format, we need the MCPStoreInfo
        # This works for both v1 and v2 servers
        if info is None:
            info = await inspect_mcpstore(mcp)
        return format_mcpstore_info(info)
    else:
        raise ValueError(f"Unknown format: {format}")
