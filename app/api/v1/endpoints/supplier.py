from fastapi import APIRouter, HTTPException
from app.models.supplier import Supplier
from app.schemas.suppliers import SupplierRequest, SupplierUpdateRequest
from app.schemas.message import Message
from sqlmodel import select
from app.api.dependencies import addToDB, AdminUser
from app.core.db import _SessionDep
from app.services.supplierService import SupplierService

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

@router.put("/")
def change_supplier(payload: SupplierUpdateRequest,user: AdminUser,session: _SessionDep) -> Message:

    supplier = SupplierService.find_supplier_by_name(session, payload.supplier_name)

    update_data = payload.model_dump(exclude_unset=True)

    # Remove supplier_name porque ele é usado só para buscar o fornecedor
    update_data.pop("supplier_name", None)

    if "email" in update_data and update_data["email"]:
        existing_supplier = session.exec(
            select(Supplier).where(
                Supplier.email == update_data["email"],
                Supplier.id != supplier.id
            )
        ).first()

        if existing_supplier:
            raise HTTPException(status_code=400,detail="Já existe um fornecedor com esse email")

    for field, value in update_data.items():
        setattr(supplier, field, value)

    addToDB(supplier, session)

    return Message(mensagem="Fornecedor atualizado com sucesso")

@router.delete("/")
def delete_supplier(user: AdminUser, session: _SessionDep, supplier_name:str):

    supplier = SupplierService.find_supplier_by_name(session, supplier_name)

    session.delete(supplier)
    session.commit()

    return f"Supplier {supplier.name} deletado com sucesso"

@router.get("/")
def get_suppliers(user: AdminUser, session: _SessionDep):
    suppliers = session.exec(select(Supplier)).all()

    if not suppliers:
        raise HTTPException(status_code=404, detail= "Não existem fornecedores cadastrados")
    return suppliers