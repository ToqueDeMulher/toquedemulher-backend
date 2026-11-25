from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.api.dependencies import AdminUser, _SessionDep
from app.core.db import Database
from app.core.time import utc_now
from app.models.category import Category
from app.models.description import Description
from app.models.product import Product
from app.models.productImage import ProductImage
from app.models.stock import Stock
from app.models.stockMovement import StockMovementType
from app.schemas.product_images import ProductImageResponse
from app.schemas.products import ProductRequest, ProductUpdateRequest
from app.services.catalog_service import public_product, public_products_query
from app.services.service import generate_unique_slug, upload_to_supabase
from app.services.stockMovementService import create_stock_movement
from app.services.stockService import StockService
from app.services.supplierProductService import upsert_supplier_products

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


def admin_product_query():
    return select(Product).options(
        selectinload(Product.images), selectinload(Product.categories),
        selectinload(Product.description), selectinload(Product.stock),
    )


def admin_product(product: Product) -> dict:
    images = sorted(product.images, key=lambda image: (image.order, image.id))
    categories = sorted(product.categories, key=lambda item: item.name)
    return {
        "id": str(product.id), "name": product.name, "slug": product.slug,
        "price": product.price, "active": product.active,
        "status": "published" if product.active else "draft",
        "image": images[0].url if images else "",
        "images": [{"id": image.id, "url": image.url,
                    "alt_text": image.alt_text, "order": image.order,
                    "is_primary": index == 0}
                   for index, image in enumerate(images)],
        "categories": [{"id": category.id, "name": category.name} for category in categories],
        "category_ids": [category.id for category in categories],
        "description": ({"text": product.description.text,
                         "usage_tips": product.description.usage_tips,
                         "ingredients": product.description.ingredients}
                        if product.description else None),
        "stock_quantity": product.stock.total_quantity if product.stock else 0,
    }


def load_admin_product(session: Session, product_id: UUID) -> Product:
    product = session.exec(admin_product_query().where(Product.id == product_id)).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    return product


def replace_categories(session: Session, product: Product, category_ids: list[int]) -> None:
    unique_ids = list(dict.fromkeys(category_ids))
    categories = session.exec(select(Category).where(Category.id.in_(unique_ids))).all() if unique_ids else []
    if len(categories) != len(unique_ids):
        raise HTTPException(status_code=422, detail="Uma ou mais categorias nao existem")
    product.categories = list(categories)


def update_description(session: Session, product: Product, payload) -> None:
    if payload is None:
        return
    if product.description:
        description = product.description
        for field, value in payload.model_dump().items():
            setattr(description, field, value)
    else:
        description = Description(**payload.model_dump())
        session.add(description)
        session.flush()
        product.description_id = description.id
        product.description = description


def validate_publishable(product: Product) -> None:
    missing = []
    if not product.description or not product.description.text.strip():
        missing.append("descricao")
    if not product.categories:
        missing.append("categoria")
    if not product.images:
        missing.append("imagem")
    if not product.stock or product.stock.total_quantity <= 0:
        missing.append("estoque")
    if product.price <= 0:
        missing.append("preco")
    if missing:
        raise HTTPException(status_code=422, detail=f"Complete antes de publicar: {', '.join(missing)}")


@router.get("/admin/categories")
def list_admin_categories(session: _SessionDep, _: AdminUser):
    return session.exec(select(Category).order_by(Category.name)).all()


@router.get("/admin/all")
def list_admin_products(
    session: _SessionDep, _: AdminUser, search: str | None = None,
    status: str | None = None, category_id: int | None = None,
):
    query = admin_product_query().order_by(Product.created_at.desc())
    if search:
        query = query.where(Product.name.ilike(f"%{search.strip()}%"))
    if status == "published":
        query = query.where(Product.active == True)
    elif status == "draft":
        query = query.where(Product.active == False)
    if category_id is not None:
        query = query.where(Product.categories.any(Category.id == category_id))
    return [admin_product(product) for product in session.exec(query).all()]


