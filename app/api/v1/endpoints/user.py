from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlmodel import select

from app.api.dependencies import CurrentUser, addToDB
from app.core.db import _SessionDep
from app.core.time import utc_now
from app.models.address import Address
from app.models.cart import Cart
from app.models.payment import Payment
from app.models.paymentItem import PaymentItem
from app.models.product import Product
from app.models.productReview import ProductReview
from app.models.user import UserInDB
from app.models.userPaymentMethod import UserPaymentMethod
from app.schemas.account import (
    AccountOrderItemResponse,
    AccountOrderResponse,
    AccountReviewResponse,
)
from app.schemas.message import Message
from app.schemas.user import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    ChangeUserInformationRequest,
    ConfirmEmailRequest,
    DeleteAccountRequest,
    GetUserResponse,
    UserRequest,
)
from app.services.email_confirmation_service import (
    send_confirmation_email,
    verify_email_confirmation_token,
)
from app.services.loginService import LoginAndJWT

router = APIRouter(prefix="/user")


@router.post("/register", response_model=Message, status_code=201)
def create_user(
    user: UserRequest,
    session: _SessionDep,
    background_tasks: BackgroundTasks,
):
    existing_user = session.exec(
        select(UserInDB).where(UserInDB.email == user.email)
    ).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    db_user = UserInDB(
        name=user.name,
        email=user.email,
        hashed_password=LoginAndJWT.hashing_password(user.password),
    )

    addToDB(db_user, session)
    background_tasks.add_task(send_confirmation_email, db_user.name, db_user.email)
    return Message(
        mensagem="Usuario criado com sucesso. Verifique seu email para confirmar a conta."
    )


@router.post("/confirm-email", response_model=Message, status_code=200)
def confirm_email(payload: ConfirmEmailRequest, session: _SessionDep):
    email = verify_email_confirmation_token(payload.token)

    if not email:
        raise HTTPException(status_code=400, detail="Token de confirmacao invalido")

    db_user = session.exec(select(UserInDB).where(UserInDB.email == email)).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    if db_user.email_confirmed_at is None:
        db_user.email_confirmed_at = utc_now()
        addToDB(db_user, session)

    return Message(mensagem="Email confirmado com sucesso")


@router.get("/me", response_model=GetUserResponse)
def get_user(session: _SessionDep, user: CurrentUser):
    db_user = session.get(UserInDB, user.id)

    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    return GetUserResponse(
        id=str(db_user.id),
        name=db_user.name,
        cpf=db_user.cpf,
        email=db_user.email,
        phone=db_user.phone,
        gender=db_user.gender,
        birth_date=db_user.birth_date,
        accepts_marketing=db_user.accepts_marketing,
        created_at=db_user.created_at.date(),
        email_confirmed_at=db_user.email_confirmed_at,
        role=db_user.role,
    )


@router.get("/me/orders", response_model=list[AccountOrderResponse])
def get_my_orders(session: _SessionDep, user: CurrentUser):
    payments = session.exec(
        select(Payment)
        .where(Payment.user_id == user.id)
        .order_by(Payment.created_at.desc())
    ).all()

    orders: list[AccountOrderResponse] = []
    for payment in payments:
        items = session.exec(
            select(PaymentItem).where(PaymentItem.payment_id == payment.id)
        ).all()
        order_items = [
            AccountOrderItemResponse(
                id=str(item.id),
                title=item.title,
                quantity=item.quantity,
                unit_price=float(item.unit_price),
            )
            for item in items
        ]
        orders.append(
            AccountOrderResponse(
                id=str(payment.order_id),
                order_date=payment.created_at,
                status=payment.status,
                total=float(payment.amount),
                items_count=sum(item.quantity for item in items),
                items=order_items,
            )
        )

    return orders


@router.get("/me/reviews", response_model=list[AccountReviewResponse])
def get_my_reviews(session: _SessionDep, user: CurrentUser):
    reviews = session.exec(
        select(ProductReview)
        .where(ProductReview.user_id == user.id)
        .order_by(ProductReview.created_at.desc())
    ).all()

    response: list[AccountReviewResponse] = []
    for review in reviews:
        product = session.get(Product, review.product_id)
        response.append(
            AccountReviewResponse(
                id=review.id or 0,
                product_id=review.product_id,
                product_name=product.name if product else "Produto removido",
                rating=review.rating,
                title=review.title,
                comment=review.comment,
                created_at=review.created_at,
            )
        )

    return response


