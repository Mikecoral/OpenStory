from examples.west_world_test.core.llm_client import FakeImageGen, FakeLLM, FakeVLM


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
