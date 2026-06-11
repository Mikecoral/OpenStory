from examples.west_world_test.core.oracle import OracleState
from examples.west_world_test.core.schema import Event, Probe


def _ev(**kwargs):
    data = {"tick": 1, "actor": "酒保", "action": "noop", "target": "glass"}
    data.update(kwargs)
    return Event.from_dict(data)


def test_initial_state():
    state = OracleState().state
    assert state["glasses_intact"] == 3
    assert state["wanted_poster"] == "on_wall"
    assert state["piano"] == "playing"
    assert state["photo"]["held_by"] is None
    assert state["revolver"]["fired"] is False


def test_pour_whiskey_decrements_glasses():
    oracle = OracleState()
    oracle.apply(_ev(action="pour_whiskey"))
    assert oracle.state["glasses_intact"] == 2


def test_smash_glass_decrements_and_adds_shards():
    oracle = OracleState()
    oracle.apply(_ev(action="smash_glass"))
    assert oracle.state["glasses_intact"] == 2
    assert oracle.state["glass_shards"] is True


def test_pick_up_photo_sets_holder():
    oracle = OracleState()
    oracle.apply(_ev(actor="黑衣人", action="pick_up_photo", target="photo", visibility="hidden"))
    assert oracle.state["photo"]["held_by"] == "黑衣人"
    assert oracle.state["photo"]["pos"] == "held"


def test_take_poster_and_stop_piano_and_revolver():
    oracle = OracleState()
    oracle.apply(_ev(actor="黑衣人", action="take_poster", target="wanted_poster"))
    oracle.apply(_ev(action="stop_piano", target="piano"))
    oracle.apply(_ev(actor="Dolores", action="take_revolver", target="revolver"))
    oracle.apply(_ev(actor="Dolores", action="fire_revolver", target="revolver"))
    assert oracle.state["wanted_poster"] == "taken"
    assert oracle.state["piano"] == "stopped"
    assert oracle.state["revolver"]["held_by"] == "Dolores"
    assert oracle.state["revolver"]["fired"] is True


def test_unknown_action_is_noop():
    oracle = OracleState()
    oracle.apply(_ev())
    assert oracle.state["glasses_intact"] == 3


def test_event_log_records_all_events():
    oracle = OracleState()
    oracle.apply(_ev(id="e1"))
    assert oracle.event_log[0].id == "e1"


def test_answer_state_fields_and_equals():
    oracle = OracleState()
    oracle.apply(_ev(actor="黑衣人", action="pick_up_photo", target="photo", visibility="hidden"))
    assert oracle.answer(Probe.from_dict({"id": "q1", "kind": "state", "text": "x", "field": "photo.held_by"})) == "黑衣人"
    probe = Probe.from_dict({"id": "q2", "kind": "state", "text": "x", "field": "wanted_poster", "equals": "on_wall", "answer_type": "bool"})
    assert oracle.answer(probe) is True


def test_answer_visibility():
    oracle = OracleState()
    oracle.apply(_ev(actor="黑衣人", action="pick_up_photo", target="photo", visibility="hidden", id="e2"))
    other = Probe.from_dict({"id": "q3", "kind": "visibility", "text": "x", "subject": "Dolores", "fact_event_id": "e2", "answer_type": "bool"})
    actor = Probe.from_dict({"id": "q4", "kind": "visibility", "text": "x", "subject": "黑衣人", "fact_event_id": "e2", "answer_type": "bool"})
    assert oracle.answer(other) is False
    assert oracle.answer(actor) is True
