"""
Adapters module - Unified export of all adapters

Provides adapters for various AI frameworks, facilitating integration of MCPStore
into different AI Agent frameworks.
"""


def __getattr__(name: str):
    """Lazy-load adapters on first access to avoid importing optional dependencies eagerly."""
    _mapping = {
        "LangChainAdapter": ".langchain_adapter",
        "OpenAIAdapter": ".openai_adapter",
        "AutoGenAdapter": ".autogen_adapter",
        "LlamaIndexAdapter": ".llamaindex_adapter",
        "CrewAIAdapter": ".crewai_adapter",
        "SemanticKernelAdapter": ".semantic_kernel_adapter",
    }
    if name in _mapping:
        import importlib
        module = importlib.import_module(_mapping[name], package=__name__)
        cls = getattr(module, name)
        globals()[name] = cls
        return cls
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "LangChainAdapter",
    "OpenAIAdapter",
    "AutoGenAdapter",
    "LlamaIndexAdapter",
    "CrewAIAdapter",
    "SemanticKernelAdapter",
]
