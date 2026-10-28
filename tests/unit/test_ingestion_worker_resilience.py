from fip.platform.jobs import worker


def test_worker_contains_database_failure_and_can_poll_again(monkeypatch):
    calls = []

    def unavailable(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("temporary database failure")

    monkeypatch.setattr(worker, "create_engine", unavailable)
    assert worker.run_once(worker_id="worker") is False
    assert worker.run_once(worker_id="worker") is False
    assert len(calls) == 2
