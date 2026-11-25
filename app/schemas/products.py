from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.supplier_product import SupplierProductRequest


class ProductDescriptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=10000)
    usage_tips: str | None = Field(default=None, max_length=5000)
    ingredients: str | None = Field(default=None, max_length=5000)

    @field_validator("text", "usage_tips", "ingredients")
    @classmethod
    def trim_text(cls, value: str | None):
        return value.strip() if value is not None else value


class ProductRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)

    slug: str | None = None
    name: str = Field(min_length=1, max_length=255)
    price: float = Field(ge=0)
    active: bool = True
    volume: str | None = None
    shipping_width: float | None = Field(default=None, gt=0, le=300)
    shipping_height: float | None = Field(default=None, gt=0, le=300)
    shipping_length: float | None = Field(default=None, gt=0, le=300)
    shipping_weight: float | None = Field(default=None, gt=0, le=1000)

    target_audience: str | None = None
    product_type: str | None = None
    skin_type: str | None = None
    hair_type: str | None = None
    color: str | None = None
    fragrance: str | None = None
    spf: int | None = None

    vegan: bool = False
    cruelty_free: bool = False
    hypoallergenic: bool = False

    brand_id: int | None = None
    description_id: int | None = None
    description: ProductDescriptionRequest | None = None
    category_ids: list[int] = Field(default_factory=list)
    stock_quantity: int = Field(default=0, ge=0)
    supplier_products: list[SupplierProductRequest] | None = None

    @field_validator("name", "slug")
    @classmethod
    def trim_required_text(cls, value: str | None):
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("O campo nao pode estar vazio")
        return value


class ProductUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)

    slug: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    price: float | None = Field(default=None, ge=0)
    active: bool | None = None
    description: ProductDescriptionRequest | None = None
    category_ids: list[int] | None = None
    stock_quantity: int | None = Field(default=None, ge=0)

    @field_validator("name", "slug")
    @classmethod
    def trim_optional_text(cls, value: str | None):
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("O campo nao pode estar vazio")
        return value


class ProductResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    price: float
