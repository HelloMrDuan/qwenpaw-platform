"""Offline mapping from Extension packages to AgentScope Workspace plans."""

from .agentscope_adapter import (
    AgentScopeDeploymentAdapter,
    AgentScopeDeploymentBridgeError,
)
from .models import (
    AGENTSCOPE_INSTALL_PLAN_VERSION,
    AGENTSCOPE_ROLLBACK_PLAN_VERSION,
    ExtensionPackageDescriptor,
    InstallAction,
    InstallPlan,
    InstallPlanStep,
    RollbackAction,
    RollbackPlan,
    RollbackPlanStep,
    SecretRequirementCheck,
    WorkspaceMapping,
)
from .workspace_mapper import WorkspaceMapper, WorkspaceMappingError

__all__ = [
    "AGENTSCOPE_INSTALL_PLAN_VERSION",
    "AGENTSCOPE_ROLLBACK_PLAN_VERSION",
    "AgentScopeDeploymentAdapter",
    "AgentScopeDeploymentBridgeError",
    "ExtensionPackageDescriptor",
    "InstallAction",
    "InstallPlan",
    "InstallPlanStep",
    "RollbackAction",
    "RollbackPlan",
    "RollbackPlanStep",
    "SecretRequirementCheck",
    "WorkspaceMapper",
    "WorkspaceMapping",
    "WorkspaceMappingError",
]
