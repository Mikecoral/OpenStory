"""全链路冒烟：需要 Redis 与 models_config.yaml，缺则跳过。"""
import json
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
def test_full_pipeline_smoke(tmp_path):
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{ROOT}:{os.path.join(ROOT, 'packages/agentkernel-distributed')}"
    env["WW_MAX_TICKS"] = "3"
    env["WW_RUN_DIR"] = str(tmp_path / "sim_run")
    result = subprocess.run(
        ["python", "-m", "examples.west_world_test.run_simulation"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=1800)
    assert result.returncode == 0, result.stderr[-3000:]
    manifest = json.loads((tmp_path / "sim_run" / "manifest.json").read_text(encoding="utf-8"))
    timeline = [
        json.loads(line)
        for line in (tmp_path / "sim_run" / "timeline.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert manifest["status"] == "completed"
    assert manifest["completed_ticks"] == 3
    assert len(timeline) == 4  # initial snapshot + 3 completed ticks
    assert all(row["consistency"]["ok"] for row in timeline)
    assert all("plan_decision" in state for state in timeline[-1]["agents"].values())
    assert (tmp_path / "sim_run" / "model_traces.jsonl").exists()
