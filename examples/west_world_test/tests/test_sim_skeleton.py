"""全链路冒烟：需要 Redis 与 models_config.yaml，缺则跳过。"""
import os
import shutil
import subprocess

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
MODELS = os.path.join(ROOT, "examples/west_world_test/configs/models_config.yaml")


def _redis_alive() -> bool:
    return shutil.which("redis-cli") is not None and \
        subprocess.run(["redis-cli", "ping"], capture_output=True).returncode == 0


@pytest.mark.skipif(not (_redis_alive() and os.path.exists(MODELS)), reason="需要 Redis 与 models_config")
def test_full_pipeline_smoke():
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{ROOT}:{os.path.join(ROOT, 'packages/agentkernel-distributed')}"
    env["WW_MAX_TICKS"] = "3"
    result = subprocess.run(
        ["python", "-m", "examples.west_world_test.run_simulation"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=1800)
    assert result.returncode == 0, result.stderr[-3000:]
