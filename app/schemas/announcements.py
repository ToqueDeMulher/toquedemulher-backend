from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FALLBACK_ANNOUNCEMENT_TEXT = "Calcule a entrega pelo seu CEP"
FALLBACK_ANNOUNCEMENT_DESTINATION = "/carrinho"


def validate_internal_destination(value: str) -> str:
    destination = value.strip()
    parsed = urlsplit(destination)
    if (
        not destination.startswith("/")
        or destination.startswith("//")
        or parsed.scheme
        or parsed.netloc
        or "\\" in destination
        or any(ord(character) < 32 for character in destination)
    ):
        raise ValueError("O destino deve ser um caminho interno seguro iniciado por /")
    return destination


class AnnouncementMessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=160)
    destination: str = Field(min_length=1, max_length=500)
    active: bool = True
    sort_order: int = Field(ge=1)

    @field_validator("text")
    @classmethod
    def trim_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A mensagem não pode estar vazia")
        return value

    @field_validator("destination")
    @classmethod
    def safe_destination(cls, value: str) -> str:
        return validate_internal_destination(value)


class AnnouncementDraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[AnnouncementMessageInput] = Field(max_length=20)

    @model_validator(mode="after")
    def unique_order(self):
        orders = [message.sort_order for message in self.messages]
        if len(orders) != len(set(orders)):
            raise ValueError("Cada mensagem deve ter uma posição diferente")
        if sorted(orders) != list(range(1, len(orders) + 1)):
            raise ValueError("As posições devem ser sequenciais, começando em 1")
        return self


class AnnouncementMessageResponse(BaseModel):
    id: UUID
    text: str
    destination: str
    active: bool
    sort_order: int


class AnnouncementRevisionResponse(BaseModel):
    id: UUID
    status: str
    updated_at: datetime
    published_at: datetime | None
    messages: list[AnnouncementMessageResponse]


class PublicAnnouncementMessage(BaseModel):
    id: str
    text: str
    destination: str
    sort_order: int


class PublicAnnouncementsResponse(BaseModel):
    source: str
    messages: list[PublicAnnouncementMessage]

