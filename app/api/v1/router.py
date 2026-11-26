from fastapi import APIRouter
from app.api.v1.endpoints import (
    abacatepay_webhook,
    announcements,
    addressRouter,
    shipping,
    brasilApi,
    admin,
    login,
    paymentMethodRouter,
    product,
    stock,
    payments,
    supplier,
    supplierProduct,
    user,
    weebhook,
    contact,
)
from app.core.settings import settings

api_router = APIRouter(prefix=settings.API_V1_PREFIX)

api_router.include_router(admin.router)
api_router.include_router(announcements.router)
api_router.include_router(product.router)
api_router.include_router(payments.router)
api_router.include_router(user.router)
api_router.include_router(weebhook.router)
api_router.include_router(abacatepay_webhook.router)
api_router.include_router(login.router)
api_router.include_router(addressRouter.router)
api_router.include_router(paymentMethodRouter.router)
api_router.include_router(stock.router)
api_router.include_router(supplier.router)
api_router.include_router(supplierProduct.router)

api_router.include_router(shipping.router)
api_router.include_router(brasilApi.router)
api_router.include_router(contact.router)
