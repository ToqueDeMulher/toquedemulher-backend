"""Melhor Envio v2 transport, OAuth rotation and server-authoritative quotes."""

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.settings import settings
from app.core.time import utc_now
from app.models.product import Product
from app.models.shipping import ShippingConnection, ShippingQuote, Shipment

SCOPES = "cart-read cart-write orders-read shipping-calculate shipping-checkout shipping-generate shipping-print shipping-tracking"


def environment():
    if settings.MELHOR_ENVIO_ENVIRONMENT not in ("sandbox", "production"):
        raise HTTPException(503, "Ambiente Melhor Envio inválido")
    return settings.MELHOR_ENVIO_ENVIRONMENT


def base_url():
    return (
        "https://sandbox.melhorenvio.com.br"
        if environment() == "sandbox"
        else "https://www.melhorenvio.com.br"
    )


def aware(value: datetime):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def cipher():
    # Separate encryption domain; never persist tokens as plaintext.
    key = hashlib.sha256(
        ("melhor-envio-tokens:" + settings.SECRET_KEY).encode()
    ).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def decrypt(value):
    try:
        return cipher().decrypt(value.encode()).decode()
    except (InvalidToken, AttributeError):
        raise HTTPException(
            503, "Reconecte sua conta Melhor Envio no painel administrativo"
        )


def headers():
    agent = settings.MELHOR_ENVIO_USER_AGENT.strip()
    if not agent or "@" not in agent:
        raise HTTPException(
            503,
            "Configure MELHOR_ENVIO_USER_AGENT com o nome da loja e e-mail de contato",
        )
    return {"Accept": "application/json", "User-Agent": agent}


def transport(method, path, *, token=None, body=None, params=None):
    request_headers = headers()
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    try:
        with httpx.Client(timeout=settings.MELHOR_ENVIO_TIMEOUT) as client:
            response = client.request(
                method,
                base_url() + path,
                headers=request_headers,
                json=body,
                params=params,
            )
    except httpx.HTTPError:
        raise HTTPException(
            502,
            "Melhor Envio indisponível. Consulte o status antes de repetir uma operação de etiqueta.",
        )
    if response.status_code >= 400:
        if response.status_code in (401, 403):
            raise HTTPException(
                503, "Reconecte o Melhor Envio e confira as permissões do aplicativo"
            )
        if response.status_code == 429:
            raise HTTPException(
                503,
                "Melhor Envio temporariamente ocupado. Tente novamente em alguns instantes.",
            )
        # Avoid leaking remote tokens, personal information or HTML errors.
        raise HTTPException(
            502,
            "Melhor Envio recusou a operação. Confira cadastro, saldo, nota fiscal e dados do envio.",
        )
    try:
        return response.json()
    except ValueError:
        raise HTTPException(502, "Melhor Envio retornou uma resposta inválida")


def oauth_config():
    if not settings.MELHOR_ENVIO_CLIENT_ID or not settings.MELHOR_ENVIO_CLIENT_SECRET:
        raise HTTPException(
            503, "Configure o aplicativo Melhor Envio no .env do backend"
        )
    headers()


def store_tokens(connection, data):
    if (
        not isinstance(data, dict)
        or not data.get("access_token")
        or not data.get("refresh_token")
    ):
        raise HTTPException(502, "Melhor Envio não retornou os tokens de autorização")
    connection.access_ciphertext = (
        cipher().encrypt(data["access_token"].encode()).decode()
    )
    connection.refresh_ciphertext = (
        cipher().encrypt(data["refresh_token"].encode()).decode()
    )
    connection.expires_at = utc_now() + timedelta(
        seconds=int(data.get("expires_in", 2592000))
    )


def authorize_url(state):
    oauth_config()
    return (
        base_url()
        + "/oauth/authorize?"
        + urlencode(
            {
                "client_id": settings.MELHOR_ENVIO_CLIENT_ID,
                "redirect_uri": settings.MELHOR_ENVIO_REDIRECT_URI,
                "response_type": "code",
                "scope": SCOPES,
                "state": state,
            }
        )
    )


def exchange_code(connection, code):
    oauth_config()
    data = transport(
        "POST",
        "/oauth/token",
        body={
            "grant_type": "authorization_code",
            "client_id": settings.MELHOR_ENVIO_CLIENT_ID,
            "client_secret": settings.MELHOR_ENVIO_CLIENT_SECRET,
            "redirect_uri": settings.MELHOR_ENVIO_REDIRECT_URI,
            "code": code,
        },
    )
    store_tokens(connection, data)


