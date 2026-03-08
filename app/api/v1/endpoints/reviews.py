from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import os, uuid, shutil

from app.db.base import get_db
from app.models.user import User
from app.models.product import Product
from app.models.order import Order, OrderItem, OrderStatus
from app.models.review import Review, ReviewImage
from app.schemas.review import ReviewCreate, ReviewUpdate, ReviewOut, ProductReviewSummary
from app.api.v1.deps import get_current_active_user, get_current_admin
from app.core.config import settings

router = APIRouter(prefix="/reviews", tags=["Avaliações"])


def _update_product_rating(product: Product, db: Session):
    """Recalcula e atualiza a nota média e contagem de avaliações do produto."""
    result = db.query(
        func.avg(Review.rating).label("avg"),
        func.count(Review.id).label("count"),
    ).filter(
        Review.product_id == product.id,
        Review.is_approved == True,
    ).first()

    product.average_rating = round(float(result.avg or 0), 1)
    product.review_count = result.count or 0


@router.get("/product/{product_id}", response_model=ProductReviewSummary)
def get_product_reviews(
    product_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Retorna as avaliações de um produto com resumo estatístico."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")

    reviews_query = db.query(Review).filter(
        Review.product_id == product_id,
        Review.is_approved == True,
    ).order_by(Review.created_at.desc())

    total = reviews_query.count()
    reviews = reviews_query.offset((page - 1) * page_size).limit(page_size).all()

    # Distribuição de notas
    distribution = {i: 0 for i in range(1, 6)}
    all_ratings = db.query(Review.rating).filter(
        Review.product_id == product_id, Review.is_approved == True
    ).all()
    for (r,) in all_ratings:
        distribution[r] = distribution.get(r, 0) + 1

    return ProductReviewSummary(
        average_rating=product.average_rating,
        review_count=product.review_count,
        rating_distribution=distribution,
        reviews=reviews,
    )


@router.post("/", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def create_review(
    review_in: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Cria uma avaliação para um produto."""
    # Verificar produto
    product = db.query(Product).filter(Product.id == review_in.product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")

    # Verificar se já avaliou
    existing = db.query(Review).filter(
        Review.user_id == current_user.id,
        Review.product_id == review_in.product_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Você já avaliou este produto.",
        )

    # Verificar se é compra verificada
    is_verified = False
    if review_in.order_id:
        order = db.query(Order).filter(
            Order.id == review_in.order_id,
            Order.user_id == current_user.id,
            Order.status == OrderStatus.delivered,
        ).first()
        if order:
            item = db.query(OrderItem).filter(
                OrderItem.order_id == order.id,
                OrderItem.product_id == review_in.product_id,
            ).first()
            is_verified = item is not None

    review = Review(
        user_id=current_user.id,
        product_id=review_in.product_id,
        order_id=review_in.order_id,
        rating=review_in.rating,
        title=review_in.title,
        body=review_in.body,
        is_verified_purchase=is_verified,
    )
    db.add(review)
    db.flush()

    # Atualizar média do produto
    _update_product_rating(product, db)

    db.commit()
    db.refresh(review)
    return review


@router.post("/{review_id}/images", response_model=ReviewOut)
async def upload_review_image(
    review_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Adiciona uma imagem a uma avaliação."""
    review = db.query(Review).filter(
        Review.id == review_id, Review.user_id == current_user.id
    ).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avaliação não encontrada.")

    if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Formato inválido.")

    upload_dir = os.path.join(settings.UPLOAD_DIR, "reviews", str(review_id))
    os.makedirs(upload_dir, exist_ok=True)

    ext = file.filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    image = ReviewImage(
        review_id=review_id,
        url=f"/uploads/reviews/{review_id}/{filename}",
    )
    db.add(image)
    db.commit()
    db.refresh(review)
    return review


@router.put("/{review_id}", response_model=ReviewOut)
def update_review(
    review_id: int,
    review_update: ReviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Atualiza uma avaliação do usuário."""
    review = db.query(Review).filter(
        Review.id == review_id, Review.user_id == current_user.id
    ).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avaliação não encontrada.")

    for field, value in review_update.model_dump(exclude_unset=True).items():
        setattr(review, field, value)

    product = db.query(Product).filter(Product.id == review.product_id).first()
    _update_product_rating(product, db)

    db.commit()
    db.refresh(review)
    return review


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Remove uma avaliação do usuário."""
    review = db.query(Review).filter(
        Review.id == review_id, Review.user_id == current_user.id
    ).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avaliação não encontrada.")

    product = db.query(Product).filter(Product.id == review.product_id).first()
    db.delete(review)
    _update_product_rating(product, db)
    db.commit()


@router.post("/{review_id}/helpful", status_code=status.HTTP_200_OK)
def mark_helpful(
    review_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """Marca uma avaliação como útil."""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avaliação não encontrada.")
    review.helpful_count += 1
    db.commit()
    return {"helpful_count": review.helpful_count}


# ─── Moderação (Admin) ────────────────────────────────────────────────────────

@router.put("/admin/{review_id}/approve", response_model=ReviewOut)
def approve_review(
    review_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """[Admin] Aprova ou desaprova uma avaliação."""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avaliação não encontrada.")
    review.is_approved = not review.is_approved
    product = db.query(Product).filter(Product.id == review.product_id).first()
    _update_product_rating(product, db)
    db.commit()
    db.refresh(review)
    return review
