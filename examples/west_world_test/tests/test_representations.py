from examples.west_world_test.core.llm_client import FakeImageGen, FakeLLM, FakeVLM
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
    handle = generator.generate("一个酒馆")
    assert "酒馆" in generator.prompts[0]
    assert handle


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
