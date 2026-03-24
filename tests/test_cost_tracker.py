from src.core.cost_tracker import CostTracker


def test_record_and_summary():
    tracker = CostTracker(model="test-model")
    tracker.record("decompose", "decompose", 100, 50, 0.01)
    tracker.record("generate", "model_oa", 200, 100, 0.03)
    summary = tracker.get_summary()
    assert summary.total_input_tokens == 300
    assert summary.total_output_tokens == 150
    assert summary.total_cost_usd == 0.04
    assert summary.api_calls == 2


def test_reset():
    tracker = CostTracker(model="test-model")
    tracker.record("decompose", "test", 100, 50, 0.01)
    tracker.reset()
    assert tracker.get_summary().api_calls == 0


def test_format_cost_line():
    tracker = CostTracker(model="test-model")
    tracker.record("decompose", "test", 100, 50, 0.01)
    line = tracker.format_cost_line()
    assert "$" in line or "0.01" in line
