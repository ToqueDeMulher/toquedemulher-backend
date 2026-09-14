import hashlib
import secrets
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlmodel import select

from app.api.dependencies import AdminUser, CurrentUser
from app.core.db import _SessionDep
from app.core.settings import settings
from app.core.time import utc_now
from app.models.payment import Payment
from app.models.product import Product
from app.models.shipping import Shipment, ShippingConnection, ShippingQuote
from app.schemas.shipping import (
    PrepareShipmentRequest,
    ReconcileShipmentRequest,
    ShippingDimensions,
    ShippingQuoteRequest,
)
from app.services import melhor_envio as me, shipment_service as operations
from app.services.brasil_api import check_rate_limit

router = APIRouter(prefix="/shipping", tags=["shipping"])
COOKIE = "tdm_shipping_oauth_state"
COOKIE_PATH = settings.API_V1_PREFIX + "/shipping/oauth"


@router.post("/quotes")
def quotes(payload: ShippingQuoteRequest, session: _SessionDep, request: Request):
    check_rate_limit(request, "quotes")
    return me.create_quote(payload, session)


@router.get("/admin/connection")
def connection_status(session: _SessionDep, user: AdminUser):
    connection = session.get(ShippingConnection, me.environment())
    return {
        "environment": me.environment(),
        "configured": bool(
            settings.MELHOR_ENVIO_CLIENT_ID and settings.MELHOR_ENVIO_CLIENT_SECRET
        ),
        "connected": bool(connection and connection.access_ciphertext),
        "expires_at": connection.expires_at if connection else None,
    }


@router.post("/admin/authorize")
def authorize(session: _SessionDep, user: AdminUser, response: Response):
    state = secrets.token_urlsafe(32)
    url = me.authorize_url(state)
    connection = session.get(
        ShippingConnection, me.environment()
    ) or ShippingConnection(environment=me.environment())
    connection.state_digest = hashlib.sha256(state.encode()).hexdigest()
    connection.state_expires_at = utc_now() + timedelta(minutes=10)
    session.add(connection)
    session.commit()
    response.set_cookie(
        COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=settings.MELHOR_ENVIO_REDIRECT_URI.startswith("https://"),
        samesite="lax",
        path=COOKIE_PATH,
    )
    return {"url": url}


@router.get("/oauth/callback")
def callback(
    request: Request,
    session: _SessionDep,
    state: str = "",
    code: str = "",
    error: str = "",
):
    cookie = request.cookies.get(COOKIE, "")
    connection = session.exec(
        select(ShippingConnection)
        .where(ShippingConnection.environment == me.environment())
        .with_for_update()
    ).first()
    if (
        not state
        or not cookie
        or not secrets.compare_digest(state, cookie)
        or not connection
        or not connection.state_digest
        or not secrets.compare_digest(
            hashlib.sha256(state.encode()).hexdigest(), connection.state_digest
        )
        or not connection.state_expires_at
        or me.aware(connection.state_expires_at) <= utc_now()
    ):
        raise HTTPException(
            400, "Autorização expirada ou inválida. Inicie a conexão novamente."
        )
    connection.state_digest = None
    connection.state_expires_at = None
    session.add(connection)
    session.commit()
    if not error and code:
        me.exchange_code(connection, code)
        session.add(connection)
        session.commit()
    response = RedirectResponse(
        settings.FRONTEND_URL.rstrip("/")
        + "/admin/envios?connection="
        + ("cancelled" if error or not code else "success"),
        status_code=303,
    )
    response.delete_cookie(COOKIE, path=COOKIE_PATH)
    return response


@router.get("/admin/products")
def shipping_products(session: _SessionDep, user: AdminUser):
    products = session.exec(
        select(Product).where(Product.active == True).order_by(Product.name)
    ).all()
    return [
        {
            "id": str(product.id),
            "name": product.name,
            **{key: getattr(product, key) for key in ShippingDimensions.model_fields},
        }
        for product in products
    ]


@router.put("/admin/products/{product_id}/dimensions")
def dimensions(
    product_id: UUID, payload: ShippingDimensions, session: _SessionDep, user: AdminUser
):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Produto não encontrado")
    for key, value in payload.model_dump().items():
        setattr(product, key, value)
    product.updated_at = utc_now()
    session.add(product)
    session.commit()
    return {"status": "ok"}


@router.get("/admin/shipments")
def list_shipments(session: _SessionDep, user: AdminUser):
    rows = session.exec(
        select(Shipment, Payment)
        .join(Payment, Payment.id == Shipment.payment_id)
        .order_by(Shipment.updated_at.desc())
        .limit(100)
    ).all()
    return [
        me.shipment_out(shipment, payment, admin=True) for shipment, payment in rows
    ]


