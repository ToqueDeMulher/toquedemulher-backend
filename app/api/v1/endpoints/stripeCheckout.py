from fastapi import APIRouter, Depends
from sqlmodel import Session
from uuid import uuid4
from decimal import Decimal

from app.schemas.create_checkout import CreateCheckoutRequest, CheckoutResponse
from app.services.checkoutService import create_checkout_session
from app.models.payment import Payment, PaymentStatus
from app.core.db import _SessionDep

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(payload: CreateCheckoutRequest, session: _SessionDep): #Checkout é literalmente a tela de pagamento
 
    order_id = uuid4()

    stripe_session = create_checkout_session(payload, order_id)

    total_amount = sum(
        Decimal(str(item.unit_price)) * item.quantity
        for item in payload.items
    )

    try:

        payment = Payment(
            order_id=order_id,
            payer_email=payload.payer_email,
            amount=total_amount,
            provider_session_id=stripe_session.id,
            status=PaymentStatus.PENDING
        )

        session.add(payment)
        session.commit()
        session.refresh(payment)

        print("Payment salvo:", payment)

    except Exception as e:

        print("Erro ao salvar payment:", e)

    return CheckoutResponse(
        checkout_url=stripe_session.url,
        order_id=str(order_id)
    )