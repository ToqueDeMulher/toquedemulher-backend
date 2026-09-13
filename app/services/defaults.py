from uuid import UUID

from sqlmodel import Session, select

from app.models.user import UserInDB


def lock_user_defaults(session: Session, user_id: UUID) -> None:
    """Serialize default changes for a user before reading or updating defaults."""
    session.exec(select(UserInDB).where(UserInDB.id == user_id).with_for_update()).one()
