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


from app.features.products.schemas import (
    CreateProductPayload,
    ProductImageResponse,
)
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


@router.post("")
def create_product(
    payload: CreateProductPayload,
    session: Session = Depends(get_session),
):
    try:
        # 1) SUPPLIER (pega ou cria)
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
            session.flush()  # gera supplier.id

        # 2) BRAND (pega ou cria)
        brand = session.exec(select(Brand).where(Brand.name == payload.brand.name)).first()

        if not brand:
            brand = Brand(name=payload.brand.name)
            session.add(brand)
            session.flush()  # gera brand.id

        # 3) DESCRIPTION (pega ou cria)
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
            session.flush()  # gera description.id

        # 4) CATEGORIES (pega ou cria)
        category_objs: List[Category] = []
        for cat_data in payload.categories:
            cat = session.exec(select(Category).where(Category.name == cat_data.name)).first()
            if not cat:
                cat = Category(name=cat_data.name)
                session.add(cat)
                session.flush()
            category_objs.append(cat)

        # 5) PRODUCT
        p = payload.product
        slug = generate_unique_slug(session, p.name)

        product = Product(
            slug=slug,
            name=p.name,
            price=p.price,
            active=p.active,
            volume=p.volume,
            target_audience=p.target_audience,
            product_type=p.product_type,
            skin_type=p.skin_type,
            hair_type=p.hair_type,
            color=p.color,
            fragrance=p.fragrance,
            spf=p.spf,
            vegan=p.vegan,
            cruelty_free=p.cruelty_free,
            hypoallergenic=p.hypoallergenic,
            supplier_id=supplier.id,
            brand_id=brand.id,
            description_id=description.id,
        )
        session.add(product)
        session.flush()  # gera product.id

        # vincula categorias pelo relacionamento
        for cat in category_objs:
            if cat not in product.categories:
                product.categories.append(cat)

        # 6) STOCK
        s = payload.stock
        stock = Stock(
            product_id=product.id,
            quantity=s.quantity,
            expiry_date=s.expiry_date,
            last_quantity=s.quantity,
        )
        session.add(stock)

        # 7) IMAGENS
        for img in payload.images:
            session.add(
                ProductImage(
                    product_id=product.id,
                    url=img.url,
                    order=img.order,
                    alt_text=img.alt_text,
                )
            )

        # 8) COMMIT
        session.commit()
        session.refresh(product)

        return {
            "id": product.id,
            "slug": product.slug,
            "name": product.name,
            "supplier_id": supplier.id,
            "brand_id": brand.id,
            "description_id": description.id,
        }

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        print("Erro ao criar produto:", repr(e))
        raise HTTPException(status_code=500, detail=f"Erro interno: {e}")


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
        raise HTTPException(status_code=500, detail=f"Erro interno: {exc}") from exc

    return ProductImageResponse(
        id=image.id,
        url=image.url,
        order=image.order,
        alt_text=image.alt_text,
    )
