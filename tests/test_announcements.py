import pytest
from sqlmodel import SQLModel

from tests.test_auth import (
    client,
    create_admin_token,
    create_logged_user,
    engine,
)


@pytest.fixture(autouse=True)
def reset_database():
    SQLModel.metadata.drop_all(bind=engine)
    SQLModel.metadata.create_all(bind=engine)
    yield


def admin_headers():
    return {"Authorization": f"Bearer {create_admin_token()}"}


def draft_payload(*messages):
    return {
        "messages": [
            {
                "text": message[0],
                "destination": message[1],
                "active": message[2],
                "sort_order": index,
            }
            for index, message in enumerate(messages, start=1)
        ]
    }


def test_public_endpoint_preserves_current_message_before_first_publication():
    response = client.get("/api/v1/announcements")

    assert response.status_code == 200
    assert response.json() == {
        "source": "fallback",
        "messages": [
            {
                "id": "fallback-delivery",
                "text": "Calcule a entrega pelo seu CEP",
                "destination": "/carrinho",
                "sort_order": 1,
            }
        ],
    }


def test_admin_endpoints_require_an_administrator():
    assert client.get("/api/v1/announcements/admin/draft").status_code == 401

    customer_token = create_logged_user()
    response = client.get(
        "/api/v1/announcements/admin/draft",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert response.status_code == 403


def test_draft_can_be_created_edited_ordered_and_previewed_without_publication():
    headers = admin_headers()
    initial = client.get("/api/v1/announcements/admin/draft", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["messages"][0]["text"] == "Calcule a entrega pelo seu CEP"

    saved = client.put(
        "/api/v1/announcements/admin/draft",
        headers=headers,
        json=draft_payload(
            ("Frete grátis acima de R$ 199", "/busca?q=frete", True),
            ("Conheça o Beauty Club", "/missoes", False),
        ),
    )
    assert saved.status_code == 200
    assert [item["text"] for item in saved.json()["messages"]] == [
        "Frete grátis acima de R$ 199",
        "Conheça o Beauty Club",
    ]
    assert saved.json()["messages"][1]["active"] is False

    # Saving a private draft must never change what shoppers receive.
    public = client.get("/api/v1/announcements").json()
    assert public["source"] == "fallback"
    assert public["messages"][0]["text"] == "Calcule a entrega pelo seu CEP"


def test_publish_is_explicit_and_future_edits_remain_private():
    headers = admin_headers()
    first_draft = draft_payload(
        ("Primeiro aviso", "/ajuda", True),
        ("Aviso desativado", "/sobre", False),
    )
    assert client.put(
        "/api/v1/announcements/admin/draft", headers=headers, json=first_draft
    ).status_code == 200

    published = client.post("/api/v1/announcements/admin/publish", headers=headers)
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert client.get("/api/v1/announcements").json()["messages"] == [
        {
            "id": published.json()["messages"][0]["id"],
            "text": "Primeiro aviso",
            "destination": "/ajuda",
            "sort_order": 1,
        }
    ]

    assert client.put(
        "/api/v1/announcements/admin/draft",
        headers=headers,
        json=draft_payload(("Mudança ainda privada", "/carrinho", True)),
    ).status_code == 200
    assert client.get("/api/v1/announcements").json()["messages"][0]["text"] == "Primeiro aviso"


def test_published_empty_or_inactive_content_intentionally_hides_bar():
    headers = admin_headers()
    assert client.put(
        "/api/v1/announcements/admin/draft",
        headers=headers,
        json=draft_payload(("Pausado", "/ajuda", False)),
    ).status_code == 200
    assert client.post(
        "/api/v1/announcements/admin/publish", headers=headers
    ).status_code == 200

    assert client.get("/api/v1/announcements").json() == {
        "source": "published",
        "messages": [],
    }


def test_discard_restores_the_last_published_revision():
    headers = admin_headers()
    client.put(
        "/api/v1/announcements/admin/draft",
        headers=headers,
        json=draft_payload(("Conteúdo publicado", "/sobre", True)),
    )
    client.post("/api/v1/announcements/admin/publish", headers=headers)
    client.put(
        "/api/v1/announcements/admin/draft",
        headers=headers,
        json=draft_payload(("Alteração descartável", "/ajuda", True)),
    )

    discarded = client.post("/api/v1/announcements/admin/discard", headers=headers)
    assert discarded.status_code == 200
    assert discarded.json()["messages"][0]["text"] == "Conteúdo publicado"


@pytest.mark.parametrize(
    "message",
    [
        ("", "/ajuda", True),
        ("Link externo", "https://example.com", True),
        ("URL relativa insegura", "//example.com", True),
    ],
)
def test_draft_rejects_invalid_or_unsafe_content(message):
    response = client.put(
        "/api/v1/announcements/admin/draft",
        headers=admin_headers(),
        json=draft_payload(message),
    )
    assert response.status_code == 422


def test_draft_rejects_duplicate_or_non_sequential_positions():
    response = client.put(
        "/api/v1/announcements/admin/draft",
        headers=admin_headers(),
        json={
            "messages": [
                {"text": "A", "destination": "/a", "active": True, "sort_order": 1},
                {"text": "B", "destination": "/b", "active": True, "sort_order": 1},
            ]
        },
    )
    assert response.status_code == 422
