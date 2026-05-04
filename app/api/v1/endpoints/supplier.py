from fastapi import APIRouter, HTTPException, status
from app.models.supplier import Supplier
from app.schemas.suppliers import SupplierRequest
from app.schemas.message import Message
from sqlmodel import select
from app.api.dependencies import addToDB, AdminUser
from app.core.db import _SessionDep

router = APIRouter(prefix="/supplier")

@router.post("/", status_code=201)
def add_to_stock(supplier: SupplierRequest, session: _SessionDep, user: AdminUser)-> Message:
    
    existing_supplier = session.exec(select(Supplier).where(Supplier.email == supplier.email)
                                      ).first() if supplier.email else None
    
    if existing_supplier: 
        raise HTTPException(status_code=400, detail= "Já existe um fornecedor com esse email")

    new_supplier = Supplier(**supplier.model_dump())
    
    addToDB(new_supplier, session)

    return Message(mensagem="Fornecedor criado com sucesso")