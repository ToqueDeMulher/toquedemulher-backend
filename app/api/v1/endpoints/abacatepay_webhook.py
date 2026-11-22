import base64
import hmac
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from sqlmodel import Session, select
from starlette.concurrency import run_in_threadpool

from app.core.db import _SessionDep
from app.core.settings import settings
from app.models.payment import Payment, PaymentStatus
from app.services import abacatepay

logger = logging.getLogger(__name__)
router = APIRouter()
# Public HMAC key from the provider documentation.
SIGNING_KEY = (
    b"t9dXRhHHo3yDEj5pVDYz0frf7q6bMKyMRmxxCPIPp3RCplBfXRxqlC6ZpiWmOqj4L63qEaeUOtrCI8P0VMUgo6iIga2ri9ogaHFs0WIIywSMg0q7RmBfybe1E5XJcfC4IW3alNqym0tXoAKkzvfEjZxV6bE0oG2zJrNNYmUCKZyV0KZ3JS8Votf9EAWWYdiDk"
    b"MkpbMdPggfh1EqHlVkMiTady6jOR3hyzGEHrIz2Ret0xHKMbiqkr9HS1JhNHDX9"
)
EVENTS = {
    f"{kind}.{event}": (kind, method)
    for kind, method in (("transparent", "PIX"), ("checkout", "CARD"))
    for event in ("completed", "refunded", "disputed", "lost")
}


def _process(
    session: Session, method: str, provider_id: str, event_type: str
) -> dict[str, str]:
    payment = session.exec(
        select(Payment)
        .where(
            Payment.provider == abacatepay.PROVIDER,
            Payment.provider_method == method,
            Payment.provider_session_id == provider_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if not payment:
        # A callback may arrive before the provider ID is committed.
        raise HTTPException(503, "Cobrança ainda não conciliada")
    refund_event = event_type.endswith((".refunded", ".lost"))
    if (
        payment.status in abacatepay.ACTIVE_STATUSES
        or payment.status == PaymentStatus.APPROVED.value
    ):
        if refund_event:
            payment.status = PaymentStatus.REFUND_PENDING.value
        elif (
            event_type == "checkout.disputed"
            and payment.status != PaymentStatus.REFUND_PENDING.value
        ):
            # Hosted checkout may report PAID while the dispute is open.
            payment.status = PaymentStatus.DISPUTED.value

    try:
        remote = abacatepay.reconcile(session, payment)
    except HTTPException:
        # A genuine refund or chargeback blocks fulfillment during API outages.
        session.commit()
        raise
    result = payment.status
    session.commit()
    if refund_event and result != PaymentStatus.REFUNDED.value:
        raise HTTPException(503, "Reembolso ainda em conciliação")
    if event_type.endswith(".completed"):
        if result == PaymentStatus.PENDING.value:
            raise HTTPException(503, "Pagamento ainda em conciliação")
        if (
            result in abacatepay.RELEASE_STATUSES
            and remote
            and remote.get("status") == "PAID"
        ):
            logger.error(
                "Pagamento após liberação do estoque: pedido=%s", payment.order_id
            )
            raise HTTPException(503, "Pagamento exige conciliação manual")
    return {"status": result}


@router.post("/payments/webhooks/abacatepay")
async def abacatepay_webhook(request: Request, session: _SessionDep) -> dict[str, str]:
    secret = settings.ABACATEPAY_WEBHOOK_SECRET
    if not secret.strip():
        raise HTTPException(503, "Webhook indisponível")

    supplied = request.query_params.getlist("webhookSecret")
    if len(supplied) != 1 or not hmac.compare_digest(
        supplied[0].encode(), secret.encode()
    ):
        raise HTTPException(403, "Webhook inválido")

    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > 64 * 1024:
            raise HTTPException(413, "Webhook excede o tamanho permitido")
        body.extend(chunk)
    expected = base64.b64encode(hmac.digest(SIGNING_KEY, body, "sha256"))
    signatures = request.headers.getlist("x-webhook-signature")
    if len(signatures) != 1 or not hmac.compare_digest(
        expected, signatures[0].encode()
    ):
        raise HTTPException(403, "Webhook inválido")

    try:
        event = json.loads(body)
    except (ValueError, RecursionError) as exc:
        raise HTTPException(400, "Webhook inválido") from exc
    if not isinstance(event, dict) or not isinstance(event.get("event"), str):
        raise HTTPException(400, "Webhook inválido")
    if event["event"] not in EVENTS:
        return {"status": "ignored"}
    if (
        event.get("apiVersion") != 2
        or event.get("devMode") is not settings.ABACATEPAY_DEV_MODE
    ):
        raise HTTPException(400, "Ambiente do webhook inválido")

    kind, method = EVENTS[event["event"]]
    data = event.get("data")
    charge = data.get(kind) if isinstance(data, dict) else None
    provider_id = charge.get("id") if isinstance(charge, dict) else None
    if not abacatepay.valid_id(provider_id, method):
        raise HTTPException(400, "Cobrança inválida")
    return await run_in_threadpool(
        _process, session, method, provider_id, event["event"]
    )
