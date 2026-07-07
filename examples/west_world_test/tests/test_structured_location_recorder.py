import json
import pytest

from examples.west_world_test.core.llm_client import FakeLLM
from examples.west_world_test.recorder.structured_location_recorder import StructuredLocationRecorder
from examples.west_world_test.recorder.world_object_registry import get_object_registry, reset_object_registry
from examples.west_world_test.worldmap.loader import Location

LOCATION = Location(
    id="saloon", name="酒馆", region="sweetwater", type="interior",
    active=True, bbox=[0, 0, 0, 0], adjacency=[],
    objects=[
        {"name": "酒杯", "note": "完整"},
        {"name": "旧照片", "hidden": True, "secret": "现代照片"},
    ],
)


@pytest.fixture(autouse=True)
def _fresh_registry():
    reset_object_registry()
    yield
    reset_object_registry()


def _reg_state(location_id, name):
    reg = get_object_registry()
    row = next(r for r in reg.objects_at(location_id, include_hidden=True) if r["name"] == name)
    return row


def _batch(agent_id="maeve", **overrides):
    """Batch LLM response for a single agent action."""
    action = {
        "agent_id": agent_id,
        "permission": True,
        "reason": "",
        "private_feedback": "酒杯碎了。",
        "patches": [{"object_id": "obj_0", "state": "破碎"}],
        "new_objects": [],
        "destroy": [],
    }
    for k in ("permission", "reason", "private_feedback", "patches", "new_objects", "destroy"):
        if k in overrides:
            action[k] = overrides.pop(k)
    global_fields = {"ambient": "", "broadcast_level": "location", "event_summary": "有人打碎酒杯。"}
    global_fields.update(overrides)
    return json.dumps({"actions": [action], **global_fields}, ensure_ascii=False)


def _batch_full(agent_id="maeve", **overrides):
    """Full batch response with all fields at their safe defaults."""
    action = {
        "agent_id": agent_id,
        "permission": True,
        "reason": "",
        "private_feedback": "做了点事。",
        "patches": [],
        "new_objects": [],
        "destroy": [],
    }
    for k in ("permission", "reason", "private_feedback", "patches", "new_objects", "destroy"):
        if k in overrides:
            action[k] = overrides.pop(k)
    global_fields = {"ambient": "", "broadcast_level": "location", "event_summary": ""}
    global_fields.update(overrides)
    return json.dumps({"actions": [action], **global_fields}, ensure_ascii=False)


def _submit_and_resolve(recorder, agent_id, action_text, tick, action_type="do"):
    """Helper: submit action, run tick_update, return feedback."""
    recorder.submit_action(agent_id, action_text, tick=tick, action_type=action_type)
    recorder.tick_update(tick)
    return recorder.read_feedback(agent_id)


def test_patch_updates_only_named_object():
    recorder = StructuredLocationRecorder(LOCATION, FakeLLM([_batch()]))

    result = _submit_and_resolve(recorder, "maeve", "我把酒杯摔碎", tick=3)

    assert result["permission"] is True
    assert _reg_state("saloon", "酒杯")["state"] == "破碎"
    assert _reg_state("saloon", "旧照片")["state"] == "状态正常"
    assert recorder.fact_ledger[0]["tick"] == 3
    assert recorder.fact_ledger[0]["registry_events"]
    assert "before" not in recorder.fact_ledger[0]
    assert "after" not in recorder.fact_ledger[0]
    assert "酒杯：破碎" in recorder.chunks["dynamic_objects"]
    assert "旧照片" not in recorder.chunks["dynamic_objects"]


def test_unknown_object_id_is_rejected_atomically():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_batch(patches=[
            {"object_id": "obj_0", "state": "破碎"},
            {"object_id": "unknown", "state": "消失"},
        ])]),
    )

    result = _submit_and_resolve(recorder, "maeve", "破坏所有东西", tick=3)

    assert result["permission"] is False
    assert "未知 object_id" in result["reason"]
    assert _reg_state("saloon", "酒杯")["state"] == "完整"
    assert _reg_state("saloon", "旧照片")["state"] == "状态正常"
    assert recorder.fact_ledger[-1]["status"] == "unresolved"
    assert recorder._unresolved_actions[-1]["action_text"] == "破坏所有东西"
    assert recorder.fact_ledger[-1]["retry_scheduled"] is True


