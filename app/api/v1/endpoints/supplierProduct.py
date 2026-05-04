from __future__ import annotations
from fastapi import APIRouter, HTTPException
from sqlmodel import select
from app.models.product import Product
from app.api.dependencies import _SessionDep, AdminUser
from app.schemas.supplier_product import SupplierAndProductRequest, SupplierProductRequest
from app.services.supplierProductService import upsert_supplier_products


router = APIRouter(prefix="/suppliersProducts")


@router.post("")
def create_product(payload: SupplierAndProductRequest, session: _SessionDep, user: AdminUser):
    # Associa 1 forecedor a vários produtos
    
    try:
        updated_products = []

        for item in payload.products_list:
            product = session.exec(select(Product).where(Product.name == item.product_name)).first()

            if not product:
                raise HTTPException(status_code=400,detail=f"Produto '{item.product_name}' não encontrado")

            supplier_product_data = SupplierProductRequest(
                supplier_name=payload.supplier_name,
                supplier_price=item.supplier_price,
                lead_time_days=item.lead_time_days
            )

            upsert_supplier_products(
                data_list=[supplier_product_data],
                product_id=product.id,
                session=session
                )

            updated_products.append(product.name)

        session.commit()

        return {
            "message": f"Fornecedor {payload.supplier_name} associado aos produtos com sucesso",
            "products_updated": updated_products
        }

    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    except HTTPException:
        session.rollback()
        raise

    except Exception as e:
        session.rollback()
        print("Erro ao associar fornecedor aos produtos:", repr(e))
        raise HTTPException(status_code=500,detail="Erro interno ao associar fornecedor aos produtos")