def access_token(session: Session):
    connection = session.exec(
        select(ShippingConnection)
        .where(ShippingConnection.environment == environment())
        .with_for_update()
    ).first()
    if not connection or not connection.access_ciphertext:
        raise HTTPException(
            503,
            "Conecte a conta Melhor Envio no painel administrativo para consultar fretes",
        )
    if not connection.expires_at or aware(
        connection.expires_at
    ) <= utc_now() + timedelta(minutes=5):
        oauth_config()
        data = transport(
            "POST",
            "/oauth/token",
            body={
                "grant_type": "refresh_token",
                "client_id": settings.MELHOR_ENVIO_CLIENT_ID,
                "client_secret": settings.MELHOR_ENVIO_CLIENT_SECRET,
                "refresh_token": decrypt(connection.refresh_ciphertext),
            },
        )
        store_tokens(connection, data)
        session.add(connection)
        session.commit()
    return decrypt(connection.access_ciphertext)


def request(session, method, path, **kwargs):
    return transport(method, path, token=access_token(session), **kwargs)


def origin_postal_code():
    """Calculation only requires origin CEP; full sender is checked at checkout."""
    try:
        data = json.loads(settings.MELHOR_ENVIO_SENDER)
        postal_code = data.get("postal_code", "") if isinstance(data, dict) else ""
    except (ValueError, TypeError):
        raise HTTPException(503, "Configure o CEP de origem em MELHOR_ENVIO_SENDER")
    if (
        not isinstance(postal_code, str)
        or len(postal_code) != 8
        or not postal_code.isascii()
        or not postal_code.isdigit()
    ):
        raise HTTPException(
            503, "Configure um CEP de origem válido em MELHOR_ENVIO_SENDER"
        )
    return postal_code


def sender():
    try:
        data = json.loads(settings.MELHOR_ENVIO_SENDER)
    except (ValueError, TypeError):
        raise HTTPException(503, "Configure o remetente em MELHOR_ENVIO_SENDER")
    required = (
        "name",
        "email",
        "phone",
        "address",
        "number",
        "district",
        "city",
        "state_abbr",
        "postal_code",
        "company_document",
        "state_register",
    )
    if not isinstance(data, dict) or any(not data.get(key) for key in required):
        raise HTTPException(
            503,
            "Complete os dados do remetente, CNPJ e inscrição estadual em MELHOR_ENVIO_SENDER",
        )
    if len(str(data["postal_code"])) != 8 or not str(data["postal_code"]).isdigit():
        raise HTTPException(503, "CEP do remetente inválido")
    return data


def resolve_product(item, session):
    if item.id:
        try:
            product = session.get(Product, UUID(item.id))
            if product:
                return product
        except ValueError:
            pass
    if item.slug:
        product = session.exec(select(Product).where(Product.slug == item.slug)).first()
        if product:
            return product
    return session.exec(select(Product).where(Product.name == item.name)).first()


def resolved_items(items, session):
    merged = {}
    for item in items:
        product = resolve_product(item, session)
        if not product or not product.active:
            raise HTTPException(404, f"Produto '{item.name}' não encontrado ou inativo")
        if any(
            not getattr(product, "shipping_" + key)
            for key in ("width", "height", "length", "weight")
        ):
            raise HTTPException(
                409,
                f"Peso e dimensões de '{product.name}' precisam ser cadastrados pela loja",
            )
        key = str(product.id)
        if key not in merged:
            merged[key] = {
                "id": key,
                "name": product.name,
                "unit_price": float(
                    Decimal(str(product.price)).quantize(Decimal("0.01"))
                ),
                "quantity": 0,
                **{
                    k: getattr(product, "shipping_" + k)
                    for k in ("width", "height", "length", "weight")
                },
            }
        merged[key]["quantity"] += item.quantity
        if merged[key]["quantity"] > 100:
            raise HTTPException(422, "Quantidade máxima por produto excedida")
    return sorted(merged.values(), key=lambda item: item["id"])


def normalize_services(data, subtotal):
    if not isinstance(data, list):
        raise HTTPException(502, "Resposta de cotação inválida")
    services = []
    for item in data:
        if not isinstance(item, dict) or item.get("error"):
            continue
        try:
            cost = Decimal(str(item.get("custom_price", item.get("price"))))
            time = int(item.get("custom_delivery_time", item.get("delivery_time")))
            interval = item.get("custom_delivery_range") or {"min": time, "max": time}
            packages = item["packages"]
            if not cost.is_finite() or cost < 0 or time < 0 or not packages:
                continue
            # Require usable packages; never fabricate dimensions or packing.
            for package in packages:
                if (
                    any(
                        float(package["dimensions"][k]) <= 0
                        for k in ("width", "height", "length")
                    )
                    or float(package["weight"]) <= 0
                ):
                    raise ValueError()
            services.append(
                {
                    "id": int(item["id"]),
                    "name": item["name"],
                    "company": item["company"]["name"],
                    "cost": float(cost.quantize(Decimal("0.01"))),
                    "price": float(cost.quantize(Decimal("0.01"))),
                    "delivery_min": int(interval["min"]),
                    "delivery_max": int(interval["max"]),
                    "packages": packages,
                }
            )
        except (KeyError, TypeError, ValueError, InvalidOperation):
            continue
    services.sort(key=lambda service: (service["cost"], service["delivery_max"]))
    threshold = settings.MELHOR_ENVIO_FREE_SHIPPING_THRESHOLD
    if services and threshold > 0 and subtotal >= Decimal(str(threshold)):
        services[0][
            "price"
        ] = 0.0  # Store sponsors the cheapest service, not every express service.
    if not services:
        raise HTTPException(
            422, "Nenhuma transportadora disponível para este CEP e estes produtos"
        )
    return services