@router.get("/admin/{product_id}")
def get_admin_product(product_id: UUID, session: _SessionDep, _: AdminUser):
    return admin_product(load_admin_product(session, product_id))


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
            exclude={"supplier_products", "description", "category_ids", "stock_quantity"},
            exclude_none=True,
        )
        product_data["slug"] = slug
        # New products are persisted as drafts. Publication is a separate,
        # validated operation performed after images have been uploaded.
        product_data["active"] = False

        product = Product(**product_data)
        session.add(product)
        session.flush()
        stock = Stock(product_id=product.id, total_quantity=payload.stock_quantity)
        session.add(stock)
        session.flush()
        if payload.stock_quantity:
            create_stock_movement(
                session=session, product_id=product.id, stock_id=stock.id,
                movement_type=StockMovementType.ADJUSTMENT,
                quantity=payload.stock_quantity, reason="Estoque inicial do cadastro administrativo",
            )
        if payload.description:
            update_description(session, product, payload.description)
        replace_categories(session, product, payload.category_ids)

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

    values = payload.model_dump(
        exclude_unset=True, exclude_none=True,
        exclude={"active", "description", "category_ids", "stock_quantity"},
    )
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
    if "description" in payload.model_fields_set:
        update_description(session, product, payload.description)
    if payload.category_ids is not None:
        replace_categories(session, product, payload.category_ids)
    if payload.stock_quantity is not None:
        session.flush()
        StockService.adjust_stock_quantity(product.slug, payload.stock_quantity, session)
    session.flush()
    if payload.active is True:
        refreshed = load_admin_product(session, product.id)
        validate_publishable(refreshed)
        product.active = True
    elif payload.active is False:
        product.active = False
    product.updated_at = utc_now()
    try:
        session.add(product)
        session.commit()
        session.refresh(product)
    except IntegrityError as exc:
        session.rollback()
        logger.exception("Erro de integridade ao atualizar produto: id=%s", product_id)
        raise HTTPException(status_code=400, detail="Dados do produto ja existem") from exc
    return admin_product(load_admin_product(session, product.id))


@router.post("/{product_id}/publish")
def publish_product(product_id: UUID, session: _SessionDep, _: AdminUser):
    product = load_admin_product(session, product_id)
    validate_publishable(product)
    product.active = True
    product.updated_at = utc_now()
    session.add(product)
    session.commit()
    return admin_product(load_admin_product(session, product_id))


@router.post("/{product_id}/unpublish")
def unpublish_product(product_id: UUID, session: _SessionDep, _: AdminUser):
    product = load_admin_product(session, product_id)
    product.active = False
    product.updated_at = utc_now()
    session.add(product)
    session.commit()
    return admin_product(load_admin_product(session, product_id))


@router.post("/{product_id}/images/{image_id}/primary")
def set_primary_image(product_id: UUID, image_id: int, session: _SessionDep, _: AdminUser):
    product = load_admin_product(session, product_id)
    images = sorted(product.images, key=lambda image: (image.order, image.id))
    target = next((image for image in images if image.id == image_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Imagem nao encontrada")
    ordered = [target, *[image for image in images if image.id != image_id]]
    for order, image in enumerate(ordered, start=1):
        image.order = order
        session.add(image)
    session.commit()
    return admin_product(load_admin_product(session, product_id))


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
    file: UploadFile = File(...),  # noqa: B008 - FastAPI dependency declaration
    order: int | None = Form(None, ge=1),
    alt_text: str | None = Form(None),
    session: Session = Depends(Database.get_session),  # noqa: B008 - FastAPI dependency declaration
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
    else:
        existing_images = session.exec(
            select(ProductImage).where(ProductImage.product_id == product_id)
        ).all()
        for existing_image in existing_images:
            if existing_image.order >= order:
                existing_image.order += 1
                session.add(existing_image)

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
