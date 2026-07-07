def test_registry_exposes_scene_and_scripted_plan():
    from examples.west_world_test.registry import RESOURCES_MAPS

    assert "scene" in RESOURCES_MAPS["environment_components"]
    assert "SceneRecorderPlugin" in RESOURCES_MAPS["environment_plugins"]
    assert "ScriptedPlanPlugin" in RESOURCES_MAPS["agent_plugins"]
