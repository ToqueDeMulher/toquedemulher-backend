from uuid import UUID

from fastapi import APIRouter, Request, Depends
from sqlmodel import Session, select
from app.core.db import Database
from app.models.payment import Payment, PaymentStatus
from app.services.mercadopago_client import get_mp_sdk

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/webhook")
async def payment_webhook(request: Request, session: Session = Depends(Database.get_session)):
    body = await request.json()

    event_type = body.get("type")
    data = body.get("data", {})
    provider_payment_id = data.get("id")

    if event_type != "payment" or not provider_payment_id:
        return {"status": "ignored"}

    sdk = get_mp_sdk()
    mp_result = sdk.payment().get(provider_payment_id)
    mp_response = mp_result.get("response", {})

    external_reference = mp_response.get("external_reference")
    provider_status = mp_response.get("status")

    if not external_reference:
        return {"status": "missing_external_reference"}

    payment = session.exec(select(Payment).where(Payment.order_id == UUID(external_reference))).first()

    if not payment:
        return {"status": "payment_not_found"}

    payment.provider_payment_id = str(provider_payment_id)

    if provider_status == "approved":
        payment.status = PaymentStatus.APPROVED
    elif provider_status == "rejected":
        payment.status = PaymentStatus.REJECTED
    elif provider_status == "cancelled":
        payment.status = PaymentStatus.CANCELLED
    elif provider_status == "refunded":
        payment.status = PaymentStatus.REFUNDED
    else:
        payment.status = PaymentStatus.PENDING

    session.add(payment)
    session.commit()
    session.refresh(payment)

    return {"status": "ok"}