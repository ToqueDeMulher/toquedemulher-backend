from fastapi import APIRouter, HTTPException, Request
from app.schemas.payments import (
    CreatePreferenceRequest,
    CreatePreferenceResponse,
)
from app.services.paymentService import create_payment_preference

router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("/preference", response_model=CreatePreferenceResponse)
def create_preference(payload: CreatePreferenceRequest):
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

        result = create_payment_preference(
            order_id=payload.order_id,
            payer_email=payload.payer_email,
            items=items,
        )

        if not result["preference_id"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Mercado Pago não retornou a preference_id",
                    "mercado_pago_response": result["raw"]
                }
            )

        return CreatePreferenceResponse(
            preference_id=result["preference_id"],
            init_point=result["init_point"],
            sandbox_init_point=result["sandbox_init_point"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook")
async def mercado_pago_webhook(request: Request):
    body = await request.json()
    query_params = dict(request.query_params)

    print("Webhook body:", body)
    print("Webhook query:", query_params)

    return {"status": "ok"}