from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.user import User, UserRole
from app.models.cart import Cart
from app.schemas.user import (
    UserCreate, UserOut, Token, LoginRequest, TokenRefresh,
    PasswordResetRequest, PasswordReset
)
from app.core.security import (
    verify_password, get_password_hash, create_access_token,
    create_refresh_token, decode_token, create_password_reset_token,
    verify_password_reset_token
)
from app.services.email_service import send_welcome_email, send_password_reset_email

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    user_in: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Registra um novo usuário e cria seu carrinho."""
    # Verificar se email já existe
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este email já está cadastrado.",
        )

    # Criar usuário
    user = User(
        full_name=user_in.full_name,
        email=user_in.email,
        phone=user_in.phone,
        cpf=user_in.cpf,
        birth_date=user_in.birth_date,
        hashed_password=get_password_hash(user_in.password),
        role=UserRole.customer,
    )
    db.add(user)
    db.flush()  # Para obter o ID do usuário

    # Criar carrinho vazio para o usuário
    cart = Cart(user_id=user.id)
    db.add(cart)
    db.commit()
    db.refresh(user)

    # Enviar email de boas-vindas em background
    background_tasks.add_task(send_welcome_email, user.full_name, user.email)

    return user


@router.post("/login", response_model=Token)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """Autentica um usuário e retorna tokens JWT."""
    user = db.query(User).filter(User.email == login_data.email).first()

    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta desativada. Entre em contato com o suporte.",
        )

    return Token(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=Token)
def refresh_token(token_data: TokenRefresh, db: Session = Depends(get_db)):
    """Gera novos tokens a partir de um refresh token válido."""
    payload = decode_token(token_data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido ou expirado.",
        )

    user_id = int(payload.get("sub"))
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado.",
        )

    return Token(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(
    request: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Envia email de redefinição de senha."""
    user = db.query(User).filter(User.email == request.email).first()
    # Sempre retorna 200 para não revelar se o email existe
    if user:
        token = create_password_reset_token(user.email)
        background_tasks.add_task(
            send_password_reset_email, user.email, user.full_name, token
        )
    return {"message": "Se este email estiver cadastrado, você receberá as instruções em breve."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(reset_data: PasswordReset, db: Session = Depends(get_db)):
    """Redefine a senha do usuário usando o token de redefinição."""
    email = verify_password_reset_token(reset_data.token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido ou expirado.",
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado.",
        )

    user.hashed_password = get_password_hash(reset_data.new_password)
    db.commit()
    return {"message": "Senha redefinida com sucesso."}
