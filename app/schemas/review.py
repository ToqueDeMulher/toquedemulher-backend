from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime


class ReviewCreate(BaseModel):
    product_id: int
    order_id: Optional[int] = None
    rating: int
    title: Optional[str] = None
    body: Optional[str] = None

    @field_validator("rating")
    @classmethod
    def rating_range(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("A avaliação deve ser entre 1 e 5.")
        return v


class ReviewUpdate(BaseModel):
    rating: Optional[int] = None
    title: Optional[str] = None
    body: Optional[str] = None

    @field_validator("rating")
    @classmethod
    def rating_range(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not 1 <= v <= 5:
            raise ValueError("A avaliação deve ser entre 1 e 5.")
        return v


class ReviewImageOut(BaseModel):
    id: int
    url: str

    class Config:
        from_attributes = True


class ReviewUserOut(BaseModel):
    id: int
    full_name: str
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class ReviewOut(BaseModel):
    id: int
    user_id: int
    product_id: int
    rating: int
    title: Optional[str] = None
    body: Optional[str] = None
    is_verified_purchase: bool
    helpful_count: int
    images: List[ReviewImageOut] = []
    user: Optional[ReviewUserOut] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProductReviewSummary(BaseModel):
    average_rating: float
    review_count: int
    rating_distribution: dict  # {1: 0, 2: 1, 3: 2, 4: 5, 5: 10}
    reviews: List[ReviewOut]
