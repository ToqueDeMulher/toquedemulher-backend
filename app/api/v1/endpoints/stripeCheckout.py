from fastapi import APIRouter, HTTPException, Depends
from uuid import uuid4
from decimal import Decimal
from app.schemas.create_checkout import CreateCheckoutRequest, CheckoutResponse
from app.services.checkoutService import create_checkout_session
from app.models.payment import Payment, PaymentStatus
from app.core.db import _SessionDep
from app.services.loginService import LoginAndJWT
from typing import Annotated
from app.models.user import UserInDB
from app.models.paymentItem import PaymentItem


router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(payload: CreateCheckoutRequest, session: _SessionDep, user: Annotated[UserInDB, Depends(LoginAndJWT.get_current_active_user)] ): #Checkout é literalmente a tela de pagamento
     
    if not payload.items:
        raise HTTPException(status_code=400, detail="Nenhum item enviado para checkout")

    order_id = uuid4()

    total_amount = sum(
        Decimal(str(item.unit_price)) * item.quantity
        for item in payload.items
    )

    try:
        stripe_session = create_checkout_session(payload, order_id)

        payment = Payment(
            order_id=order_id,
            user_id=user.id,
            payer_email=user.email,
            amount=total_amount,
            provider_session_id=stripe_session.id,
            status=PaymentStatus.PENDING
        )
        session.add(payment)
        session.flush()

        for item in payload.items:
            payment_item = PaymentItem(
                payment_id=payment.id,
                title=item.name,
                product_url=item.product_url,
                unit_price=Decimal(str(item.unit_price)),
                quantity=item.quantity
            )
            session.add(payment_item)

        session.commit()
        session.refresh(payment)
        

        print("Payment salvo:", payment)

    except Exception as e:
        session.rollback()
        print("Erro ao salvar payment:", e)
        raise HTTPException(500, detail="Erro ao criar checkout")
    

    return CheckoutResponse(checkout_url=stripe_session.url,)