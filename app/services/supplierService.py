from app.api.dependencies import _SessionDep
from sqlmodel import select
from app.models.supplier import Supplier
from fastapi import HTTPException


class SupplierService():
    
    @staticmethod
    def find_supplier_by_name(session: _SessionDep, name: str):

        supplier = session.exec(select(Supplier).where(Supplier.name == name)).first()
        if not supplier:
            raise HTTPException(status_code=404,detail="Fornecedor não encontrado")
        
        return supplier