def owned_shipment(order_id, session, user, *, admin=False):
    payment = session.exec(select(Payment).where(Payment.order_id == order_id)).first()
    if not payment or (not admin and payment.user_id != user.id):
        raise HTTPException(404, "Pedido não encontrado")
    shipment = session.exec(
        select(Shipment).where(Shipment.payment_id == payment.id).with_for_update()
    ).first()
    if not shipment:
        raise HTTPException(404, "Este pedido não possui envio integrado")
    quote = session.get(ShippingQuote, shipment.quote_id)
    if quote.environment != me.environment():
        raise HTTPException(409, "Envio de outro ambiente Melhor Envio")
    return shipment, payment


@router.get("/orders/{order_id}")
def get_shipment(order_id: UUID, session: _SessionDep, user: CurrentUser):
    shipment, payment = owned_shipment(order_id, session, user)
    return me.shipment_out(shipment, payment)


@router.post("/orders/{order_id}/sync")
def sync_customer(
    order_id: UUID, session: _SessionDep, user: CurrentUser, request: Request
):
    check_rate_limit(request, "tracking")
    shipment, payment = owned_shipment(order_id, session, user)
    if shipment.labels and me.aware(shipment.updated_at) < utc_now() - timedelta(
        seconds=60
    ):
        operations.refresh(session, shipment)
    return me.shipment_out(shipment, payment)


@router.post("/admin/shipments/{order_id}/prepare")
def prepare(
    order_id: UUID,
    payload: PrepareShipmentRequest,
    session: _SessionDep,
    user: AdminUser,
):
    shipment, payment = owned_shipment(order_id, session, user, admin=True)
    operations.prepare(session, shipment, payment, payload.invoice_key)
    return me.shipment_out(shipment, payment, admin=True)


@router.post("/admin/shipments/{order_id}/reconcile")
def reconcile(
    order_id: UUID,
    payload: ReconcileShipmentRequest,
    session: _SessionDep,
    user: AdminUser,
):
    shipment, payment = owned_shipment(order_id, session, user, admin=True)
    if shipment.status not in {"needs_review", "creating"}:
        raise HTTPException(
            409, "Reconciliação disponível apenas para criação interrompida"
        )
    ids = list(dict.fromkeys(str(label_id) for label_id in payload.label_ids))
    if any(label["id"] not in ids for label in shipment.labels):
        raise HTTPException(422, "Inclua também as etiquetas já registradas")
    recovered_labels = []
    for label_id in ids:
        data = me.request(
            session, "GET", "/api/v2/me/orders/search", params={"q": label_id}
        )
        label = (
            next((item for item in data if item.get("id") == label_id), None)
            if isinstance(data, list)
            else None
        )
        if (
            not label
            or int(label.get("service_id", 0)) != shipment.service_id
            or not any(
                (tag.get("tag") if isinstance(tag, dict) else tag) == str(order_id)
                for tag in label.get("tags", [])
            )
            or label.get("to", {}).get("postal_code")
            != shipment.recipient["postal_code"]
        ):
            raise HTTPException(
                422, "Uma das etiquetas não pertence ao pedido ou à entrega escolhida"
            )
        try:
            actual_cost = Decimal(str(label["price"]))
            if not actual_cost.is_finite() or actual_cost < 0:
                raise ValueError()
        except (KeyError, ValueError, InvalidOperation):
            raise HTTPException(502, "O valor de uma das etiquetas não foi confirmado")
        recovered_labels.append(
            {"id": label_id, "cost": str(actual_cost.quantize(Decimal("0.01")))}
        )
    shipment.labels = recovered_labels
    shipment.cost = sum(
        (Decimal(label["cost"]) for label in recovered_labels), Decimal("0")
    )
    operations.persist(session, shipment)
    operations.refresh(session, shipment)
    return me.shipment_out(shipment, payment, admin=True)


@router.post("/admin/shipments/{order_id}/{action}")
def shipment_action(order_id: UUID, action: str, session: _SessionDep, user: AdminUser):
    shipment, payment = owned_shipment(order_id, session, user, admin=True)
    if action == "sync":
        operations.refresh(session, shipment)
    elif action == "pay":
        operations.pay(session, shipment, payment)
    elif action == "generate":
        operations.generate(session, shipment)
    elif action == "print":
        operations.print_labels(session, shipment)
    else:
        raise HTTPException(404, "Operação de envio desconhecida")
    return me.shipment_out(shipment, payment, admin=True)
