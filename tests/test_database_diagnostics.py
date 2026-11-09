from sqlalchemy.exc import OperationalError

from scripts import check_supabase_connection as diagnostic


def test_connection_failure_hides_credentials_and_disposes_engine(monkeypatch, capsys):
    secret_url = "postgresql://postgres:do-not-print-me@db.example.supabase.co/postgres"
    monkeypatch.setenv("DATABASE_URL", secret_url)
    disposed = []

    class UnavailableEngine:
        def connect(self):
            raise OperationalError("SELECT 1", {}, Exception(
                f"{secret_url}: connection failed: timeout expired"))

        def dispose(self):
            disposed.append(True)

    monkeypatch.setattr(diagnostic, "create_engine", lambda *args, **kwargs: UnavailableEngine())
    assert diagnostic.main() == 2
    output = capsys.readouterr()
    assert "A conexao expirou" in output.err
    assert "do-not-print-me" not in output.err + output.out
    assert "postgresql://" not in output.err + output.out
    assert disposed == [True]


def test_invalid_url_does_not_print_a_traceback_or_credentials(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:do-not-print-me@localhost:invalid/postgres")
    assert diagnostic.main() == 2
    output = capsys.readouterr()
    assert "Falha na conexao" in output.err
    assert "Traceback" not in output.err
    assert "do-not-print-me" not in output.err + output.out


def test_pooler_failure_does_not_misdiagnose_a_wrong_password():
    error = OperationalError("SELECT 1", {}, Exception(
        "FATAL: (EAUTHQUERY) authentication query failed: connection to database not available"))
    message = diagnostic.connection_error_hint(error)
    assert "estado do projeto" in message
    assert "senha" not in message
