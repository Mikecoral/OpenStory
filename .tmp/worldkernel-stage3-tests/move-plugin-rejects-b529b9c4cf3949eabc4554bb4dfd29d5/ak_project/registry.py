
import importlib.util
import sys
import types

if importlib.util.find_spec("faker") is None and "faker" not in sys.modules:
    faker_stub = types.ModuleType("faker")
    faker_stub.Faker = type("Faker", (), {})
    sys.modules["faker"] = faker_stub

from agentkernel_distributed.mas.action.components import CommunicationComponent, OtherActionsComponent
from agentkernel_distributed.mas.agent.components import InvokeComponent, PerceiveComponent, PlanComponent, ProfileComponent, ReflectComponent
from agentkernel_distributed.mas.environment.components import RelationComponent, SpaceComponent
from agentkernel_distributed.mas.system.components import Messager, Timer
from agentkernel_distributed.toolkit.models.api.openai import OpenAIProvider

from BasicController import WKController
from BasicPodManager import WKPodManager
from plugins.action.wk_plugins import WKCommunicationPlugin, WKMovePlugin, WKOtherActionPlugin
from plugins.agent.wk_plugins import (
    WKInvokePlugin,
    WKPerceivePlugin,
    WKPlanPlugin,
    WKProfilePlugin,
    WKReflectPlugin,
    WKStateComponent,
    WKStatePlugin,
)
from plugins.environment.wk_plugins import WKRelationPlugin, WKSpacePlugin


RESOURCES_MAPS = {
    "agent_components": {
        "profile": ProfileComponent,
        "state": WKStateComponent,
        "plan": PlanComponent,
        "perceive": PerceiveComponent,
        "reflect": ReflectComponent,
        "invoke": InvokeComponent,
    },
    "agent_plugins": {
        "WKProfilePlugin": WKProfilePlugin,
        "WKStatePlugin": WKStatePlugin,
        "WKPlanPlugin": WKPlanPlugin,
        "WKPerceivePlugin": WKPerceivePlugin,
        "WKInvokePlugin": WKInvokePlugin,
        "WKReflectPlugin": WKReflectPlugin,
    },
    "action_components": {
        "communication": CommunicationComponent,
        "move": OtherActionsComponent,
        "otheractions": OtherActionsComponent,
    },
    "action_plugins": {
        "WKCommunicationPlugin": WKCommunicationPlugin,
        "WKMovePlugin": WKMovePlugin,
        "WKOtherActionPlugin": WKOtherActionPlugin,
    },
    "environment_components": {
        "relation": RelationComponent,
        "space": SpaceComponent,
    },
    "environment_plugins": {
        "WKRelationPlugin": WKRelationPlugin,
        "WKSpacePlugin": WKSpacePlugin,
    },
    "system_components": {
        "messager": Messager,
        "timer": Timer,
    },
    "models": {"OpenAIProvider": OpenAIProvider},
    "adapters": {},
    "controller": WKController,
    "pod_manager": WKPodManager,
}