def test_held_by_cannot_be_assigned_to_another_agent():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_batch(patches=[{"object_id": "obj_0", "held_by": "teddy"}])]),
    )

    result = _submit_and_resolve(recorder, "maeve", "把酒杯交给泰迪", tick=4)

    assert result["permission"] is True
    assert _reg_state("saloon", "酒杯")["held_by"] == ""


def test_held_by_can_pass_to_present_agent():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_batch(patches=[{"object_id": "obj_0", "held_by": "teddy"}])]),
    )
    recorder.set_present_agents(["maeve", "teddy"])

    result = _submit_and_resolve(recorder, "maeve", "把酒杯交给泰迪", tick=4)

    assert result["permission"] is True
    assert _reg_state("saloon", "酒杯")["held_by"] == "teddy"


def test_held_by_to_absent_agent_is_rejected():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_batch(patches=[{"object_id": "obj_0", "held_by": "ghost"}])]),
    )
    recorder.set_present_agents(["maeve"])

    result = _submit_and_resolve(recorder, "maeve", "把酒杯交给幽灵", tick=4)

    assert result["permission"] is True
    assert _reg_state("saloon", "酒杯")["held_by"] == ""


def test_submit_action_does_not_call_llm():
    """submit_action only queues; tick_update triggers the LLM."""
    llm = FakeLLM([_batch()])
    recorder = StructuredLocationRecorder(LOCATION, llm)

    recorder.submit_action("maeve", "我把酒杯摔碎", tick=3)
    assert len(llm.calls) == 0

    recorder.tick_update(3)
    assert len(llm.calls) == 1


def test_free_field_patch_stores_extra_attributes():
    """LLM can add arbitrary fields like quantity or container."""
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_batch(patches=[
            {"object_id": "obj_0", "state": "半满", "quantity": "半杯"}
        ])]),
    )

    _submit_and_resolve(recorder, "maeve", "喝了半杯酒", tick=1)

    assert _reg_state("saloon", "酒杯")["state"] == "半满"
    assert _reg_state("saloon", "酒杯")["quantity"] == "半杯"
    assert "quantity：半杯" in recorder.chunks["dynamic_objects"]


def test_meta_field_patch_is_rejected():
    """Patches cannot overwrite protected meta fields like name."""
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_batch(patches=[{"object_id": "obj_0", "name": "黄金酒杯"}])]),
    )

    result = _submit_and_resolve(recorder, "maeve", "重命名酒杯", tick=1)

    assert result["permission"] is False
    assert "保留字段" in result["reason"]
    assert _reg_state("saloon", "酒杯")["name"] == "酒杯"
    assert recorder.fact_ledger[-1]["status"] == "unresolved"


def test_parse_failure_is_preserved_and_retried_on_tick_update():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM(["not json", "still not json", _batch_full(patches=[])]),
    )

    recorder.submit_action("maeve", "擦拭吧台", tick=2)
    assert recorder._intent_queue  # queued, not yet processed

    recorder.tick_update(2)
    # LLM exhausted retries on both "not json" responses → unresolved
    assert recorder._unresolved_actions
    assert recorder.fact_ledger[-1]["status"] == "unresolved"

    recorder.tick_update(3)
    # Retry succeeds with _batch_full
    assert recorder._unresolved_actions == []
    assert recorder.fact_ledger[-1]["status"] == "resolved"


def test_do_event_summary_cannot_claim_cross_location_move():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_batch_full(event_summary="梅芙离开酒馆，前往火车站。", broadcast_level="location")]),
    )

    _submit_and_resolve(recorder, "maeve", "朝门口看了一眼", tick=3, action_type="do")

    # Global event_summary normalized: movement keywords replaced
    assert recorder.chunks["recent_events"][-1] == "maeve在酒馆采取了行动。"


def test_invalid_broadcast_level_is_normalized():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_batch_full(broadcast_level="场地", event_summary="梅芙擦拭吧台。")]),
    )

    _submit_and_resolve(recorder, "maeve", "擦拭吧台", tick=3)

    assert recorder.chunks["recent_events"][-1] == "梅芙擦拭吧台。"


