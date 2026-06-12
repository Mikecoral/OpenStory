"""load_config 应支持非默认 configs 目录名。"""
import yaml
from agentkernel_distributed.mas.builder import load_config


# Minimal valid content for each sub-config file, matching pydantic model requirements.
_SUB_CONFIGS = {
    "environment_config.yaml": {"name": "test_env", "components": {}},
    "actions_config.yaml": {"name": "test_actions", "components": {}},
    "agent_templates_config.yaml": {"templates": []},
    "system_config.yaml": {"name": "test_system", "components": {}},
    "database_config.yaml": {"pools": {}, "adapters": {}},
    "models_config.yaml": [],
}

_CONFIGS_KEYS = {
    "environment": "environment_config.yaml",
    "actions": "actions_config.yaml",
    "agent_templates": "agent_templates_config.yaml",
    "system": "system_config.yaml",
    "database": "database_config.yaml",
    "models": "models_config.yaml",
}


def _write_minimal_project(tmp_path, dirname):
    cfg_dir = tmp_path / dirname
    cfg_dir.mkdir()
    for filename, content in _SUB_CONFIGS.items():
        (cfg_dir / filename).write_text(yaml.safe_dump(content), encoding="utf-8")
    (cfg_dir / "simulation_config.yaml").write_text(yaml.safe_dump({
        "simulation": {"pod_size": 1, "init_batch_size": 1, "max_ticks": 1},
        "configs": _CONFIGS_KEYS,
        "data": {},
    }), encoding="utf-8")
    return str(tmp_path)


def test_default_dirname_unchanged(tmp_path):
    project = _write_minimal_project(tmp_path, "configs")
    config = load_config(project)
    assert config.simulation.pod_size == 1


def test_custom_dirname(tmp_path):
    project = _write_minimal_project(tmp_path, "configs_sim")
    config = load_config(project, configs_dirname="configs_sim")
    assert config.simulation.pod_size == 1
