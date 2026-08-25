"""Controlled local execution bridge for standardized Skill extensions."""

from .executor_bridge import (
    ExecutorLoadError,
    ExtensionExecutorBridge,
    UnsupportedSkillExecutor,
)
from .context import (
    EXTENSION_RUNTIME_CONTEXT_VERSION,
    ExtensionRuntimeContext,
)
from .gateway import (
    ExtensionGatewayOperation,
    ExtensionGatewayResult,
    ExtensionMessageReceiver,
    ExtensionNotAvailableError,
    ExtensionRuntimeGateway,
    ExtensionRuntimeGatewayError,
    PluginInvocationFacade,
)
from .models import (
    ArtifactPublisher,
    ArtifactResolver,
    SkillExecutorDescriptor,
    SkillRuntimeResult,
    StreamEventPublisher,
)
from .plugin_bridge import (
    ExternalServiceProbe,
    ExternalServiceSnapshot,
    ExternalServiceState,
    PluginRuntimeBridge,
    PluginRuntimeBridgeError,
    PluginRuntimeDescriptor,
)
from .skill_invoker import SkillInvocationError, SkillInvoker

__all__ = [
    "ArtifactPublisher",
    "ArtifactResolver",
    "EXTENSION_RUNTIME_CONTEXT_VERSION",
    "ExecutorLoadError",
    "ExtensionGatewayOperation",
    "ExtensionGatewayResult",
    "ExtensionMessageReceiver",
    "ExtensionNotAvailableError",
    "ExtensionExecutorBridge",
    "ExtensionRuntimeContext",
    "ExtensionRuntimeGateway",
    "ExtensionRuntimeGatewayError",
    "ExternalServiceProbe",
    "ExternalServiceSnapshot",
    "ExternalServiceState",
    "PluginRuntimeBridge",
    "PluginRuntimeBridgeError",
    "PluginRuntimeDescriptor",
    "PluginInvocationFacade",
    "SkillExecutorDescriptor",
    "SkillInvocationError",
    "SkillInvoker",
    "SkillRuntimeResult",
    "StreamEventPublisher",
    "UnsupportedSkillExecutor",
]
