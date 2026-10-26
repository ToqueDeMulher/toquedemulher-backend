"""Explicit label stages; no financial operation is automatically retried."""

from decimal import Decimal, InvalidOperation
from fastapi import HTTPException
from app.core.time import utc_now
from app.models.shipping import ShippingQuote
from app.services import melhor_envio as me

PAID_STATUSES = {
    "released",
    "paid",
    "generated",
    "printed",
    "posted",
    "delivered",
    "undelivered",
}
READY_STATUSES = {"generated", "printed", "posted", "delivered", "undelivered"}


def persist(session, shipment, status=None):
    if status:
        shipment.status = status
    shipment.updated_at = utc_now()
    session.add(shipment)
    session.commit()
    session.refresh(shipment)


def fail(session, shipment, error):
    shipment.last_error = (
        str(error.detail)
        if isinstance(error, HTTPException)
        else "Não foi possível concluir a operação. Confira a etiqueta no Melhor Envio."
    )
    persist(session, shipment, "needs_review")


def prepare(session, shipment, payment, invoice_key):
    if shipment.status != "pending":
        raise HTTPException(
            409, "Etiqueta já iniciada. Atualize o status antes de repetir."
        )
    if str(payment.status) != "approved":
        raise HTTPException(409, "Aguarde a confirmação do pagamento do pedido")
    quote = session.get(ShippingQuote, shipment.quote_id)
    if quote.environment != me.environment():
        raise HTTPException(409, "Este envio pertence a outro ambiente Melhor Envio")
    service = next(
        service for service in quote.services if service["id"] == shipment.service_id
    )
    packages = service["packages"]
    single_volume = shipment.company_name.lower() in {
        "correios",
        "j&t",
        "j&t express",
        "loggi",
    }
    groups = [[package] for package in packages] if single_volume else [packages]
    calls = []
    declared_quantities = {}
    for group in groups:
        quantities = {}
        for package in group:
            for item in package.get("products", []):
                quantities[item["id"]] = quantities.get(item["id"], 0) + int(
                    item["quantity"]
                )
        if len(groups) == 1:
            quantities = {item["id"]: item["quantity"] for item in quote.items}
        if not quantities or any(
            key not in {item["id"] for item in quote.items} for key in quantities
        ):
            raise HTTPException(
                502, "A cotação não informou os produtos de cada pacote"
            )
        for key, quantity in quantities.items():
            if quantity <= 0:
                raise HTTPException(502, "Quantidade de pacote inválida na cotação")
            declared_quantities[key] = declared_quantities.get(key, 0) + quantity
        products = [
            {
                "name": item["name"],
                "quantity": quantities[item["id"]],
                "unitary_value": item["unit_price"],
            }
            for item in quote.items
            if item["id"] in quantities
        ]
        insurance = sum(
            (
                Decimal(str(item["unitary_value"])) * item["quantity"]
                for item in products
            ),
            Decimal("0"),
        )
        calls.append(
            {
                "service": shipment.service_id,
                "from": shipment.sender,
                "to": shipment.recipient,
                "products": products,
                "volumes": [
                    {**package["dimensions"], "weight": float(package["weight"])}
                    for package in group
                ],
                "options": {
                    "insurance_value": float(insurance),
                    "receipt": False,
                    "own_hand": False,
                    "reverse": False,
                    "non_commercial": False,
                    "invoice": {"key": invoice_key},
                    "platform": "Toque de Mulher",
                    "tags": [{"tag": str(payment.order_id)}],
                },
            }
        )
    if declared_quantities != {item["id"]: item["quantity"] for item in quote.items}:
        raise HTTPException(
            502, "A distribuição dos produtos nos pacotes está incompleta"
        )
    # Commit the operation marker before contacting the provider. Concurrent
    # requests and crash recovery cannot blindly create/pay the same labels.
    shipment.invoice_key = invoice_key
    shipment.last_error = None
    persist(session, shipment, "creating")
    try:
        for payload in calls:
            data = me.request(session, "POST", "/api/v2/me/cart", body=payload)
            if not isinstance(data, dict) or not data.get("id"):
                raise HTTPException(502, "Melhor Envio não retornou o ID da etiqueta")
            shipment.labels = [
                *shipment.labels,
                {
                    "id": data["id"],
                    "status": data.get("status", "pending"),
                    "tracking": data.get("tracking"),
                },
            ]
            persist(session, shipment)
            try:
                actual_cost = Decimal(str(data["price"]))
                if not actual_cost.is_finite() or actual_cost < 0:
                    raise ValueError()
            except (KeyError, InvalidOperation, ValueError):
                raise HTTPException(
                    502,
                    "O valor da etiqueta não foi confirmado. Confira o status antes de pagar.",
                )
            shipment.labels = [
                (
                    dict(label, cost=str(actual_cost.quantize(Decimal("0.01"))))
                    if label["id"] == data["id"]
                    else label
                )
                for label in shipment.labels
            ]
            shipment.cost = sum(
                (Decimal(label["cost"]) for label in shipment.labels), Decimal("0")
            )
            persist(session, shipment)
        persist(session, shipment, "carted")
    except Exception as error:
        fail(session, shipment, error)
        raise


