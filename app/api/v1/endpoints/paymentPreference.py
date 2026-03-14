from fastapi import APIRouter, HTTPException, Request
from app.schemas.create_preference import (CreatePreferenceRequest,CreatePreferenceResponse)
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

        result = create_payment_preference(payload)

        total_amount = sum(Decimal(str(item.unit_price)) * item.quantity
            for item in payload.items
        )

        payment = Payment(
            order_id=payload.order_id,
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


# Serve para receber a notificação do Mercado Pago, quando acontecer alguma atualização relacionada ao pagamento.
@router.post("/webhook")
async def mercado_pago_webhook(request: Request):
    body = await request.json()
    query_params = dict(request.query_params)

    print("Webhook body:", body)
    print("Webhook query:", query_params)

    return {"status": "ok"}