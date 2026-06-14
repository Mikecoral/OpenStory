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


def _proposal(**overrides):
    value = {
        "permission": True,
        "reason": "",
        "private_feedback": "酒杯碎了。",
        "broadcast_level": "location",
        "event_summary": "有人打碎酒杯。",
        "patches": [{"object_id": "obj_0", "state": "破碎"}],
    }
    value.update(overrides)
    return json.dumps(value, ensure_ascii=False)


def test_patch_updates_only_named_object():
    recorder = StructuredLocationRecorder(LOCATION, FakeLLM([_proposal()]))

    result = recorder.submit_action("maeve", "我把酒杯摔碎", tick=3)

    assert result["permission"] is True
    assert _reg_state("saloon", "酒杯")["state"] == "破碎"
    assert _reg_state("saloon", "旧照片")["state"] == "状态正常"
    assert recorder.fact_ledger[0]["tick"] == 3
    assert "酒杯：破碎" in recorder.chunks["dynamic_objects"]
    assert "旧照片" not in recorder.chunks["dynamic_objects"]


def test_unknown_object_id_is_rejected_atomically():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_proposal(patches=[
            {"object_id": "obj_0", "state": "破碎"},
            {"object_id": "unknown", "state": "消失"},
        ])]),
    )

    result = recorder.submit_action("maeve", "破坏所有东西", tick=3)

    assert result["permission"] is False
    assert "未知 object_id" in result["reason"]
    # visible object state unchanged
    assert _reg_state("saloon", "酒杯")["state"] == "完整"
    assert _reg_state("saloon", "旧照片")["state"] == "状态正常"
    assert recorder.fact_ledger == []


def test_held_by_cannot_be_assigned_to_another_agent():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_proposal(patches=[{"object_id": "obj_0", "held_by": "teddy"}])]),
    )

    result = recorder.submit_action("maeve", "把酒杯交给泰迪", tick=4)

    assert result["permission"] is True
    assert _reg_state("saloon", "酒杯")["held_by"] == ""


def test_held_by_can_pass_to_present_agent():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_proposal(patches=[{"object_id": "obj_0", "held_by": "teddy"}])]),
    )
    recorder.set_present_agents(["maeve", "teddy"])

    result = recorder.submit_action("maeve", "把酒杯交给泰迪", tick=4)

    assert result["permission"] is True
    assert _reg_state("saloon", "酒杯")["held_by"] == "teddy"


def test_held_by_to_absent_agent_is_rejected():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_proposal(patches=[{"object_id": "obj_0", "held_by": "ghost"}])]),
    )
    recorder.set_present_agents(["maeve"])

    result = recorder.submit_action("maeve", "把酒杯交给幽灵", tick=4)

    assert result["permission"] is True
    assert _reg_state("saloon", "酒杯")["held_by"] == ""

def test_tick_update_does_not_call_llm():
    llm = FakeLLM([_proposal()])
    recorder = StructuredLocationRecorder(LOCATION, llm)
    recorder.submit_action("maeve", "我把酒杯摔碎", tick=3)

    recorder.tick_update(3)

    assert len(llm.calls) == 1


def test_free_field_patch_stores_extra_attributes():
    """LLM can add arbitrary fields like quantity or container."""
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_proposal(patches=[
            {"object_id": "obj_0", "state": "半满", "quantity": "半杯"}
        ])]),
    )

    recorder.submit_action("maeve", "喝了半杯酒", tick=1)

    assert _reg_state("saloon", "酒杯")["state"] == "半满"
    assert _reg_state("saloon", "酒杯")["quantity"] == "半杯"
    assert "quantity：半杯" in recorder.chunks["dynamic_objects"]


def test_meta_field_patch_is_rejected():
    """Patches cannot overwrite protected meta fields like name."""
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_proposal(patches=[{"object_id": "obj_0", "name": "黄金酒杯"}])]),
    )

    result = recorder.submit_action("maeve", "重命名酒杯", tick=1)

    assert result["permission"] is False
    assert "保留字段" in result["reason"]
    assert _reg_state("saloon", "酒杯")["name"] == "酒杯"


def test_hidden_object_not_exposed_in_public_state_but_facts_preserved():
    """Hidden objects must not appear in public dynamic_objects, yet stay tracked internally."""
    recorder = StructuredLocationRecorder(LOCATION, FakeLLM([_proposal()]))
    recorder.submit_action("maeve", "随便看看", tick=0)

    assert "旧照片" not in recorder.chunks["dynamic_objects"]
    # registry should still have it (include_hidden=True)
    all_objs = get_object_registry().objects_at("saloon", include_hidden=True)
    assert any(r["name"] == "旧照片" for r in all_objs)


