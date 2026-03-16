from fastapi import APIRouter, Depends
from sqlmodel import Session
from uuid import uuid4
from decimal import Decimal

from app.schemas.payment_schema import CreateCheckoutRequest, CheckoutResponse
from app.services.paymentService import create_checkout_session
from app.models.payment import Payment, PaymentStatus
from app.core.db import _SessionDep

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(payload: CreateCheckoutRequest, session: _SessionDep):

    order_id = uuid4()

    stripe_session = create_checkout_session(payload, order_id)

    total_amount = sum(
        Decimal(str(item.unit_price)) * item.quantity
        for item in payload.items
    )

    payment = Payment(
        order_id=order_id,
        payer_email=payload.payer_email,
        amount=total_amount,
        provider_session_id=stripe_session.id,
        status=PaymentStatus.PENDING
    )

    session.add(payment)
    session.commit()

    return CheckoutResponse(
        checkout_url=stripe_session.url,
        order_id=str(order_id)
    )