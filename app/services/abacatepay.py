import re
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlencode, urlsplit, urlunsplit
from uuid import UUID

import httpx
from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError
from sqlmodel import Session, select

from app.core.settings import settings
from app.core.time import utc_now
from app.models.payment import Payment, PaymentStatus
from app.schemas.create_checkout import PixDetails
from app.services.paymentStockService import release_checkout_stock

PROVIDER = "abacatepay"
API_URL = "https://api.abacatepay.com/v2"
PIX_EXPIRY_SECONDS = 900
CHECK_INTERVAL = timedelta(seconds=6)
ACTIVE_STATUSES = (
    PaymentStatus.PENDING.value,
    PaymentStatus.DISPUTED.value,
    PaymentStatus.REFUND_PENDING.value,
)
REMOTE_STATUS = {
    "PENDING": PaymentStatus.PENDING.value,
    "PAID": PaymentStatus.APPROVED.value,
    "REFUNDED": PaymentStatus.REFUNDED.value,
    "UNDER_DISPUTE": PaymentStatus.DISPUTED.value,
    "CANCELLED": PaymentStatus.CANCELLED.value,
    "EXPIRED": PaymentStatus.EXPIRED.value,
    "FAILED": PaymentStatus.REJECTED.value,
}
RELEASE_STATUSES = {
    PaymentStatus.CANCELLED.value,
    PaymentStatus.EXPIRED.value,
    PaymentStatus.REJECTED.value,
}


def cents(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def unavailable() -> HTTPException:
    return HTTPException(
        502, "Não foi possível consultar o pagamento. Tente novamente."
    )


class ChargeRejected(Exception):
    """The provider explicitly rejected the creation request."""


def _request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    payload: dict | None = None,
    allow_missing: bool = False,
    charge_creation: bool = False,
) -> dict | list | None:
    key = settings.ABACATEPAY_API_KEY.strip()
    if not key:
        raise HTTPException(503, "Pagamento temporariamente indisponível.")
    try:
        response = httpx.request(
            method,
            f"{API_URL}/{path}",
            params=params,
            json=payload,
            headers={"Authorization": f"Bearer {key}"},
            timeout=httpx.Timeout(6, connect=2),
            follow_redirects=False,
        )
        if allow_missing and response.status_code == 404:
            return None
        if charge_creation and response.status_code == 422:
            raise ChargeRejected
        response.raise_for_status()
        envelope = response.json()
        if isinstance(envelope, dict) and envelope.get("success") is True:
            data = envelope.get("data")
            if isinstance(data, (dict, list)):
                return data
    except (httpx.HTTPError, ValueError):
        pass
    raise unavailable()


def valid_id(identifier: object, method: str | None) -> bool:
    prefix = "bill_" if method == "CARD" else "pix_char_"
    return (
        isinstance(identifier, str)
        and re.fullmatch(prefix + r"[A-Za-z0-9_-]{1,200}", identifier) is not None
    )


def _validate(payment: Payment, remote: dict) -> str:
    identifier = remote.get("id")
    amount = cents(payment.amount)
    status = REMOTE_STATUS.get(str(remote.get("status")))
    if (
        not valid_id(identifier, payment.provider_method)
        or (payment.provider_session_id and payment.provider_session_id != identifier)
        or type(remote.get("amount")) is not int
        or remote["amount"] != amount
        or remote.get("devMode") is not payment.provider_dev_mode
        or type(payment.provider_dev_mode) is not bool
        or remote.get("currency", "BRL") != "BRL"
        or payment.currency != "BRL"
        or not status
    ):
        raise unavailable()
    if status == PaymentStatus.APPROVED.value:
        paid_amount = remote.get("paidAmount")
        if (payment.provider_method == "CARD" or paid_amount is not None) and (
            type(paid_amount) is not int or paid_amount != amount
        ):
            raise unavailable()
    return status


def lookup(payment: Payment) -> dict | None:
    if payment.provider_dev_mode is not settings.ABACATEPAY_DEV_MODE:
        raise HTTPException(503, "Ambiente do pagamento indisponível.")
    reference = str(payment.order_id)
    params = (
        {"id": payment.provider_session_id}
        if payment.provider_session_id
        else {"externalId": reference}
    )
    if payment.provider_method == "CARD":
        result = _request("GET", "checkouts/get", params=params, allow_missing=True)
        if result is None:
            return None
        if not isinstance(result, dict) or result.get("externalId") != reference:
            raise unavailable()
        return result

    results = _request(
        "GET", "transparents/list", params={**params, "limit": 2, "method": "PIX"}
    )
    if not isinstance(results, list) or len(results) > 1:
        raise unavailable()
    if not results:
        return None
    remote = results[0]
    if not isinstance(remote, dict):
        raise unavailable()
    if not payment.provider_session_id:
        metadata = remote.get("metadata")
        if not isinstance(metadata, dict) or metadata.get("order_id") != reference:
            raise unavailable()
    return remote


def _return_url(base: str, payment: Payment) -> str:
    parts = urlsplit(base)
    query = urlencode({"session_id": str(payment.order_id)})
    return urlunsplit(
        parts._replace(query="&".join(filter(None, (parts.query, query))))
    )


