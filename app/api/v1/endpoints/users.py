import os
import uuid
import shutil
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_active_user, get_current_admin
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.db.base import get_db
from app.models.user import Address, User
from app.schemas.user import (
    AddressCreate,
    AddressOut,
    AddressUpdate,
    UserChangePassword,
    UserOut,
    UserOutAdmin,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["Usuários"])

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


# ─── Perfil do Usuário Logado ────────────────────────────────────────────────

@router.get("/me", response_model=UserOut)
def get_my_profile(current_user: User = Depends(get_current_active_user)) -> User:
    """Retorna os dados do usuário autenticado."""
    return current_user


@router.put("/me", response_model=UserOut)
def update_my_profile(
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Atualiza os dados do usuário autenticado."""
    for field, value in user_update.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/change-password", status_code=status.HTTP_200_OK)
def change_password(
    password_data: UserChangePassword,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Altera a senha do usuário autenticado."""
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual incorreta.",
        )
    current_user.hashed_password = get_password_hash(password_data.new_password)
    db.commit()
    return {"message": "Senha alterada com sucesso."}


@router.post("/me/avatar", response_model=UserOut)
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Faz upload do avatar do usuário."""
    # Valida tipo MIME
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de imagem inválido. Use JPEG, PNG ou WebP.",
        )

    # CORREÇÃO: extensão extraída com segurança via os.path.splitext,
    # não com split(".")[-1] que permite nomes como "shell.php.jpg" passarem silenciosamente
    original_name = os.path.basename(file.filename or "")
    _, ext = os.path.splitext(original_name)
    ext = ext.lower()

    if ext not in _ALLOWED_IMAGE_EXTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Extensão de arquivo inválida.",
        )

    upload_dir = os.path.join(settings.UPLOAD_DIR, "avatars")
    os.makedirs(upload_dir, exist_ok=True)

    filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    current_user.avatar_url = f"/uploads/avatars/{filename}"
    db.commit()
    db.refresh(current_user)
    return current_user


# ─── Endereços ───────────────────────────────────────────────────────────────

@router.get("/me/addresses", response_model=List[AddressOut])
def list_addresses(current_user: User = Depends(get_current_active_user)) -> list:
    """Lista os endereços do usuário autenticado."""
    return current_user.addresses


@router.post("/me/addresses", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
def create_address(
    address_in: AddressCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Address:
    """Adiciona um novo endereço ao usuário."""
    if address_in.is_default:
        db.query(Address).filter(Address.user_id == current_user.id).update({"is_default": False})

    address = Address(user_id=current_user.id, **address_in.model_dump())
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


@router.put("/me/addresses/{address_id}", response_model=AddressOut)
def update_address(
    address_id: int,
    address_update: AddressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Address:
    """Atualiza um endereço do usuário."""
    address = db.query(Address).filter(
        Address.id == address_id, Address.user_id == current_user.id
    ).first()
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endereço não encontrado.")

    if address_update.is_default:
        db.query(Address).filter(Address.user_id == current_user.id).update({"is_default": False})

    for field, value in address_update.model_dump(exclude_unset=True).items():
        setattr(address, field, value)
    db.commit()
    db.refresh(address)
    return address


@router.delete("/me/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_address(
    address_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """Remove um endereço do usuário."""
    address = db.query(Address).filter(
        Address.id == address_id, Address.user_id == current_user.id
    ).first()
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endereço não encontrado.")
    db.delete(address)
    db.commit()


# ─── Administração de Usuários ───────────────────────────────────────────────

@router.get("/", response_model=List[UserOutAdmin])
def list_users(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> list:
    """[Admin] Lista todos os usuários."""
    return db.query(User).offset(skip).limit(limit).all()


@router.put("/{user_id}/activate", response_model=UserOut)
def toggle_user_active(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> User:
    """[Admin] Ativa ou desativa um usuário."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return user