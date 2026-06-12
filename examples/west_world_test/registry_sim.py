"""正式仿真的资源注册表（与 MVE 的 registry.py 并存）。"""
from agentkernel_distributed.mas.action.components import CommunicationComponent, OtherActionsComponent
from agentkernel_distributed.mas.agent.components import (
    InvokeComponent,
    PerceiveComponent,
    PlanComponent,
    ProfileComponent,
)
from agentkernel_distributed.mas.environment.components import RelationComponent
from agentkernel_distributed.mas.system.components import Messager, Timer
from agentkernel_distributed.toolkit.models.api.openai import OpenAIProvider
from agentkernel_distributed.toolkit.storages import RedisKVAdapter

from examples.story_of_the_stone.BasicController import BasicController
from examples.story_of_the_stone.plugins.action.communication.BasicCommunicationPlugin import BasicCommunicationPlugin
from examples.story_of_the_stone.plugins.action.move.BasicMovePlugin import BasicMovePlugin
from examples.story_of_the_stone.plugins.action.other.BasicOtherActionPlugin import BasicOtherActionPlugin
from examples.story_of_the_stone.plugins.agent.profile.BasicProfliePlugin import BasicProfilePlugin
from examples.story_of_the_stone.plugins.agent.state.BasicStatePlugin import BasicStatePlugin
from examples.story_of_the_stone.plugins.agent.state.component import BasicStateComponent
from examples.story_of_the_stone.plugins.environment.relation.BasicRelationPlugin import BasicRelationPlugin
from examples.west_world_test.WestWorldPodManager import WestWorldPodManager
from examples.west_world_test.plugins.agent.invoke.WestWorldInvokePlugin import WestWorldInvokePlugin
from examples.west_world_test.plugins.agent.perceive.WestWorldPerceivePlugin import WestWorldPerceivePlugin
from examples.west_world_test.plugins.agent.plan.RandomWalkPlanPlugin import RandomWalkPlanPlugin

RESOURCES_MAPS = {
    "agent_components": {
        "profile": ProfileComponent,
        "perceive": PerceiveComponent,
        "plan": PlanComponent,
        "invoke": InvokeComponent,
        "state": BasicStateComponent,
    },
    "agent_plugins": {
        "BasicProfilePlugin": BasicProfilePlugin,
        "BasicStatePlugin": BasicStatePlugin,
        "WestWorldPerceivePlugin": WestWorldPerceivePlugin,
        "RandomWalkPlanPlugin": RandomWalkPlanPlugin,
        "WestWorldInvokePlugin": WestWorldInvokePlugin,
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
    },
    "environment_plugins": {
        "BasicRelationPlugin": BasicRelationPlugin,
    },
    "system_components": {
        "messager": Messager,
        "timer": Timer,
    },
    "models": {
        "OpenAIProvider": OpenAIProvider,
    },
    "adapters": {
        "RedisKVAdapter": RedisKVAdapter,
    },
    "controller": BasicController,
    "pod_manager": WestWorldPodManager,
}
