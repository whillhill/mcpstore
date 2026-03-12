"""
Composed MCPStore class
Defines the final MCPStore by composing mixins and BaseMCPStore in one place
"""
from .base_store import BaseMCPStore
from .config_export_mixin import ConfigExportMixin
from .config_management import ConfigManagementMixin
from .context_factory import ContextFactoryMixin
from .data_space_manager import DataSpaceManagerMixin
from .service_query import ServiceQueryMixin
from .setup_mixin import SetupMixin
from .tool_operations import ToolOperationsMixin


class MCPStore(
    ServiceQueryMixin,
    ToolOperationsMixin,
    ConfigManagementMixin,
    DataSpaceManagerMixin,
    ContextFactoryMixin,
    SetupMixin,
    ConfigExportMixin,
    BaseMCPStore,
):
    """Final composed Store class"""
    pass
