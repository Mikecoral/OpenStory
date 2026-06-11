from examples.west_world_test.core.llm_client import FakeImageGen, FakeLLM, FakeVLM
from examples.west_world_test.core.image_representation import ImageRepresentation
from examples.west_world_test.core.schema import Event, Probe
from examples.west_world_test.core.text_representation import TextRepresentation


def _ev(**kwargs):
    data = {"tick": 1, "actor": "酒保", "action": "pour_whiskey", "target": "glass"}
    data.update(kwargs)
    return Event.from_dict(data)


def test_fake_llm_returns_scripted_replies_in_order():
    llm = FakeLLM(["回复A", "回复B"])
    assert llm.chat("p1") == "回复A"
    assert llm.chat("p2") == "回复B"
    assert llm.calls == ["p1", "p2"]


def test_fake_llm_default_when_exhausted():
    assert FakeLLM([], default="DEF").chat("x") == "DEF"


def test_fake_image_gen_records_prompt_and_returns_handle():
    generator = FakeImageGen()
    initial = generator.create_initial("一个酒馆")
    updated = generator.apply_event(initial, "酒保打碎酒杯")
    assert "酒馆" in generator.initial_prompts[0]
    assert generator.event_calls == [(initial, "酒保打碎酒杯")]
    assert updated == "fake-image://event-1"


def test_fake_vlm_answers_from_scripted():
    vlm = FakeVLM(["2"])
    assert vlm.ask("handle://img", "几个酒杯?") == "2"
    assert vlm.calls[0][1] == "几个酒杯?"


def test_text_update_and_answer():
    llm = FakeLLM(["吧台上有2个完整酒杯。", "2"])
    representation = TextRepresentation(llm, initial_text="吧台上有3个完整酒杯。")
    representation.update(_ev())
    assert representation.text == "吧台上有2个完整酒杯。"
    assert "3个完整酒杯" in llm.calls[0]
    assert "pour_whiskey" in llm.calls[0]
    probe = Probe.from_dict({"id": "q1", "kind": "state", "text": "几个完整酒杯?", "field": "glasses_intact", "answer_type": "int"})
    assert representation.answer(probe) == "2"
    assert "几个完整酒杯" in llm.calls[1]


def test_image_update_evolves_previous_image_without_text_state():
    generator = FakeImageGen()
    vlm = FakeVLM(["2", "是"])
    representation = ImageRepresentation(generator, vlm, initial_text="吧台上有3个完整酒杯。")
    representation.update(_ev())
    assert not hasattr(representation, "scene_text")
    assert len(generator.initial_prompts) == 1
    assert generator.event_calls[0][0] == "fake-image://initial"
    assert "pour_whiskey" in generator.event_calls[0][1]
    assert representation.current_image == "fake-image://event-1"
    probe = Probe.from_dict({"id": "q1", "kind": "state", "text": "几个完整酒杯?", "field": "glasses_intact", "answer_type": "int"})
    assert representation.answer(probe) == "2"
    assert representation.answer(probe) == "是"
    assert len(generator.event_calls) == 1
    assert vlm.calls[0][0] == "fake-image://event-1"


def test_image_updates_form_a_history_chain():
    generator = FakeImageGen()
    representation = ImageRepresentation(generator, FakeVLM([]))
    representation.update(_ev(tick=1))
    representation.update(_ev(tick=2, action="smash_glass"))
    assert generator.event_calls[0][0] == "fake-image://initial"
    assert generator.event_calls[1][0] == "fake-image://event-1"
    assert representation.current_image == "fake-image://event-2"
