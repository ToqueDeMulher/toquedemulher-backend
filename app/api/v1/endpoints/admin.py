from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from fastapi import APIRouter
from sqlmodel import select

from app.api.dependencies import AdminUser
from app.core.db import _SessionDep
from app.core.time import utc_now
from app.models.payment import Payment, PaymentStatus
from app.models.paymentItem import PaymentItem
from app.models.product import Product
from app.models.stock import Stock
from app.models.user import UserInDB
from app.schemas.admin import (
    AdminDashboardResponse,
    AdminKpiResponse,
    AdminMonthlyRevenueResponse,
    AdminRecentOrderResponse,
    AdminStatusDistributionResponse,
    AdminTopProductResponse,
)

router = APIRouter(prefix="/admin", tags=["admin"])

MONTH_LABELS = [
    "Jan",
    "Fev",
    "Mar",
    "Abr",
    "Mai",
    "Jun",
    "Jul",
    "Ago",
    "Set",
    "Out",
    "Nov",
    "Dez",
]

STATUS_LABELS = {
    PaymentStatus.PENDING.value: "Pendente",
    PaymentStatus.APPROVED.value: "Aprovado",
    PaymentStatus.REJECTED.value: "Recusado",
    PaymentStatus.CANCELLED.value: "Cancelado",
    PaymentStatus.REFUNDED.value: "Reembolsado",
}


def _as_float(value: Decimal | float | int) -> float:
    return float(value)


def _money(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _compact_money(value: float) -> str:
    if value >= 1_000_000:
        return f"R$ {value / 1_000_000:.1f} mi".replace(".", ",")
    if value >= 1_000:
        return f"R$ {value / 1_000:.1f} mil".replace(".", ",")
    return _money(value)


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _same_year(value: datetime, year: int) -> bool:
    return _normalize_datetime(value).year == year


def _build_order_summary(items: Iterable[PaymentItem]) -> str:
    ordered_items = list(items)
    if not ordered_items:
        return "Pedido sem itens registrados"

    first_items = ", ".join(
        f"{item.quantity}x {item.title}" for item in ordered_items[:2]
    )
    remaining = len(ordered_items) - 2
    if remaining > 0:
        return f"{first_items} +{remaining}"
    return first_items


@router.get("/dashboard", response_model=AdminDashboardResponse)
def get_admin_dashboard(session: _SessionDep, _: AdminUser):
    now = utc_now()
    current_year = now.year
    previous_year = current_year - 1

    users = session.exec(select(UserInDB)).all()
    products = session.exec(select(Product)).all()
    stocks = session.exec(select(Stock)).all()
    payments = session.exec(
        select(Payment).order_by(Payment.created_at.desc())
    ).all()
    payment_items = session.exec(select(PaymentItem)).all()

    users_by_id = {user.id: user for user in users}
    payments_by_id = {payment.id: payment for payment in payments}
    items_by_payment_id: dict[UUID, list[PaymentItem]] = defaultdict(list)
    for item in payment_items:
        items_by_payment_id[item.payment_id].append(item)

    active_customers = [
        user
        for user in users
        if user.role != "admin" and not user.disabled and user.deleted_at is None
    ]
    active_products = [product for product in products if product.active]
    low_stock_count = sum(1 for stock in stocks if stock.total_quantity <= 5)
    current_year_payments = [
        payment for payment in payments if _same_year(payment.created_at, current_year)
    ]
    approved_current_year_payments = [
        payment
        for payment in current_year_payments
        if payment.status == PaymentStatus.APPROVED.value
    ]
    approved_revenue = sum(
        _as_float(payment.amount) for payment in approved_current_year_payments
    )

    kpis = [
        AdminKpiResponse(
            key="customers",
            title="Clientes ativos",
            value=str(len(active_customers)),
            detail="contas cliente habilitadas",
        ),
        AdminKpiResponse(
            key="products",
            title="Produtos ativos",
            value=str(len(active_products)),
            detail=f"{low_stock_count} com estoque baixo",
        ),
        AdminKpiResponse(
            key="orders",
            title="Pedidos no ano",
            value=str(len(current_year_payments)),
            detail=f"{len(payments)} pagamentos registrados",
        ),
        AdminKpiResponse(
            key="revenue",
            title="Receita aprovada",
            value=_compact_money(approved_revenue),
            detail="pagamentos aprovados no ano",
        ),
    ]

    monthly_totals = {
        current_year: [0.0 for _ in range(12)],
        previous_year: [0.0 for _ in range(12)],
    }
    for payment in payments:
        payment_date = _normalize_datetime(payment.created_at)
        if payment.status != PaymentStatus.APPROVED.value:
            continue
        if payment_date.year not in monthly_totals:
            continue
        monthly_totals[payment_date.year][payment_date.month - 1] += _as_float(
            payment.amount
        )

    monthly_revenue = [
        AdminMonthlyRevenueResponse(
            label=label,
            current_year=round(monthly_totals[current_year][index], 2),
            previous_year=round(monthly_totals[previous_year][index], 2),
        )
        for index, label in enumerate(MONTH_LABELS)
    ]

    status_counts = {
        status: sum(1 for payment in payments if payment.status == status)
        for status in STATUS_LABELS
    }
    total_payments = sum(status_counts.values())
    status_distribution = []
    if total_payments:
        status_distribution = [
            AdminStatusDistributionResponse(
                status=status,
                label=label,
                count=count,
                percent=round((count / total_payments) * 100),
            )
            for status, label in STATUS_LABELS.items()
            if (count := status_counts[status]) > 0
        ]

    recent_orders = []
    for payment in payments[:6]:
        items = items_by_payment_id[payment.id]
        customer = users_by_id.get(payment.user_id)
        recent_orders.append(
            AdminRecentOrderResponse(
                id=str(payment.id),
                order_id=str(payment.order_id),
                customer=customer.name if customer and not customer.disabled else payment.payer_email,
                date=payment.created_at,
                total=_as_float(payment.amount),
                status=payment.status,
                status_label=STATUS_LABELS.get(payment.status, payment.status),
                items_count=sum(item.quantity for item in items),
                summary=_build_order_summary(items),
            )
        )

    approved_payment_ids = {
        payment.id
        for payment in payments
        if payment.status == PaymentStatus.APPROVED.value
    }
    product_sales: dict[str, dict[str, object]] = {}
    for item in payment_items:
        if item.payment_id not in approved_payment_ids:
            continue

        key = str(item.product_id)
        current = product_sales.setdefault(
            key,
            {
                "product_id": key,
                "name": item.title,
                "quantity": 0,
                "revenue": 0.0,
            },
        )
        current["quantity"] = int(current["quantity"]) + item.quantity
        current["revenue"] = float(current["revenue"]) + _as_float(
            item.unit_price
        ) * item.quantity

    top_product_rows = sorted(
        product_sales.values(),
        key=lambda row: (int(row["quantity"]), float(row["revenue"])),
        reverse=True,
    )[:5]
    max_quantity = max(
        [int(row["quantity"]) for row in top_product_rows],
        default=0,
    )
    top_products = [
        AdminTopProductResponse(
            product_id=str(row["product_id"]),
            name=str(row["name"]),
            quantity=int(row["quantity"]),
            revenue=round(float(row["revenue"]), 2),
            percent=round((int(row["quantity"]) / max_quantity) * 100)
            if max_quantity
            else 0,
        )
        for row in top_product_rows
    ]

    return AdminDashboardResponse(
        kpis=kpis,
        monthly_revenue=monthly_revenue,
        status_distribution=status_distribution,
        recent_orders=recent_orders,
        top_products=top_products,
    )
