from examples.west_world_test.core.metrics import accuracy_over_ticks, contradiction_count, drift_slope, is_correct, normalize


def test_normalize_and_correct():
    assert normalize("还有 2 个", "int") == "2"
    assert normalize("是的", "bool") == "true"
    assert normalize("不在", "bool") == "false"
    assert is_correct("吧台还剩2个", 2, "int")
    assert is_correct("否", False, "bool")
    assert is_correct("无", None, "str")
    assert is_correct("The Man in Black", "黑衣人", "str", ("the man in black",))


def test_accuracy_and_drift():
    records = [{"tick": 1, "correct": True}, {"tick": 1, "correct": False}, {"tick": 2, "correct": True}]
    assert accuracy_over_ticks(records) == {1: 0.5, 2: 1.0}
    assert drift_slope({1: 1.0, 2: 0.8, 3: 0.6}) < 0


def test_contradiction_count():
    records = [
        {"tick": 1, "probe_id": "q1", "norm": "3", "had_relevant_event": False},
        {"tick": 2, "probe_id": "q1", "norm": "2", "had_relevant_event": False},
    ]
    assert contradiction_count(records) == 1
