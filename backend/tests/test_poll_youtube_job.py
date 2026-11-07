from app.jobs import poll_youtube_processing as job


class _FakeSession:
    def __enter__(self):
        return object()

    def __exit__(self, *exc):
        return False


def test_poll_job_reports_success(monkeypatch, capsys):
    monkeypatch.setattr(job, "SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(job, "poll_youtube_processing", lambda db, limit: {"published": 2})
    assert job.main() == 0
    assert '"ok": true' in capsys.readouterr().out


def test_poll_job_fails_closed_on_infrastructure_error(monkeypatch, capsys):
    def boom(db, limit):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(job, "SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(job, "poll_youtube_processing", boom)
    assert job.main() == 1
    assert '"ok": false' in capsys.readouterr().out
