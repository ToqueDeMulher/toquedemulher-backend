from html import escape

import pytest

from app.services import email_service


@pytest.mark.parametrize(
    "name", ['<a/href="https://evil.example">Entrar</a>', "", "   ", "João Pedro"]
)
def test_password_reset_escapes_names_and_handles_legacy_empty_names(monkeypatch, name):
    sent = []
    monkeypatch.setattr(
        email_service, "send_email", lambda *args: sent.append(args) or True
    )
    assert email_service.send_password_reset_email(
        "fixture@example.com", name, "fixture-token"
    )
    body = sent[0][2]
    expected = escape(name.split()[0]) if name.split() else "cliente"
    assert f"<h2>Olá, {expected}!</h2>" in body
    assert '<a/href="https://evil.example">' not in body
    assert "/redefinir-senha?token=fixture-token" in body
