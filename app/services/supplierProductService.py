
from uuid import UUID
from app.models.supplier import Supplier
from app.models.supplier_product import SupplierProduct
from sqlmodel import select
from app.schemas.supplier_product import SupplierProductRequest
from app.api.dependencies import _SessionDep

from typing import List

# Cria um Supplier_product, caso não exista, e adicina ao BD
def upsert_supplier_products(data_list: List[SupplierProductRequest], product_id: UUID, session: _SessionDep):

    for data in data_list:

        supplier = session.exec(
            select(Supplier).where(Supplier.name == data.supplier_name)
        ).first()

        if not supplier:
            raise ValueError(f"Fornecedor '{data.supplier_name}' não existe")

        relation = session.exec(
            select(SupplierProduct).where(
                SupplierProduct.product_id == product_id,
                SupplierProduct.supplier_id == supplier.id
            )
        ).first()

        if not relation:
            relation = SupplierProduct(
                product_id=product_id,
                supplier_id=supplier.id,
                supplier_price=data.supplier_price,
                lead_time_days=data.lead_time_days
            )
            session.add(relation)
        else:
            relation.supplier_price = data.supplier_price
            relation.lead_time_days = data.lead_time_days