def create_quote(payload, session):
    origin = origin_postal_code()
    items = resolved_items(payload.items, session)
    subtotal = sum(
        (Decimal(str(item["unit_price"])) * item["quantity"] for item in items),
        Decimal("0"),
    )
    data = request(
        session,
        "POST",
        "/api/v2/me/shipment/calculate",
        body={
            "from": {"postal_code": origin},
            "to": {"postal_code": payload.postal_code},
            "products": [
                {
                    "id": item["id"],
                    "width": item["width"],
                    "height": item["height"],
                    "length": item["length"],
                    "weight": item["weight"],
                    "insurance_value": item["unit_price"],
                    "quantity": item["quantity"],
                }
                for item in items
            ],
            "options": {"receipt": False, "own_hand": False},
            "services": settings.MELHOR_ENVIO_SERVICES,
        },
    )
    quote = ShippingQuote(
        environment=environment(),
        origin_postal_code=origin,
        postal_code=payload.postal_code,
        items=items,
        services=normalize_services(data, subtotal),
        subtotal=subtotal,
        expires_at=utc_now()
        + timedelta(minutes=settings.MELHOR_ENVIO_QUOTE_TTL_MINUTES),
    )
    session.add(quote)
    session.commit()
    session.refresh(quote)
    return {
        "id": str(quote.id),
        "postal_code": quote.postal_code,
        "subtotal": float(subtotal),
        "expires_at": aware(quote.expires_at),
        "item_prices": [
            {"name": item["name"], "unit_price": item["unit_price"]}
            for item in quote.items
        ],
        "services": [
            {k: v for k, v in service.items() if k != "packages"}
            for service in quote.services
        ],
    }


def validate_selection(selection, items, address, session):
    if not selection:
        raise HTTPException(422, "Calcule e escolha o frete antes de pagar")
    quote = session.get(ShippingQuote, selection.quote_id)
    if (
        not quote
        or quote.environment != environment()
        or aware(quote.expires_at) <= utc_now()
    ):
        raise HTTPException(409, "A cotação expirou. Calcule o frete novamente.")
    if (
        quote.postal_code != address.cep.replace("-", "")
        or quote.origin_postal_code != sender()["postal_code"]
    ):
        raise HTTPException(409, "O endereço mudou. Calcule o frete novamente.")
    if quote.items != resolved_items(items, session):
        raise HTTPException(
            409,
            "Os produtos, preços ou quantidades mudaram. Calcule o frete novamente.",
        )
    service = next(
        (
            service
            for service in quote.services
            if service["id"] == selection.service_id
        ),
        None,
    )
    if not service:
        raise HTTPException(422, "Serviço de entrega não pertence à cotação")
    return quote, service


def new_shipment(payment, quote, service, selection, address):
    recipient = {
        "name": selection.recipient_name,
        "email": str(selection.recipient_email),
        "phone": selection.recipient_phone,
        "document": selection.recipient_document,
        "address": address.street,
        "number": address.number,
        "complement": address.complement or "",
        "district": address.neighborhood,
        "city": address.city,
        "state_abbr": address.state,
        "postal_code": quote.postal_code,
        "country_id": "BR",
    }
    return Shipment(
        payment_id=payment.id,
        quote_id=quote.id,
        service_id=service["id"],
        service_name=service["name"],
        company_name=service["company"],
        cost=Decimal(str(service["cost"])),
        customer_price=Decimal(str(service["price"])),
        delivery_min=service["delivery_min"],
        delivery_max=service["delivery_max"],
        recipient=recipient,
        sender=sender(),
    )


def shipment_out(shipment, payment, *, admin=False):
    if not shipment:
        return None
    result = {
        "id": str(shipment.id),
        "order_id": str(payment.order_id),
        "service": shipment.service_name,
        "company": shipment.company_name,
        "price": float(shipment.customer_price),
        "delivery_min": shipment.delivery_min,
        "delivery_max": shipment.delivery_max,
        "status": shipment.status,
        "labels": [
            {
                "id": label["id"],
                "status": label.get("status"),
                "tracking": label.get("tracking"),
            }
            for label in shipment.labels
        ],
        "updated_at": shipment.updated_at,
    }
    if admin:
        result.update(
            {
                "payment_status": str(payment.status),
                "recipient_name": shipment.recipient.get("name"),
                "cost": float(shipment.cost),
                "invoice_key": shipment.invoice_key,
                "print_url": shipment.print_url,
                "last_error": shipment.last_error,
            }
        )
    return result
