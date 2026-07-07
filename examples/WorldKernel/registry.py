from __future__ import annotations

from plugins._optional_deps import ensure_optional_agentkernel_imports

ensure_optional_agentkernel_imports()

from agentkernel_distributed.mas.action.components import CommunicationComponent, OtherActionsComponent
from agentkernel_distributed.mas.agent.components import (
    InvokeComponent,
    PerceiveComponent,
    PlanComponent,
    ProfileComponent,
    ReflectComponent,
)
from agentkernel_distributed.mas.environment.components import RelationComponent, SpaceComponent
from agentkernel_distributed.mas.system.components import Messager, Timer
from agentkernel_distributed.toolkit.models.api.openai import OpenAIProvider
from agentkernel_distributed.toolkit.storages import RedisKVAdapter

from BasicController import WKController
from BasicPodManager import WKPodManager
from plugins.action.communication.BasicCommunicationPlugin import BasicCommunicationPlugin
from plugins.action.move.BasicMovePlugin import BasicMovePlugin
from plugins.action.other.BasicOtherActionPlugin import BasicOtherActionPlugin
from plugins.agent.invoke.BasicInvokePlugin import BasicInvokePlugin
from plugins.agent.perceive.BasicPerceivePlugin import BasicPerceivePlugin
from plugins.agent.plan.BasicPlanPlugin import BasicPlanPlugin
from plugins.agent.profile.BasicProfilePlugin import BasicProfilePlugin
from plugins.agent.reflect.BasicReflectPlugin import BasicReflectPlugin
from plugins.agent.state.BasicStatePlugin import BasicStatePlugin
from plugins.agent.state.component import BasicStateComponent
from plugins.environment.relation.BasicRelationPlugin import BasicRelationPlugin
from plugins.environment.space.BasicSpacePlugin import BasicSpacePlugin


RESOURCES_MAPS = {
    "agent_components": {
        "profile": ProfileComponent,
        "state": BasicStateComponent,
        "plan": PlanComponent,
        "perceive": PerceiveComponent,
        "reflect": ReflectComponent,
        "invoke": InvokeComponent,
    },
    "agent_plugins": {
        "BasicProfilePlugin": BasicProfilePlugin,
        "BasicStatePlugin": BasicStatePlugin,
        "BasicPlanPlugin": BasicPlanPlugin,
        "BasicPerceivePlugin": BasicPerceivePlugin,
        "BasicInvokePlugin": BasicInvokePlugin,
        "BasicReflectPlugin": BasicReflectPlugin,
    },
    "action_components": {
        "communication": CommunicationComponent,
        "move": OtherActionsComponent,
        "otheractions": OtherActionsComponent,
    },
    "action_plugins": {
        "BasicCommunicationPlugin": BasicCommunicationPlugin,
        "BasicMovePlugin": BasicMovePlugin,
        "BasicOtherActionPlugin": BasicOtherActionPlugin,
    },
    "environment_components": {
        "relation": RelationComponent,
        "space": SpaceComponent,
    },
    "environment_plugins": {
        "BasicRelationPlugin": BasicRelationPlugin,
        "BasicSpacePlugin": BasicSpacePlugin,
    },
    "system_components": {
        "messager": Messager,
        "timer": Timer,
    },
    "models": {"OpenAIProvider": OpenAIProvider},
    "adapters": {"RedisKVAdapter": RedisKVAdapter},
    "controller": WKController,
    "pod_manager": WKPodManager,
}
