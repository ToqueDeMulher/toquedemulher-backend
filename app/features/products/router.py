from __future__ import annotations
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.stock import Stock
from app.models.category import Category
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.brand import Brand
from app.models.description import Description
from app.models.productImage import ProductImage
from app.schemas.create_products import (CreateProductRequest,CreateProductResponse,)
from app.schemas.product_images import ProductImageResponse
from app.features.products.service import generate_unique_slug, upload_to_supabase


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
    payload: CreateProductRequest,
    session: Session = Depends(get_session),
):
    try:
        # 1) SUPPLIER (busca ou cria)
        supplier = session.exec(
            select(Supplier).where(Supplier.name == payload.supplier.name)
        ).first()

        if not supplier:
            supplier = Supplier(
                name=payload.supplier.name,
                contact=payload.supplier.contact,
                email=payload.supplier.email,
            )
            session.add(supplier)
            session.flush()

        # 2) BRAND (busca ou cria)
        brand = session.exec(
            select(Brand).where(Brand.name == payload.brand.name)
        ).first()

        if not brand:
            brand = Brand(name=payload.brand.name)
            session.add(brand)
            session.flush()

        # 3) DESCRIPTION (busca ou cria)
        description = session.exec(
            select(Description).where(Description.text == payload.description.text)
        ).first()

        if not description:
            description = Description(
                text=payload.description.text,
                usage_tips=payload.description.usage_tips,
                ingredients=payload.description.ingredients,
            )
            session.add(description)
            session.flush()

        # 4) CATEGORIES (busca ou cria)
        category_objs: List[Category] = []

        for category_data in payload.categories:
            category = session.exec(
                select(Category).where(Category.name == category_data.name)
            ).first()

            if not category:
                category = Category(name=category_data.name)
                session.add(category)
                session.flush()

            category_objs.append(category)

        # 5) PRODUCT
        product_data = payload.product
        slug = generate_unique_slug(session, product_data.name)

        product = Product(
            slug=slug,
            name=product_data.name,
            price=product_data.price,
            active=product_data.active,
            volume=product_data.volume,
            target_audience=product_data.target_audience,
            product_type=product_data.product_type,
            skin_type=product_data.skin_type,
            hair_type=product_data.hair_type,
            color=product_data.color,
            fragrance=product_data.fragrance,
            spf=product_data.spf,
            vegan=product_data.vegan,
            cruelty_free=product_data.cruelty_free,
            hypoallergenic=product_data.hypoallergenic,
            supplier_id=supplier.id,
            brand_id=brand.id,
            description_id=description.id,
        )
        session.add(product)
        session.flush()

        # 6) vincula categorias
        for category in category_objs:
            if category not in product.categories:
                product.categories.append(category)

        # 7) STOCK
        stock_data = payload.stock
        stock = Stock(
            product_id=product.id,
            quantity=stock_data.quantity,
            expiry_date=stock_data.expiry_date,
            last_quantity=stock_data.quantity,
        )
        session.add(stock)

        # 8) IMAGES
        for image_data in payload.images:
            image = ProductImage(
                product_id=product.id,
                url=image_data.url,
                order=image_data.order,
                alt_text=image_data.alt_text,
            )
            session.add(image)

        # 9) COMMIT
        session.commit()
        session.refresh(product)

        return CreateProductResponse(
            id=product.id,
            slug=product.slug,
            name=product.name,
            supplier_id=supplier.id,
            brand_id=brand.id,
            description_id=description.id,
        )

    except HTTPException:
        raise
    except Exception as exc:
        session.rollback()
        print("Erro ao criar produto:", repr(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {exc}",
        ) from exc


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
    session: Session = Depends(get_session),
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