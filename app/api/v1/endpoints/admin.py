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
    AdminSalesOverviewResponse,
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
    PaymentStatus.APPROVED.value: "Pago",
    PaymentStatus.REJECTED.value: "Recusado",
    PaymentStatus.CANCELLED.value: "Cancelado",
    PaymentStatus.REFUNDED.value: "Reembolsado",
}


def _as_float(value: Decimal | float | int) -> float:
    return float(value)


def _money(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _compact_money(value: float) -> str:
    sign = "-" if value < 0 else ""
    absolute_value = abs(value)
    if absolute_value >= 1_000_000:
        return f"{sign}R$ {absolute_value / 1_000_000:.1f} mi".replace(".", ",")
    if absolute_value >= 1_000:
        return f"{sign}R$ {absolute_value / 1_000:.1f} mil".replace(".", ",")
    return _money(value)


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _same_year(value: datetime, year: int) -> bool:
    return _normalize_datetime(value).year == year


def _status_value(status: str | PaymentStatus) -> str:
    if isinstance(status, PaymentStatus):
        return status.value
    return str(status)


def _payment_amount(payment: Payment) -> float:
    return _as_float(payment.amount)


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
    products_by_id = {product.id: product for product in products}
    items_by_payment_id: dict[UUID, list[PaymentItem]] = defaultdict(list)
    for item in payment_items:
        items_by_payment_id[item.payment_id].append(item)

    status_counts = {status: 0 for status in STATUS_LABELS}
    status_amounts = {status: 0.0 for status in STATUS_LABELS}
    for payment in payments:
        status = _status_value(payment.status)
        status_counts[status] = status_counts.get(status, 0) + 1
        status_amounts[status] = status_amounts.get(status, 0.0) + _payment_amount(
            payment
        )

    approved_payments = [
        payment
        for payment in payments
        if _status_value(payment.status) == PaymentStatus.APPROVED.value
    ]
    refunded_payments = [
        payment
        for payment in payments
        if _status_value(payment.status) == PaymentStatus.REFUNDED.value
    ]
    pending_payments = [
        payment
        for payment in payments
        if _status_value(payment.status) == PaymentStatus.PENDING.value
    ]

    gross_sales = sum(_payment_amount(payment) for payment in approved_payments)
    refunded_sales = sum(_payment_amount(payment) for payment in refunded_payments)
    pending_sales = sum(_payment_amount(payment) for payment in pending_payments)
    net_sales = gross_sales - refunded_sales
    average_order_value = (
        gross_sales / len(approved_payments) if approved_payments else 0.0
    )

    approved_payments_by_id = {payment.id: payment for payment in approved_payments}
    approved_payment_ids = set(approved_payments_by_id)
    items_sold = sum(
        item.quantity for item in payment_items if item.payment_id in approved_payment_ids
    )

    active_customers = [
        user
        for user in users
        if user.role != "admin" and not user.disabled and user.deleted_at is None
    ]
    active_products = [product for product in products if product.active]
    low_stock_count = sum(1 for stock in stocks if stock.total_quantity <= 5)

    sales_overview = AdminSalesOverviewResponse(
        gross_sales=round(gross_sales, 2),
        net_sales=round(net_sales, 2),
        refunded_sales=round(refunded_sales, 2),
        pending_sales=round(pending_sales, 2),
        average_order_value=round(average_order_value, 2),
        total_orders=len(payments),
        paid_orders=status_counts.get(PaymentStatus.APPROVED.value, 0),
        refunded_orders=status_counts.get(PaymentStatus.REFUNDED.value, 0),
        pending_orders=status_counts.get(PaymentStatus.PENDING.value, 0),
        rejected_orders=status_counts.get(PaymentStatus.REJECTED.value, 0),
        cancelled_orders=status_counts.get(PaymentStatus.CANCELLED.value, 0),
        items_sold=items_sold,
    )

    kpis = [
        AdminKpiResponse(
            key="net_sales",
            title="Vendas líquidas",
            value=_compact_money(net_sales),
            detail=f"{len(approved_payments)} pagos, {len(refunded_payments)} reembolsados",
        ),
        AdminKpiResponse(
            key="orders",
            title="Pedidos",
            value=str(len(payments)),
            detail=f"{len(pending_payments)} pendentes no checkout",
        ),
        AdminKpiResponse(
            key="average_order_value",
            title="Ticket médio",
            value=_compact_money(average_order_value),
            detail="média dos pedidos pagos",
        ),
        AdminKpiResponse(
            key="items_sold",
            title="Itens vendidos",
            value=str(items_sold),
            detail="unidades em pedidos pagos",
        ),
        AdminKpiResponse(
            key="products",
            title="Produtos ativos",
            value=str(len(active_products)),
            detail=f"{low_stock_count} com estoque baixo",
        ),
        AdminKpiResponse(
            key="customers",
            title="Clientes ativos",
            value=str(len(active_customers)),
            detail="contas cliente habilitadas",
        ),
    ]

    monthly_totals = {
        current_year: [0.0 for _ in range(12)],
        previous_year: [0.0 for _ in range(12)],
    }
    current_order_counts = [0 for _ in range(12)]
    refunded_totals = [0.0 for _ in range(12)]

    for payment in payments:
        payment_date = _normalize_datetime(payment.created_at)
        status = _status_value(payment.status)

        if status == PaymentStatus.APPROVED.value and payment_date.year in monthly_totals:
            monthly_totals[payment_date.year][payment_date.month - 1] += _payment_amount(
                payment
            )

        if payment_date.year == current_year:
            if status == PaymentStatus.APPROVED.value:
                current_order_counts[payment_date.month - 1] += 1
            elif status == PaymentStatus.REFUNDED.value:
                refunded_totals[payment_date.month - 1] += _payment_amount(payment)

    monthly_revenue = [
        AdminMonthlyRevenueResponse(
            label=label,
            current_year=round(monthly_totals[current_year][index], 2),
            previous_year=round(monthly_totals[previous_year][index], 2),
            current_orders=current_order_counts[index],
            refunded_total=round(refunded_totals[index], 2),
        )
        for index, label in enumerate(MONTH_LABELS)
    ]

    total_payments = sum(status_counts.values())
    status_distribution = []
    if total_payments:
        status_distribution = [
            AdminStatusDistributionResponse(
                status=status,
                label=STATUS_LABELS.get(status, status.title()),
                count=count,
                amount=round(status_amounts.get(status, 0.0), 2),
                percent=round((count / total_payments) * 100),
            )
            for status, count in status_counts.items()
            if count > 0
        ]

    recent_orders = []
    for payment in payments[:12]:
        items = items_by_payment_id[payment.id]
        customer = users_by_id.get(payment.user_id)
        customer_name = (
            customer.name
            if customer and not customer.disabled and customer.deleted_at is None
            else payment.payer_email
        )
        recent_orders.append(
            AdminRecentOrderResponse(
                id=str(payment.id),
                order_id=str(payment.order_id),
                customer=customer_name,
                customer_email=payment.payer_email,
                date=payment.created_at,
                total=_payment_amount(payment),
                status=_status_value(payment.status),
                status_label=STATUS_LABELS.get(
                    _status_value(payment.status), _status_value(payment.status)
                ),
                provider=payment.provider,
                items_count=sum(item.quantity for item in items),
                summary=_build_order_summary(items),
            )
        )

    product_sales: dict[str, dict[str, object]] = {}
    for item in payment_items:
        payment = approved_payments_by_id.get(item.payment_id)
        if payment is None:
            continue

        product = products_by_id.get(item.product_id)
        key = str(item.product_id) if item.product_id else item.title.lower()
        current = product_sales.setdefault(
            key,
            {
                "product_id": str(item.product_id) if item.product_id else None,
                "name": product.name if product else item.title,
                "slug": product.slug if product else None,
                "quantity": 0,
                "orders": set(),
                "revenue": 0.0,
                "last_sale_at": None,
            },
        )
        current["quantity"] = int(current["quantity"]) + item.quantity
        current["revenue"] = float(current["revenue"]) + _as_float(
            item.unit_price
        ) * item.quantity
        current_orders = current["orders"]
        if isinstance(current_orders, set):
            current_orders.add(item.payment_id)
        last_sale_at = current["last_sale_at"]
        if not isinstance(last_sale_at, datetime) or payment.created_at > last_sale_at:
            current["last_sale_at"] = payment.created_at

    top_product_rows = sorted(
        product_sales.values(),
        key=lambda row: (int(row["quantity"]), float(row["revenue"])),
        reverse=True,
    )[:8]
    total_sold_quantity = sum(int(row["quantity"]) for row in product_sales.values())
    top_products = []
    for row in top_product_rows:
        quantity = int(row["quantity"])
        revenue = float(row["revenue"])
        orders = row["orders"]
        orders_count = len(orders) if isinstance(orders, set) else 0
        top_products.append(
            AdminTopProductResponse(
                product_id=row["product_id"],
                name=str(row["name"]),
                slug=row["slug"],
                quantity=quantity,
                orders_count=orders_count,
                revenue=round(revenue, 2),
                average_unit_price=round(revenue / quantity, 2) if quantity else 0.0,
                percent=round((quantity / total_sold_quantity) * 100)
                if total_sold_quantity
                else 0,
                last_sale_at=row["last_sale_at"],
            )
        )

    return AdminDashboardResponse(
        generated_at=now,
        kpis=kpis,
        sales_overview=sales_overview,
        monthly_revenue=monthly_revenue,
        status_distribution=status_distribution,
        recent_orders=recent_orders,
        top_products=top_products,
    )