def test_recorder_sees_hidden_secret_in_judge_prompt():
    """The parse/judge prompt must carry hidden secrets so the recorder can decide whether to reveal."""
    llm = FakeLLM([_proposal()])
    recorder = StructuredLocationRecorder(LOCATION, llm)

    recorder.submit_action("dolores", "我走到角落，捡起地上那张照片仔细端详", tick=2)

    prompt = llm.calls[0]
    assert "现代照片" in prompt            # secret reaches the recorder's judging view
    assert "旧照片" in prompt              # hidden object name is in the secret section
    # but the secret never leaks into the public chunk
    assert "现代照片" not in recorder.chunks["dynamic_objects"]


def test_secret_revealed_only_via_private_feedback():
    """When the recorder decides the action touched the secret, it surfaces via private_feedback only."""
    reveal = _proposal(
        private_feedback="你拾起照片，照片里是个站在霓虹都市夜景中的女人，与此地格格不入。",
        patches=[],
    )
    recorder = StructuredLocationRecorder(LOCATION, FakeLLM([reveal]))

    result = recorder.submit_action("dolores", "捡起角落的照片端详", tick=2)

    assert "霓虹都市" in result["private_feedback"]
    # discovery does not mutate any object state nor leak to public/other agents
    assert _reg_state("saloon", "旧照片")["state"] == "状态正常"
    assert "霓虹都市" not in recorder.chunks["dynamic_objects"]


def test_patch_targeting_hidden_object_is_dropped_without_failing_action():
    """A patch aimed at a hidden object is silently skipped; the rest of the action still applies."""
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_proposal(patches=[
            {"object_id": "obj_0", "state": "破碎"},
            {"object_id": "obj_1", "state": "被翻看"},  # hidden — must be dropped
        ])]),
    )

    result = recorder.submit_action("maeve", "摔了酒杯，顺手翻了下角落照片", tick=3)

    assert result["permission"] is True
    assert _reg_state("saloon", "酒杯")["state"] == "破碎"       # visible patch applied
    assert _reg_state("saloon", "旧照片")["state"] == "状态正常"  # hidden stays untouched
    assert _reg_state("saloon", "旧照片")["hidden"] is True      # never migrates to visible


def _proposal_full(**overrides):
    value = {
        "permission": True, "reason": "", "private_feedback": "做了点事。",
        "broadcast_level": "location", "event_summary": "",
        "patches": [], "new_objects": [], "destroy": [], "ambient": "",
    }
    value.update(overrides)
    return json.dumps(value, ensure_ascii=False)


def test_new_objects_are_created_with_provenance():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_proposal_full(new_objects=[{"name": "地上的血", "state": "暗红一滩", "held_by": ""}])]),
    )
    recorder.submit_action("hector", "开枪", tick=5)
    blood = _reg_state("saloon", "地上的血")
    assert blood["state"] == "暗红一滩"
    assert blood["provenance"]["created_by"] == "hector"
    assert blood["provenance"]["created_tick"] == 5


def test_destroy_soft_deletes_object():
    recorder = StructuredLocationRecorder(LOCATION, FakeLLM([_proposal_full(destroy=["obj_0"])]))
    recorder.submit_action("maeve", "把酒杯扔进火里", tick=6)
    reg = get_object_registry()
    assert reg.get("obj_0")["destroyed"] is True


def test_ambient_is_rewritten_and_readable():
    recorder = StructuredLocationRecorder(LOCATION, FakeLLM([_proposal_full(ambient="灯光昏暗，弥漫硝烟味。")]))
    recorder.submit_action("maeve", "环顾四周", tick=7)
    assert recorder.chunks["ambient"] == "灯光昏暗，弥漫硝烟味。"
    assert recorder.read("maeve", ["ambient"])["ambient"] == "灯光昏暗，弥漫硝烟味。"


def test_new_object_cannot_be_hidden():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_proposal_full(new_objects=[{"name": "暗格", "hidden": True}])]),
    )
    recorder.submit_action("maeve", "藏东西", tick=8)
    created = _reg_state("saloon", "暗格")
    assert created["hidden"] is False


def test_destroy_unknown_id_is_dropped_without_failing_action():
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_proposal_full(destroy=["obj_999"], event_summary="无效销毁")]),
    )
    judgement = recorder.submit_action("maeve", "试图销毁不存在的东西", tick=9)
    assert judgement["permission"] is True


def test_leaving_does_not_release_objects_held_by_others():
    """Only the leaving agent's holdings are released; others' holdings are preserved."""
    recorder = StructuredLocationRecorder(
        LOCATION,
        FakeLLM([_proposal(patches=[{"object_id": "obj_0", "held_by": "maeve"}])]),
    )
    recorder.submit_action("maeve", "拿起酒杯", tick=1)

    recorder.agent_leave("teddy")  # a different agent leaves

    assert _reg_state("saloon", "酒杯")["held_by"] == "maeve"