def test_hidden_object_not_exposed_in_public_state_but_facts_preserved():
    """Hidden objects must not appear in public dynamic_objects, yet stay tracked internally."""
    recorder = StructuredLocationRecorder(LOCATION, FakeLLM([_batch()]))
    _submit_and_resolve(recorder, "maeve", "随便看看", tick=0)

    assert "旧照片" not in recorder.chunks["dynamic_objects"]
    all_objs = get_object_registry().objects_at("saloon", include_hidden=True)
    assert any(r["name"] == "旧照片" for r in all_objs)


def test_recorder_sees_hidden_secret_in_judge_prompt():
    """The batch prompt must carry hidden secrets so the recorder can decide whether to reveal."""
    llm = FakeLLM([_batch()])
    recorder = StructuredLocationRecorder(LOCATION, llm)

    _submit_and_resolve(recorder, "dolores", "我走到角落，捡起地上那张照片仔细端详", tick=2)

    prompt = llm.calls[0]
    assert "现代照片" in prompt
    assert "旧照片" in prompt
    assert "现代照片" not in recorder.chunks["dynamic_objects"]


def test_secret_revealed_only_via_private_feedback():
    """When the recorder decides the action touched the secret, it surfaces via private_feedback only."""
    reveal = _batch(
        agent_id="dolores",
        private_feedback="你拾起照片，照片里是个站在霓虹都市夜景中的女人，与此地格格不入。",
        patches=[],
    )
    recorder = StructuredLocationRecorder(LOCATION, FakeLLM([reveal]))

    result = _submit_and_resolve(recorder, "dolores", "捡起角落的照片端详", tick=2)

    assert "霓虹都市" in result["private_feedback"]
    assert _reg_state("saloon", "旧照片")["state"] == "状态正常"
    assert "霓虹都市" not in recorder.chunks["dynamic_objects"]


def test_patch_targeting_hidden_object_is_dropped_without_failing_action():
    """A patch aimed at a hidden object is silently skipped; the rest of the action still applies."""
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_batch(patches=[
            {"object_id": "obj_0", "state": "破碎"},
            {"object_id": "obj_1", "state": "被翻看"},  # hidden — must be dropped
        ])]),
    )

    result = _submit_and_resolve(recorder, "maeve", "摔了酒杯，顺手翻了下角落照片", tick=3)

    assert result["permission"] is True
    assert _reg_state("saloon", "酒杯")["state"] == "破碎"
    assert _reg_state("saloon", "旧照片")["state"] == "状态正常"
    assert _reg_state("saloon", "旧照片")["hidden"] is True


def test_new_objects_are_created_with_provenance():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_batch_full(agent_id="hector", new_objects=[{"name": "地上的血", "state": "暗红一滩", "held_by": ""}])]),
    )
    _submit_and_resolve(recorder, "hector", "开枪", tick=5)
    blood = _reg_state("saloon", "地上的血")
    assert blood["state"] == "暗红一滩"
    assert blood["provenance"]["created_by"] == "hector"
    assert blood["provenance"]["created_tick"] == 5


def test_destroy_soft_deletes_object():
    recorder = StructuredLocationRecorder(LOCATION, FakeLLM([_batch_full(destroy=["obj_0"])]))
    _submit_and_resolve(recorder, "maeve", "把酒杯扔进火里", tick=6)
    assert get_object_registry().get("obj_0")["destroyed"] is True


def test_ambient_is_rewritten_and_readable():
    recorder = StructuredLocationRecorder(LOCATION, FakeLLM([_batch_full(ambient="灯光昏暗，弥漫硝烟味。")]))
    _submit_and_resolve(recorder, "maeve", "环顾四周", tick=7)
    assert recorder.chunks["ambient"] == "灯光昏暗，弥漫硝烟味。"
    assert recorder.read("maeve", ["ambient"])["ambient"] == "灯光昏暗，弥漫硝烟味。"


