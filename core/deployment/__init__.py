"""Offline mapping from Extension packages to AgentScope Workspace plans."""

from .agentscope_adapter import (
    AgentScopeDeploymentAdapter,
    AgentScopeDeploymentBridgeError,
)
from .models import (
    AGENTSCOPE_INSTALL_PLAN_VERSION,
    ExtensionPackageDescriptor,
    InstallAction,
    InstallPlan,
    InstallPlanStep,
    SecretRequirementCheck,
    WorkspaceMapping,
)
from .workspace_mapper import WorkspaceMapper, WorkspaceMappingError

__all__ = [
    "AGENTSCOPE_INSTALL_PLAN_VERSION",
    "AgentScopeDeploymentAdapter",
    "AgentScopeDeploymentBridgeError",
    "ExtensionPackageDescriptor",
    "InstallAction",
    "InstallPlan",
    "InstallPlanStep",
    "SecretRequirementCheck",
    "WorkspaceMapper",
    "WorkspaceMapping",
    "WorkspaceMappingError",
]
