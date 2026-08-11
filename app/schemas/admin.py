from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AdminKpiResponse(BaseModel):
    key: str
    title: str
    value: str
    detail: str


class AdminMonthlyRevenueResponse(BaseModel):
    label: str
    current_year: float
    previous_year: float


class AdminStatusDistributionResponse(BaseModel):
    status: str
    label: str
    count: int
    percent: int


class AdminRecentOrderResponse(BaseModel):
    id: str
    order_id: str
    customer: str
    date: datetime
    total: float
    status: str
    status_label: str
    items_count: int
    summary: str


class AdminTopProductResponse(BaseModel):
    product_id: Optional[str] = None
    name: str
    quantity: int
    revenue: float
    percent: int


class AdminDashboardResponse(BaseModel):
    kpis: list[AdminKpiResponse]
    monthly_revenue: list[AdminMonthlyRevenueResponse]
    status_distribution: list[AdminStatusDistributionResponse]
    recent_orders: list[AdminRecentOrderResponse]
    top_products: list[AdminTopProductResponse]