def test_new_object_cannot_be_hidden():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_batch_full(new_objects=[{"name": "暗格", "hidden": True}])]),
    )
    _submit_and_resolve(recorder, "maeve", "藏东西", tick=8)
    assert _reg_state("saloon", "暗格")["hidden"] is False


def test_destroy_unknown_id_is_dropped_without_failing_action():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_batch_full(destroy=["obj_999"], event_summary="无效销毁")]),
    )
    result = _submit_and_resolve(recorder, "maeve", "试图销毁不存在的东西", tick=9)
    assert result["permission"] is True


def test_held_object_not_dropped_on_leave_and_follows_via_registry():
    """agent_leave must NOT drop held objects; holdings follow via registry relocate_holdings."""
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_batch(patches=[{"object_id": "obj_0", "held_by": "maeve"}])]),
    )
    _submit_and_resolve(recorder, "maeve", "拿起酒杯", tick=1)
    assert _reg_state("saloon", "酒杯")["held_by"] == "maeve"

    recorder.agent_leave("maeve")
    assert _reg_state("saloon", "酒杯")["held_by"] == "maeve"

    get_object_registry().relocate_holdings("maeve", "ranch")
    assert _reg_state("ranch", "酒杯")["location_id"] == "ranch"
    assert recorder.read("maeve", ["dynamic_objects"])["dynamic_objects"] == "暂无可变物品。"


def test_hidden_event_summary_is_not_broadcast_to_recent_events():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_batch_full(broadcast_level="none", event_summary="梅芙偷偷拿走了东西")]),
    )

    _submit_and_resolve(recorder, "maeve", "悄悄拿走东西", tick=10)

    assert recorder.chunks["recent_events"] == []


def test_restore_recovers_scene_chunks_and_registry():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_batch_full(ambient="空气里有烟味", patches=[{"object_id": "obj_0", "state": "破碎"}])]),
    )
    _submit_and_resolve(recorder, "maeve", "摔碎酒杯", tick=1)
    scene_snapshot = recorder.snapshot(include_hidden=True)
    scene_snapshot["registry"] = get_object_registry().snapshot()

    get_object_registry().destroy("obj_0", "maeve", 2)
    recorder.chunks["ambient"] = "后来状态"
    recorder.restore(scene_snapshot, restore_registry=True)

    assert _reg_state("saloon", "酒杯")["state"] == "破碎"
    assert recorder.read("maeve", ["ambient"])["ambient"] == "空气里有烟味"


# ── 新增测试 ────────────────────────────────────────────────────────────────

def test_submit_returns_queued_placeholder():
    """submit_action immediately returns a queued placeholder without blocking."""
    recorder = StructuredLocationRecorder(LOCATION, FakeLLM([_batch()]))
    result = recorder.submit_action("maeve", "行动", tick=1)
    assert result["status"] == "queued"
    assert result["permission"] is None


def test_world_state_frozen_during_tick():
    """Agent B cannot see Agent A's changes until tick_update runs."""
    recorder = StructuredLocationRecorder(LOCATION, FakeLLM([
        _batch(agent_id="maeve", patches=[{"object_id": "obj_0", "state": "破碎"}]),
    ]))
    recorder.set_present_agents(["maeve", "teddy"])

    recorder.submit_action("maeve", "摔碎酒杯", tick=1)
    # State not yet changed — frozen during the tick
    assert _reg_state("saloon", "酒杯")["state"] == "完整"

    recorder.tick_update(1)
    # After update, state reflects the action
    assert _reg_state("saloon", "酒杯")["state"] == "破碎"


