from fastapi import APIRouter, HTTPException
from app.models.supplier import Supplier
from app.schemas.suppliers import SupplierRequest
from app.schemas.message import Message
from sqlmodel import select
from app.api.dependencies import addToDB, CurrentUser
from app.core.db import _SessionDep

router = APIRouter(prefix="/supplier")

@router.post("/", status_code=201)
def add_to_stock(supplier: SupplierRequest, session: _SessionDep, user: CurrentUser)-> Message:

    existing_supplier = session.exec(select(Supplier).where(Supplier.email == supplier.email)
                                      ).first() if supplier.email else None
    
    if existing_supplier: 
        raise HTTPException(status_code=400, detail= "Já existe um fornecedor com esse email")

    new_supplier = Supplier(**supplier.model_dump())
    
    addToDB(new_supplier)

    return Message("Fornecedor criado com sucesso")