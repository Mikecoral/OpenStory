"""Resource registry for the West World recorder MVE."""
from agentkernel_distributed.mas.agent.components import PlanComponent
from agentkernel_distributed.mas.environment.components import get_or_create_component_class
from agentkernel_distributed.mas.system.components import Messager, Timer
from agentkernel_distributed.toolkit.models.api.openai import OpenAIProvider
from agentkernel_distributed.toolkit.storages import RedisKVAdapter

from examples.story_of_the_stone.BasicController import BasicController
from examples.story_of_the_stone.plugins.agent.state.BasicStatePlugin import BasicStatePlugin
from examples.story_of_the_stone.plugins.agent.state.component import BasicStateComponent
from examples.west_world_test.WestWorldPodManager import WestWorldPodManager
from examples.west_world_test.plugins.agent.plan.ScriptedPlanPlugin import ScriptedPlanPlugin
from examples.west_world_test.scene.SceneRecorderPlugin import SceneRecorderPlugin

RESOURCES_MAPS = {
    "agent_components": {"plan": PlanComponent, "state": BasicStateComponent},
    "agent_plugins": {"ScriptedPlanPlugin": ScriptedPlanPlugin, "BasicStatePlugin": BasicStatePlugin},
    "action_components": {},
    "action_plugins": {},
    "environment_components": {"scene": get_or_create_component_class("scene")},
    "environment_plugins": {"SceneRecorderPlugin": SceneRecorderPlugin},
    "system_components": {"messager": Messager, "timer": Timer},
    "models": {"OpenAIProvider": OpenAIProvider},
    "adapters": {"RedisKVAdapter": RedisKVAdapter},
    "controller": BasicController,
    "pod_manager": WestWorldPodManager,
}
