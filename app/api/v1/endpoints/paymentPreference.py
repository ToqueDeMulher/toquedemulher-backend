from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from app.schemas.create_preference import (CreatePreferenceRequest,CreatePreferenceResponse , CreatePreferenceRequestWithOrder)
from app.services.paymentService import create_payment_preference
from app.models.payment import Payment, PaymentStatus
from decimal import Decimal
from app.core.db import _SessionDep


router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("/preference", response_model=CreatePreferenceResponse)
def create_preference(payload: CreatePreferenceRequest, session: _SessionDep):
    try:
        items = [
            {
                "id": item.id,
                "title": item.title,
                "quantity": item.quantity,
                "currency_id": "BRL",
                "unit_price": item.unit_price,
            }
            for item in payload.items
        ]

        payload_with_order = CreatePreferenceRequestWithOrder(
            order_id=str(uuid4()),
            payer_email=payload.payer_email,
            items=payload.items,
)
        result = create_payment_preference(payload_with_order)

        total_amount = sum(Decimal(str(item.unit_price)) * item.quantity
            for item in payload.items
        )

        payment = Payment(
            order_id=payload_with_order.order_id,
            status=PaymentStatus.PENDING,
            payer_email=payload.payer_email,
            amount=total_amount,
            provider_preference_id=result.preference_id,
)
        
        session.add(payment)
        session.commit()
        session.refresh(payment)
        

        if not result.preference_id:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Mercado Pago não retornou a preference_id",
                    "mercado_pago_response": result.raw
                }
            )

        return CreatePreferenceResponse(
            preference_id=result.preference_id,
            init_point=result.init_point,
            sandbox_init_point=result.sandbox_init_point,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


