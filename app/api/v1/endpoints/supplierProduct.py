from __future__ import annotations
from fastapi import APIRouter, HTTPException
from sqlmodel import select
from app.models.product import Product
from app.schemas.create_products import CreateProductResponse
from app.api.dependencies import _SessionDep
from app.schemas.supplier_product import SupplierAndProductRequest
from app.services.supplierProductService import upsert_supplier_products


router = APIRouter(
    prefix="/suppliersProducts"
)

@router.post("", response_model=CreateProductResponse)
def create_product(payload: SupplierAndProductRequest, session: _SessionDep):
    # Associa fornecedores a produtos em lote
    try:
        updated_products = []

        for product_name in payload.products_list:

            product = session.exec(
                select(Product).where(Product.name == product_name)).first()

            if not product:
                raise HTTPException(status_code=400, detail=f"Produto '{product_name}' não encontrado")

            upsert_supplier_products(
                data_list=payload.supplier,
                product_id=product.id,
                session=session
            )

            updated_products.append(product.name)

        session.commit()

        return {
            "message": "Fornecedores associados com sucesso",
            "products_updated": updated_products
        }


    except ValueError as e:
        session.rollback()
        raise HTTPException(400, str(e))

    except HTTPException:
        raise

    except Exception as e:
        session.rollback()
        print("Erro ao criar produto:", repr(e))
        raise HTTPException(500, "Erro interno ao criar produto")
