from uuid import UUID

from fastapi import APIRouter
from sqlmodel import Session, select

from app.api.dependencies import AdminUser
from app.core.db import _SessionDep
from app.core.time import utc_now
from app.models.announcement import AnnouncementMessage, AnnouncementRevision
from app.schemas.announcements import (
    FALLBACK_ANNOUNCEMENT_DESTINATION,
    FALLBACK_ANNOUNCEMENT_TEXT,
    AnnouncementDraftUpdate,
    AnnouncementMessageResponse,
    AnnouncementRevisionResponse,
    PublicAnnouncementMessage,
    PublicAnnouncementsResponse,
)

router = APIRouter(prefix="/announcements", tags=["store content"])


def _revision(session: Session, status: str) -> AnnouncementRevision | None:
    return session.exec(
        select(AnnouncementRevision)
        .where(AnnouncementRevision.status == status)
        .order_by(AnnouncementRevision.created_at.desc())
    ).first()


def _messages(session: Session, revision_id: UUID) -> list[AnnouncementMessage]:
    return list(
        session.exec(
            select(AnnouncementMessage)
            .where(AnnouncementMessage.revision_id == revision_id)
            .order_by(AnnouncementMessage.sort_order, AnnouncementMessage.id)
        ).all()
    )


def _fallback_input() -> dict:
    return {
        "text": FALLBACK_ANNOUNCEMENT_TEXT,
        "destination": FALLBACK_ANNOUNCEMENT_DESTINATION,
        "active": True,
        "sort_order": 1,
    }


def _new_draft(session: Session) -> AnnouncementRevision:
    draft = AnnouncementRevision(status="draft")
    session.add(draft)
    session.flush()

    published = _revision(session, "published")
    source_messages = _messages(session, published.id) if published else None
    values = [
        {
            "text": message.text,
            "destination": message.destination,
            "active": message.active,
            "sort_order": message.sort_order,
        }
        for message in (source_messages or [])
    ]
    if source_messages is None:
        values = [_fallback_input()]
    session.add_all(
        AnnouncementMessage(revision_id=draft.id, **value) for value in values
    )
    return draft


def _draft(session: Session) -> AnnouncementRevision:
    return _revision(session, "draft") or _new_draft(session)


def _revision_response(
    session: Session, revision: AnnouncementRevision
) -> AnnouncementRevisionResponse:
    return AnnouncementRevisionResponse(
        id=revision.id,
        status=revision.status,
        updated_at=revision.updated_at,
        published_at=revision.published_at,
        messages=[
            AnnouncementMessageResponse.model_validate(message, from_attributes=True)
            for message in _messages(session, revision.id)
        ],
    )


@router.get("", response_model=PublicAnnouncementsResponse)
def get_public_announcements(session: _SessionDep):
    published = _revision(session, "published")
    if published is None:
        return PublicAnnouncementsResponse(
            source="fallback",
            messages=[
                PublicAnnouncementMessage(
                    id="fallback-delivery",
                    text=FALLBACK_ANNOUNCEMENT_TEXT,
                    destination=FALLBACK_ANNOUNCEMENT_DESTINATION,
                    sort_order=1,
                )
            ],
        )

    messages = [message for message in _messages(session, published.id) if message.active]
    return PublicAnnouncementsResponse(
        source="published",
        messages=[
            PublicAnnouncementMessage(
                id=str(message.id),
                text=message.text,
                destination=message.destination,
                sort_order=message.sort_order,
            )
            for message in messages
        ],
    )


@router.get("/admin/draft", response_model=AnnouncementRevisionResponse)
def get_announcement_draft(session: _SessionDep, _: AdminUser):
    draft = _draft(session)
    session.commit()
    session.refresh(draft)
    return _revision_response(session, draft)


@router.put("/admin/draft", response_model=AnnouncementRevisionResponse)
def save_announcement_draft(
    payload: AnnouncementDraftUpdate, session: _SessionDep, _: AdminUser
):
    draft = _draft(session)
    for message in _messages(session, draft.id):
        session.delete(message)
    session.flush()
    session.add_all(
        AnnouncementMessage(revision_id=draft.id, **message.model_dump())
        for message in payload.messages
    )
    draft.updated_at = utc_now()
    session.add(draft)
    session.commit()
    session.refresh(draft)
    return _revision_response(session, draft)


@router.post("/admin/discard", response_model=AnnouncementRevisionResponse)
def discard_announcement_draft(session: _SessionDep, _: AdminUser):
    current_draft = _revision(session, "draft")
    if current_draft:
        for message in _messages(session, current_draft.id):
            session.delete(message)
        session.delete(current_draft)
        session.flush()
    draft = _new_draft(session)
    session.commit()
    session.refresh(draft)
    return _revision_response(session, draft)


@router.post("/admin/publish", response_model=AnnouncementRevisionResponse)
def publish_announcement_draft(session: _SessionDep, _: AdminUser):
    draft = _draft(session)
    now = utc_now()
    published = _revision(session, "published")
    if published:
        published.status = "archived"
        published.updated_at = now
        session.add(published)
        session.flush()

    draft.status = "published"
    draft.updated_at = now
    draft.published_at = now
    session.add(draft)
    session.flush()
    response = _revision_response(session, draft)
    _new_draft(session)
    session.commit()
    return response

