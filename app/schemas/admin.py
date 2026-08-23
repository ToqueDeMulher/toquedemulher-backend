from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AdminKpiResponse(BaseModel):
    key: str
    title: str
    value: str
    detail: str


class AdminSalesOverviewResponse(BaseModel):
    gross_sales: float
    net_sales: float
    refunded_sales: float
    pending_sales: float
    average_order_value: float
    total_orders: int
    paid_orders: int
    refunded_orders: int
    pending_orders: int
    rejected_orders: int
    cancelled_orders: int
    items_sold: int


class AdminMonthlyRevenueResponse(BaseModel):
    label: str
    current_year: float
    previous_year: float
    current_orders: int
    refunded_total: float


class AdminStatusDistributionResponse(BaseModel):
    status: str
    label: str
    count: int
    amount: float
    percent: int


class AdminRecentOrderResponse(BaseModel):
    id: str
    order_id: str
    customer: str
    customer_email: str
    date: datetime
    total: float
    status: str
    status_label: str
    provider: str
    items_count: int
    summary: str


class AdminTopProductResponse(BaseModel):
    product_id: Optional[str] = None
    name: str
    slug: Optional[str] = None
    quantity: int
    orders_count: int
    revenue: float
    average_unit_price: float
    percent: int
    last_sale_at: Optional[datetime] = None


class AdminDashboardResponse(BaseModel):
    generated_at: datetime
    kpis: list[AdminKpiResponse]
    sales_overview: AdminSalesOverviewResponse
    monthly_revenue: list[AdminMonthlyRevenueResponse]
    status_distribution: list[AdminStatusDistributionResponse]
    recent_orders: list[AdminRecentOrderResponse]
    top_products: list[AdminTopProductResponse]
