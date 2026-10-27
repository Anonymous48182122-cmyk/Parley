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


def test_cio_failure_gives_an_honest_automatic_summary(monkeypatch):
    from agents.stances import fallback_summary
    names = {"buffett": "Warren Buffett", "munger": "Charlie Munger", "lynch": "Peter Lynch", "thiel": "Peter Thiel"}
    stage1 = {"buffett": "Verdict: Pass", "munger": "Verdict: Pass", "lynch": "Verdict: Buy", "thiel": "Verdict: Buy"}
    turns = [("thiel", "I am changing my call.\nVerdict: Sell")]
    memo, verdict, conviction = fallback_summary(stage1, turns, names)
    assert verdict == "HOLD" and conviction == 3
    assert memo.startswith("VERDICT: HOLD | CONVICTION: 3/10") and "automatic summary" in memo
    assert "Peter Thiel went from Buy to Sell" in memo
    assert fallback_summary({"a": "Verdict: Buy", "b": "Verdict: Buy", "c": "Verdict: Pass"}, [], {})[1] == "BUY"
    assert fallback_summary({"a": "Verdict: Sell", "b": "Verdict: Sell", "c": "Verdict: Pass", "d": "Verdict: Pass"}, [], {})[1] == "SELL"
    assert fallback_summary({"a": "Verdict: Sell", "b": "Verdict: Pass", "c": "Verdict: Pass"}, [], {})[1] == "HOLD"  # one bear is not a camp


def test_run_committee_survives_a_failed_cio(monkeypatch):
    monkeypatch.setattr(runner, "run_stage1_all", lambda *a, **k: {"buffett": "Verdict: Pass", "munger": "Verdict: Pass", "lynch": "Verdict: Buy"})
    monkeypatch.setattr(runner, "run_business_card", lambda *a, **k: None)
    monkeypatch.setattr(runner, "run_full_debate", lambda *a, **k: [("buffett", "Verdict: Pass")])
    monkeypatch.setattr(runner, "run_cio", lambda *a, **k: (_ for _ in ()).throw(_agent_error()))
    seen = []
    out = runner.run_committee("X", "d", agent_keys=["buffett", "munger", "lynch"], on_update=lambda k, p: seen.append((k, p)))
    assert out["verdict"] == "HOLD"
    cio = next(p for k, p in seen if k == "cio")
    assert cio["fallback"] is True and "VERDICT" not in cio["text"]
