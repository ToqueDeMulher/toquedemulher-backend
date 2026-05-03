from __future__ import annotations
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select
from app.core.db import Database
from app.models.product import Product
from app.models.productImage import ProductImage
from app.schemas.create_products import CreateProductResponse
from app.schemas.product_images import ProductImageResponse
from app.services.service import upload_to_supabase
from app.api.dependencies import _SessionDep
from app.schemas.products import ProductRequest
from app.services.supplierProductService import upsert_supplier_products


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
    payload: ProductRequest,
    session: _SessionDep
):
    try:
        # 🔎 verifica slug duplicado
        existing = session.exec(
            select(Product).where(Product.slug == payload.slug)
        ).first()

        if existing:
            raise HTTPException(400, "Slug já existe")

        # cria produto
        product_data = payload.model_dump(exclude={"supplier_products"})
        product = Product(**product_data)

        session.add(product)
        session.flush()

        # trata lista de fornecedores
        if payload.supplier_products:
            upsert_supplier_products(
                data_list=payload.supplier_products,
                product_id=product.id,
                session=session
            )

        session.commit()
        session.refresh(product)

        return f"Produto {product.name} criado com sucesso"

    except ValueError as e:
        session.rollback()
        raise HTTPException(400, str(e))

    except HTTPException:
        raise

    except Exception as e:
        session.rollback()
        print("Erro ao criar produto:", repr(e))
        raise HTTPException(500, "Erro interno ao criar produto")



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