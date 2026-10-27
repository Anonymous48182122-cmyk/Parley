from backend import job_store, jobs


def _running_job(**extra):
    return {"ticker": "AAPL", "status": "running", "stage1": {}, "debate": [], "agents": ["buffett"], **extra}


def test_a_run_cut_off_by_a_restart_comes_back_as_stopped_early_with_its_content(monkeypatch):
    saved = _running_job(stage1={"buffett": "Verdict: Pass"}, debate=[{"turn": 1, "agent": "buffett", "text": "x"}])
    monkeypatch.setattr(job_store, "load", lambda t: saved)
    jobs._jobs.pop("AAPL", None)
    job = jobs.get_job("aapl")
    assert job["status"] == "error" and job["error_kind"] == "interrupted"
    assert job["stage1"] and job["debate"]  # nothing already produced is thrown away
    jobs._jobs.pop("AAPL", None)


def test_a_run_that_had_produced_nothing_is_simply_started_again(monkeypatch):
    monkeypatch.setattr(job_store, "load", lambda t: _running_job())
    jobs._jobs.pop("AAPL", None)
    assert jobs.get_job("AAPL") is None  # the page sees "no analysis" and starts it again


def test_a_finished_run_is_reused_after_a_restart(monkeypatch):
    done = _running_job(status="complete", cio_memo="memo")
    monkeypatch.setattr(job_store, "load", lambda t: done)
    jobs._jobs.pop("AAPL", None)
    assert jobs.get_job("AAPL")["cio_memo"] == "memo"
    jobs._jobs.pop("AAPL", None)


def test_the_store_does_nothing_when_the_table_is_missing(monkeypatch):
    def boom():
        raise RuntimeError("relation parley_jobs does not exist")
    monkeypatch.setattr(job_store, "_client", boom)
    monkeypatch.setattr(job_store, "_paused_until", 0.0)
    job_store.save("AAPL", "{}")  # must not raise
    assert job_store.load("AAPL") is None
    assert job_store._paused_until > 0  # and it backs off instead of failing on every update
    monkeypatch.setattr(job_store, "_paused_until", 0.0)