@router.delete("/me", response_model=Message)
def delete_user(data: DeleteAccountRequest, session: _SessionDep, user: CurrentUser):
    db_user = session.get(UserInDB, user.id)

    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    if data.confirm_email.lower() != db_user.email.lower():
        raise HTTPException(status_code=400, detail="Email de confirmacao invalido")

    if data.confirm_text.strip().upper() != "DELETE":
        raise HTTPException(status_code=400, detail="Confirmacao invalida")

    current_password = data.current_password.strip() if data.current_password else None
    if current_password and not LoginAndJWT.verify_password(
        current_password,
        db_user.hashed_password,
    ):
        raise HTTPException(status_code=400, detail="Senha incorreta")

    now = utc_now()
    anonymized_email = f"deleted-{db_user.id.hex}@toquedemulher.invalid"

    for payment_method in session.exec(
        select(UserPaymentMethod).where(UserPaymentMethod.user_id == db_user.id)
    ).all():
        session.delete(payment_method)

    for review in session.exec(
        select(ProductReview).where(ProductReview.user_id == db_user.id)
    ).all():
        session.delete(review)

    for address in session.exec(
        select(Address).where(Address.user_id == db_user.id)
    ).all():
        address.label = None
        address.cep = "00000000"
        address.street = "Endereco removido"
        address.number = None
        address.complement = None
        address.neighborhood = None
        address.city = "Removido"
        address.state = "NA"
        address.region = None
        address.ddd = None
        address.is_default_shipping = False
        address.is_default_billing = False
        session.add(address)

    for payment in session.exec(
        select(Payment).where(Payment.user_id == db_user.id)
    ).all():
        payment.payer_email = anonymized_email
        payment.updated_at = now
        session.add(payment)

    for cart in session.exec(select(Cart).where(Cart.user_id == db_user.id)).all():
        cart.status = "excluido"
        cart.updated_at = now
        session.add(cart)

    db_user.name = "Conta excluida"
    db_user.email = anonymized_email
    db_user.hashed_password = LoginAndJWT.hashing_password(f"deleted:{db_user.id}:{now}")
    db_user.cpf = None
    db_user.phone = None
    db_user.gender = None
    db_user.birth_date = None
    db_user.accepts_marketing = False
    db_user.email_confirmed_at = None
    db_user.deleted_at = now
    db_user.updated_at = now
    db_user.disabled = True
    session.add(db_user)
    session.commit()

    return Message(mensagem="Conta excluida com sucesso")


@router.put("/me", response_model=Message)
def change_user_information(
    user_informations: ChangeUserInformationRequest,
    session: _SessionDep,
    user: CurrentUser,
):
    db_user = session.exec(select(UserInDB).where(UserInDB.id == user.id)).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    update_data = user_informations.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_user, key, value)

    addToDB(db_user, session)
    return Message(mensagem=f"Usuario {db_user.name} atualizado com sucesso")


@router.put("/me/email", response_model=Message)
def change_email(data: ChangeEmailRequest, session: _SessionDep, user: CurrentUser):
    db_user = session.get(UserInDB, user.id)

    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    if data.new_email == db_user.email:
        raise HTTPException(status_code=400, detail="O novo email e igual ao email atual")

    existing_user = session.exec(
        select(UserInDB).where(UserInDB.email == data.new_email)
    ).first()

    if existing_user and existing_user.id != db_user.id:
        raise HTTPException(status_code=400, detail="Email ja esta em uso")

    db_user.email = data.new_email
    addToDB(db_user, session)

    return Message(mensagem="Email atualizado com sucesso")


@router.put("/me/password", response_model=Message)
def change_password(data: ChangePasswordRequest, user: CurrentUser, session: _SessionDep):
    db_user = session.get(UserInDB, user.id)

    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    password_is_correct = LoginAndJWT.verify_password(
        data.current_password,
        db_user.hashed_password,
    )

    if not password_is_correct:
        raise HTTPException(status_code=400, detail="Senha atual incorreta")

    db_user.hashed_password = LoginAndJWT.hashing_password(data.new_password)
    addToDB(db_user, session)

    return Message(mensagem="Senha alterada com sucesso")
