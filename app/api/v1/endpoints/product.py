from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.api.dependencies import AdminUser, _SessionDep
from app.core.db import Database
from app.core.time import utc_now
from app.models.product import Product
from app.models.productImage import ProductImage
from app.models.stock import Stock
from app.schemas.product_images import ProductImageResponse
from app.schemas.products import ProductRequest, ProductUpdateRequest
from app.services.service import generate_unique_slug, upload_to_supabase
from app.services.supplierProductService import upsert_supplier_products
from app.services.catalog_service import public_product, public_products_query


router = APIRouter(
    prefix="/products",
    tags=["products"],
)

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


@router.get("")
def list_active_products(session: _SessionDep, response: Response):
    """Return the public catalog without requiring an authenticated session."""
    response.headers["Cache-Control"] = "no-store"
    return [public_product(product) for product in session.exec(public_products_query()).all()]


@router.get("/admin/all")
def list_admin_products(session: _SessionDep, _: AdminUser):
    products = session.exec(select(Product).order_by(Product.created_at.desc())).all()
    images = session.exec(
        select(ProductImage).order_by(ProductImage.product_id, ProductImage.order)
    ).all()
    image_by_product = {}
    for image in images:
        image_by_product.setdefault(image.product_id, image.url)

    return [
        {
            "id": str(product.id),
            "name": product.name,
            "slug": product.slug,
            "price": product.price,
            "active": product.active,
            "image": image_by_product.get(product.id, ""),
        }
        for product in products
    ]


@router.get("/{product_id}")
def get_product(product_id: UUID, session: _SessionDep, response: Response):
    product = session.exec(public_products_query().where(Product.id == product_id)).first()
    if not product or not product.active:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    response.headers["Cache-Control"] = "no-store"
    return public_product(product)


@router.post("")
def create_product(payload: ProductRequest, session: _SessionDep, user: AdminUser):
    try:
        existing_name = session.exec(
            select(Product).where(Product.name == payload.name)
        ).first()
        if existing_name:
            raise HTTPException(status_code=400, detail="Nome do produto ja existe")

        slug = payload.slug or generate_unique_slug(session, payload.name)

        existing = session.exec(select(Product).where(Product.slug == slug)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Slug ja existe")

        product_data = payload.model_dump(
            exclude={"supplier_products"},
            exclude_none=True,
        )
        product_data["slug"] = slug

        product = Product(**product_data)
        session.add(product)
        session.flush()
        session.add(Stock(product_id=product.id, total_quantity=0))

        if payload.supplier_products:
            upsert_supplier_products(
                data_list=payload.supplier_products,
                product_id=product.id,
                session=session,
            )

        session.commit()
        session.refresh(product)

        return {
            "message": f"Produto {product.name} criado com sucesso",
            "id": str(product.id),
            "slug": product.slug,
            "name": product.name,
        }
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        session.rollback()
        raise
    except IntegrityError as exc:
        session.rollback()
        logger.exception("Erro de integridade ao criar produto: name=%s", payload.name)
        raise HTTPException(
            status_code=400,
            detail="Nome ou identificador do produto ja existe",
        ) from exc
    except Exception as exc:
        session.rollback()
        logger.exception("Erro interno ao criar produto: name=%s", payload.name)
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao criar produto",
        ) from exc


@router.patch("/{product_id}")
def update_product(
    product_id: UUID,
    payload: ProductUpdateRequest,
    session: _SessionDep,
    _: AdminUser,
):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")

    values = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "name" in values and values["name"] != product.name:
        existing = session.exec(select(Product).where(Product.name == values["name"])).first()
        if existing and existing.id != product.id:
            raise HTTPException(status_code=400, detail="Nome do produto ja existe")
        if "slug" not in values:
            values["slug"] = generate_unique_slug(session, values["name"])
    if "slug" in values:
        existing = session.exec(select(Product).where(Product.slug == values["slug"])).first()
        if existing and existing.id != product.id:
            raise HTTPException(status_code=400, detail="Slug ja existe")

    for field, value in values.items():
        setattr(product, field, value)
    product.updated_at = utc_now()
    try:
        session.add(product)
        session.commit()
        session.refresh(product)
    except IntegrityError as exc:
        session.rollback()
        logger.exception("Erro de integridade ao atualizar produto: id=%s", product_id)
        raise HTTPException(status_code=400, detail="Dados do produto ja existem") from exc
    return {"id": str(product.id), "name": product.name, "price": product.price, "active": product.active}


@router.delete("/{product_id}")
def delete_product(product_id: UUID, session: _SessionDep, _: AdminUser):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    try:
        images = session.exec(
            select(ProductImage).where(ProductImage.product_id == product.id)
        ).all()
        for image in images:
            session.delete(image)
        session.delete(product)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Este produto possui movimentacoes e nao pode ser excluido. Desative-o em vez disso.",
        ) from exc
    return {"message": "Produto excluido com sucesso"}


@router.post(
    "/{product_id}/images",
    response_model=ProductImageResponse,
    responses={
        400: {"description": "Formato de imagem invalido."},
        404: {"description": "Produto nao encontrado."},
        413: {"description": "Arquivo maior que o limite configurado."},
        500: {"description": "Falha ao persistir a imagem."},
    },
)
@router.post(
    "/{product_id}/images/upload",
    response_model=ProductImageResponse,
    responses={
        400: {"description": "Formato de imagem invalido."},
        404: {"description": "Produto nao encontrado."},
        413: {"description": "Arquivo maior que o limite configurado."},
        500: {"description": "Falha ao persistir a imagem."},
    },
)
async def upload_product_image(
    product_id: UUID,
    _admin: AdminUser,
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
            detail="Erro interno ao salvar imagem.",
        ) from exc

    return ProductImageResponse(
        id=image.id,
        url=image.url,
        alt_text=image.alt_text,
        order=image.order,
        sort_order=image.order,
        is_primary=image.order == 1,
    )