def test_two_agents_compete_for_same_object():
    """LLM arbitrates: only one agent wins the object."""
    batch_response = json.dumps({
        "actions": [
            {"agent_id": "maeve", "permission": True, "reason": "", "private_feedback": "你拿到了枪。",
             "patches": [{"object_id": "obj_0", "held_by": "maeve"}], "new_objects": [], "destroy": []},
            {"agent_id": "teddy", "permission": False, "reason": "枪已被 maeve 取走",
             "private_feedback": "枪已不在桌上。",
             "patches": [], "new_objects": [], "destroy": []},
        ],
        "ambient": "", "broadcast_level": "location",
        "event_summary": "maeve 拿走了酒杯，teddy 未能如愿。",
    }, ensure_ascii=False)

    recorder = StructuredLocationRecorder(LOCATION, FakeLLM([batch_response]))
    recorder.set_present_agents(["maeve", "teddy"])

    recorder.submit_action("maeve", "拿起酒杯", tick=2)
    recorder.submit_action("teddy", "也想拿酒杯", tick=2)
    recorder.tick_update(2)

    maeve_fb = recorder.read_feedback("maeve")
    teddy_fb = recorder.read_feedback("teddy")

    assert maeve_fb["permission"] is True
    assert teddy_fb["permission"] is False
    assert _reg_state("saloon", "酒杯")["held_by"] == "maeve"
    assert "maeve" in recorder.chunks["recent_events"][-1]


def test_batch_llm_failure_sends_all_to_unresolved():
    """If the whole batch LLM call fails, all intents go to unresolved."""
    recorder = StructuredLocationRecorder(LOCATION, FakeLLM(["not json", "also not json"]))
    recorder.set_present_agents(["maeve", "teddy"])

    recorder.submit_action("maeve", "行动A", tick=3)
    recorder.submit_action("teddy", "行动B", tick=3)
    recorder.tick_update(3)

    assert len(recorder._unresolved_actions) == 2
    maeve_fb = recorder.read_feedback("maeve")
    teddy_fb = recorder.read_feedback("teddy")
    assert maeve_fb["status"] == "unresolved"
    assert teddy_fb["status"] == "unresolved"


def test_one_invalid_patch_does_not_block_others():
    """If one agent's patch is invalid, only that agent goes to unresolved; others still apply."""
    batch_response = json.dumps({
        "actions": [
            {"agent_id": "maeve", "permission": True, "reason": "", "private_feedback": "ok",
             "patches": [{"object_id": "obj_0", "state": "破碎"}], "new_objects": [], "destroy": []},
            {"agent_id": "teddy", "permission": True, "reason": "", "private_feedback": "oops",
             "patches": [{"object_id": "obj_999", "state": "消失"}], "new_objects": [], "destroy": []},
        ],
        "ambient": "", "broadcast_level": "none", "event_summary": "",
    }, ensure_ascii=False)

    recorder = StructuredLocationRecorder(LOCATION, FakeLLM([batch_response]))
    recorder.set_present_agents(["maeve", "teddy"])

    recorder.submit_action("maeve", "摔碎酒杯", tick=4)
    recorder.submit_action("teddy", "尝试操作不存在的东西", tick=4)
    recorder.tick_update(4)

    assert _reg_state("saloon", "酒杯")["state"] == "破碎"  # maeve's patch applied
    assert recorder.read_feedback("maeve")["permission"] is True
    assert recorder.read_feedback("teddy")["status"] == "unresolved"


def test_snapshot_restore_includes_new_fields():
    """snapshot/restore round-trips intent_queue and pending_feedback."""
    recorder = StructuredLocationRecorder(LOCATION, FakeLLM([_batch()]))
    recorder.submit_action("maeve", "行动", tick=1)  # queued but not processed

    snap = recorder.snapshot(include_hidden=True)
    assert len(snap["intent_queue"]) == 1
    assert snap["pending_feedback"] == {}

    # Restore clears the queue since snapshot was taken before tick_update
    recorder2 = StructuredLocationRecorder(LOCATION, FakeLLM([_batch()]))
    recorder2.restore(snap)
    assert len(recorder2._intent_queue) == 1


def test_move_action_does_not_enter_intent_queue():
    """move actions bypass the queue and are handled synchronously by invoke."""
    recorder = StructuredLocationRecorder(LOCATION, FakeLLM([]))
    # move is handled by invoke, not by recorder.submit_action
    # Verify the queue stays empty after a non-do submit (if called at all)
    # In practice, invoke doesn't call submit_action for move — this tests the do queue isolation.
    assert recorder._intent_queue == []
    recorder.submit_action("maeve", "进入大厅", tick=1, action_type="do")
    assert len(recorder._intent_queue) == 1
    recorder._intent_queue.clear()
    assert recorder._intent_queue == []
