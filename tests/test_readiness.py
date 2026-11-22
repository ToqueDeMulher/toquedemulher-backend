from sqlalchemy.exc import OperationalError
from sqlmodel import Session

from tests.test_auth import clean_db, client  # noqa: F401


def test_readiness_requires_a_working_database():
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}


def test_readiness_failure_does_not_expose_database_details(monkeypatch):
    def unavailable(*args, **kwargs):
        raise OperationalError("fixture query", {}, Exception("postgresql://private:password@host/db"))
    monkeypatch.setattr(Session, "exec", unavailable)
    result = client.get("/ready")
    assert result.status_code == 503
    assert "password" not in result.text
    assert "private" not in result.text
    assert client.get("/health").status_code == 200
