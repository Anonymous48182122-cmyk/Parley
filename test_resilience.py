import pytest

from agents import runner


def _agent_error(msg="models busy"):
    return runner.AgentCallError(msg)


def test_one_failed_first_pass_does_not_end_the_session(monkeypatch):
    def fake(agent, ticker, data, prefer_provider=None):
        if agent == "burry":
            raise _agent_error()
        return f"{agent} write up\nVerdict: Buy"
    monkeypatch.setattr(runner, "run_stage1", fake)
    seen = []
    out = runner.run_stage1_all("X", "d", agent_keys=["buffett", "munger", "lynch", "burry"],
                                on_update=lambda kind, p: seen.append((kind, p["agent"])))
    assert sorted(out) == ["buffett", "lynch", "munger"] and ("stage1", "burry") not in seen


def test_too_few_first_passes_still_fails(monkeypatch):
    monkeypatch.setattr(runner, "run_stage1", lambda *a, **k: (_ for _ in ()).throw(_agent_error()))
    with pytest.raises(runner.AgentCallError):
        runner.run_stage1_all("X", "d", agent_keys=["buffett", "munger", "lynch"])


def test_a_debate_turn_is_retried_and_a_stubborn_one_is_skipped(monkeypatch):
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def fake(agent, ticker, data, turns, instruction, roster, own_position=None):
        calls["n"] += 1
        if agent == "munger":
            raise _agent_error()
        if agent == "lynch" and calls["n"] < 4:  # fails twice, then works
            raise _agent_error()
        return f"{agent} speaks"
    monkeypatch.setattr(runner, "run_debate_turn", fake)
    turns = runner.run_full_debate("X", "d", {"buffett": "a", "munger": "b", "lynch": "c"},
                                   agent_keys=["buffett", "munger", "lynch"])
    speakers = [a for a, _ in turns]
    assert "munger" not in speakers  # skipped after three tries each time
    assert speakers.count("lynch") >= 1 and speakers.count("buffett") >= 1  # the retried turn went through
