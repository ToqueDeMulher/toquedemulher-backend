from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, String
from sqlmodel import Field, SQLModel

from app.core.time import utc_now


class AnnouncementRevision(SQLModel, table=True):
    __tablename__ = "announcement_revision"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_announcement_revision_status",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    status: str = Field(
        default="draft",
        sa_column=Column(String(16), nullable=False, index=True),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    published_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class AnnouncementMessage(SQLModel, table=True):
    __tablename__ = "announcement_message"
    __table_args__ = (
        CheckConstraint(
            "length(trim(text)) BETWEEN 1 AND 160",
            name="ck_announcement_message_text",
        ),
        CheckConstraint(
            "sort_order >= 1",
            name="ck_announcement_message_sort_order",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    revision_id: UUID = Field(foreign_key="announcement_revision.id", index=True)
    text: str = Field(max_length=160)
    destination: str = Field(max_length=500)
    active: bool = Field(default=True, nullable=False)
    sort_order: int = Field(ge=1)