def prepare_card_product(payment: Payment) -> str:
    amount = cents(payment.amount)
    external_id = f"tdm-brl-{amount}"
    product = _request(
        "GET", "products/get", params={"externalId": external_id}, allow_missing=True
    )
    if product is None:
        product = _request(
            "POST",
            "products/create",
            payload={
                "externalId": external_id,
                "name": "Pedido Toque de Mulher",
                "price": amount,
                "currency": "BRL",
            },
        )
    if (
        not isinstance(product, dict)
        or product.get("externalId") != external_id
        or product.get("price") != amount
        or product.get("currency") != "BRL"
        or product.get("devMode") is not payment.provider_dev_mode
        or not isinstance(product.get("id"), str)
    ):
        raise unavailable()
    return product["id"]


def create_remote(payment: Payment, *, card_product: str | None = None) -> dict:
    reference = str(payment.order_id)
    if card_product is not None:
        remote = _request(
            "POST",
            "checkouts/create",
            payload={
                "externalId": reference,
                "items": [{"id": card_product, "quantity": 1}],
                "methods": ["CARD"],
                "returnUrl": _return_url(settings.FRONTEND_PENDING_URL, payment),
                "completionUrl": _return_url(settings.FRONTEND_SUCCESS_URL, payment),
            },
            charge_creation=True,
        )
    else:
        remote = _request(
            "POST",
            "transparents/create",
            payload={
                "method": "PIX",
                "data": {
                    "amount": cents(payment.amount),
                    "expiresIn": PIX_EXPIRY_SECONDS,
                    "externalId": reference,
                    "metadata": {"order_id": reference},
                },
            },
            charge_creation=True,
        )
    if not isinstance(remote, dict):
        raise unavailable()
    _validate(payment, remote)
    return remote


def payment_for_update(
    session: Session, order_id: UUID, *, user_id: UUID | None = None
) -> Payment | None:
    query = select(Payment).where(
        Payment.order_id == order_id, Payment.provider == PROVIDER
    )
    if user_id is not None:
        query = query.where(Payment.user_id == user_id)
    return session.exec(
        query.with_for_update().execution_options(populate_existing=True)
    ).first()


def close_unpaid(session: Session, payment: Payment, status: str) -> None:
    release_checkout_stock(session, payment, "Liberação de reserva: cobrança encerrada")
    payment.status = status
    payment.provider_checkout_details = None
    payment.updated_at = utc_now()
    session.add(payment)


def apply_remote(session: Session, payment: Payment, remote: dict) -> None:
    target = _validate(payment, remote)
    current = payment.status
    payment.provider_session_id = remote["id"]
    payment.provider_payment_id = remote["id"]
    if current == PaymentStatus.REFUND_PENDING.value:
        if target == PaymentStatus.REFUNDED.value:
            payment.status = target
    elif current in ACTIVE_STATUSES or current == PaymentStatus.APPROVED.value:
        if target in RELEASE_STATUSES and current == PaymentStatus.PENDING.value:
            close_unpaid(session, payment, target)
        elif (
            target in {PaymentStatus.REFUNDED.value, PaymentStatus.DISPUTED.value}
            or target == PaymentStatus.APPROVED.value
            and (
                current != PaymentStatus.DISPUTED.value
                or payment.provider_method == "PIX"
            )
        ):
            payment.status = target
    payment.updated_at = utc_now()
    payment.provider_checked_at = utc_now()
    payment.provider_checkout_details = payment_details(payment, remote)
    session.add(payment)


def aware(timestamp: datetime) -> datetime:
    return timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=UTC)


def reconcile(session: Session, payment: Payment) -> dict | None:
    payment.provider_checked_at = utc_now()
    payment.provider_checkout_details = None
    if not payment.provider_creation_started and not payment.provider_session_id:
        if (
            aware(payment.created_at) + timedelta(seconds=PIX_EXPIRY_SECONDS)
            <= utc_now()
        ):
            close_unpaid(session, payment, PaymentStatus.EXPIRED.value)
        payment.provider_checkout_details = {}
        return None

    remote = lookup(payment)
    if remote is not None:
        apply_remote(session, payment, remote)
    elif payment.provider_session_id:
        raise unavailable()
    else:
        payment.provider_checkout_details = {}
    return remote


def refresh_from_client(session: Session, payment: Payment) -> bool:
    """Serialize and throttle provider reads across API workers."""
    checked_at = payment.provider_checked_at
    if checked_at and utc_now() - aware(checked_at) < CHECK_INTERVAL:
        if payment.provider_checkout_details is None:
            raise unavailable()
        return False
    try:
        reconcile(session, payment)
    except HTTPException:
        # Persist the attempt so outages cannot trigger a request flood.
        session.commit()
        raise
    return True


def payment_details(payment: Payment, remote: dict | None) -> dict:
    if not remote or payment.status != PaymentStatus.PENDING.value:
        return {}
    if payment.provider_method == "CARD":
        url = remote.get("url")
        if isinstance(url, str):
            parsed = urlsplit(url)
            if (
                parsed.scheme == "https"
                and parsed.netloc == "app.abacatepay.com"
                and parsed.path.startswith("/pay/")
            ):
                return {"checkout_url": url}
        raise unavailable()

    code = remote.get("brCode")
    image = remote.get("brCodeBase64")
    if (
        not isinstance(code, str)
        or not 1 <= len(code) <= 1024
        or not isinstance(image, str)
        or len(image) > 300_000
        or not re.fullmatch(r"data:image/png;base64,[A-Za-z0-9+/]+={0,2}", image)
    ):
        raise unavailable()
    try:
        expires_at = TypeAdapter(datetime).validate_python(remote.get("expiresAt"))
    except ValidationError:
        raise unavailable() from None
    if expires_at.tzinfo is None:
        raise unavailable()
    return {
        "pix": PixDetails(code=code, image=image, expires_at=expires_at).model_dump(
            mode="json"
        )
    }
