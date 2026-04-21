from __future__ import annotations
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select
from app.core.db import Database
from app.models.stock import Stock
from app.models.category import Category
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.brand import Brand
from app.models.description import Description
from app.models.productImage import ProductImage
from app.schemas.create_products import (CreateProductRequest,CreateProductResponse,)
from app.schemas.product_images import ProductImageResponse
from app.services.service import generate_unique_slug, upload_to_supabase
from app.api.dependencies import _SessionDep
from app.schemas.products import ProductRequest


router = APIRouter(
    prefix="/products",
    tags=["products"],
)

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


@router.post("", response_model=CreateProductResponse)
def create_product(
    payload: ProductRequest,
    session: _SessionDep
):
    try:
        # 🔎 verifica slug duplicado
        existing = session.exec(
            select(Product).where(Product.slug == payload.slug)
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail="Slug já existe"
            )

        # 🧱 cria produto
        product = Product(**payload.model_dump())

        session.add(product)
        session.commit()
        session.refresh(product)

        return product

    except Exception as e:
        session.rollback()
        print("Erro ao criar produto:", repr(e))

    raise HTTPException(
        status_code=500,
        detail="Erro interno ao criar produto"
    )

@router.post(
    "/{product_id}/images/upload",
    response_model=ProductImageResponse,
    responses={
        400: {"description": "Formato de imagem inválido."},
        404: {"description": "Produto não encontrado."},
        413: {"description": "Arquivo maior que o limite configurado."},
        500: {"description": "Falha ao persistir a imagem."},
    },
)
async def upload_product_image(
    product_id: UUID,
    file: UploadFile = File(...),
    order: Optional[int] = Form(None),
    alt_text: Optional[str] = Form(None),
    session: Session = Depends(Database.get_session),
):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado.")

    extension = ALLOWED_IMAGE_TYPES.get(file.content_type or "")
    if not extension:
        raise HTTPException(
            status_code=400,
            detail="Formato de imagem invalido. Use JPG, PNG ou WEBP.",
        )

    if order is None:
        last_order = session.exec(
            select(ProductImage.order)
            .where(ProductImage.product_id == product_id)
            .order_by(ProductImage.order.desc())
        ).first()
        order = (last_order or 0) + 1

    url = await upload_to_supabase(
        product_id=product_id,
        file=file,
        extension=extension,
    )

    image = ProductImage(
        product_id=product_id,
        url=url,
        order=order,
        alt_text=alt_text,
    )

    try:
        session.add(image)
        session.commit()
        session.refresh(image)
    except Exception as exc:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {exc}",
        ) from exc

    return ProductImageResponse(
        id=image.id,
        url=image.url,
        order=image.order,
        alt_text=image.alt_text,
    )