def refresh(session, shipment):
    if not shipment.labels:
        raise HTTPException(
            409,
            "Nenhuma etiqueta registrada. Se a criação foi interrompida, confira o pedido no Melhor Envio e reconcilie os IDs.",
        )
    ids = [label["id"] for label in shipment.labels]
    data = me.request(
        session, "POST", "/api/v2/me/shipment/tracking", body={"orders": ids}
    )
    if not isinstance(data, dict) or any(
        not isinstance(data.get(label_id), dict) or not data[label_id].get("status")
        for label_id in ids
    ):
        raise HTTPException(
            502, "Melhor Envio não retornou o status de todas as etiquetas"
        )
    stored_costs = {label["id"]: label.get("cost") for label in shipment.labels}
    shipment.labels = [
        {
            "cost": stored_costs.get(label_id),
            "id": label_id,
            "status": data[label_id]["status"],
            "tracking": data[label_id].get("tracking")
            or data[label_id].get("melhorenvio_tracking"),
        }
        for label_id in ids
    ]
    previous_status = shipment.status
    statuses = {label["status"] for label in shipment.labels}
    quote = session.get(ShippingQuote, shipment.quote_id)
    service = next(
        service for service in quote.services if service["id"] == shipment.service_id
    )
    expected = (
        len(service["packages"])
        if shipment.company_name.lower() in {"correios", "j&t", "j&t express", "loggi"}
        else 1
    )
    if len(ids) != expected:
        status = "needs_review"
    elif statuses == {"delivered"}:
        status = "delivered"
    elif statuses <= {"posted", "delivered", "undelivered"}:
        status = "posted"
    elif statuses <= READY_STATUSES:
        status = "ready"
    elif statuses <= PAID_STATUSES:
        status = "generating" if previous_status == "generating" else "paid"
    elif statuses <= {"pending"}:
        status = "carted"
    elif statuses <= {"canceled", "cancelled"}:
        status = "cancelled"
    else:
        status = "needs_review"
    shipment.last_error = (
        None
        if status != "needs_review"
        else "Confira todas as etiquetas no Melhor Envio antes de continuar."
    )
    persist(session, shipment, status)


def pay(session, shipment, payment):
    if str(payment.status) != "approved":
        raise HTTPException(409, "Pedido ainda não está pago")
    if shipment.status != "carted":
        raise HTTPException(
            409, "Atualize o status: a etiqueta deve estar no carrinho para ser paga"
        )
    shipment.last_error = None
    persist(session, shipment, "paying")
    try:
        data = me.request(
            session,
            "POST",
            "/api/v2/me/shipment/checkout",
            body={"orders": [label["id"] for label in shipment.labels]},
        )
        if (
            not isinstance(data, dict)
            or data.get("purchase", {}).get("status") != "paid"
        ):
            raise HTTPException(
                502,
                "Pagamento da etiqueta não confirmado. Atualize o status antes de continuar.",
            )
        refresh(session, shipment)
    except Exception as error:
        fail(session, shipment, error)
        raise


def generate(session, shipment):
    if shipment.status != "paid":
        raise HTTPException(409, "A etiqueta deve estar paga antes da geração")
    shipment.last_error = None
    persist(session, shipment, "generating")
    try:
        ids = [label["id"] for label in shipment.labels]
        data = me.request(
            session, "POST", "/api/v2/me/shipment/generate", body={"orders": ids}
        )
        if not isinstance(data, dict) or any(
            not isinstance(data.get(label_id), dict)
            or data[label_id].get("status") is not True
            for label_id in ids
        ):
            raise HTTPException(
                502, "A geração de uma etiqueta não foi confirmada. Atualize o status."
            )
        # Generation is asynchronous: printing is only enabled by a later sync.
        persist(session, shipment, "generating")
    except Exception as error:
        fail(session, shipment, error)
        raise


def print_labels(session, shipment):
    if shipment.status not in {"ready", "posted", "delivered"}:
        raise HTTPException(
            409, "Aguarde a geração e atualize o status antes de imprimir"
        )
    data = me.request(
        session,
        "POST",
        "/api/v2/me/shipment/print",
        body={"mode": "private", "orders": [label["id"] for label in shipment.labels]},
    )
    if not isinstance(data, dict) or not str(data.get("url", "")).startswith(
        "https://"
    ):
        raise HTTPException(502, "Link de impressão indisponível")
    shipment.print_url = data["url"]
    persist(session, shipment)
