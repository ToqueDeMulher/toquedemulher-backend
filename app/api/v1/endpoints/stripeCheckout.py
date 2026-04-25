from fastapi import APIRouter, HTTPException
from uuid import uuid4
from decimal import Decimal
from app.schemas.create_checkout import CreateCheckoutRequest, CheckoutResponse
from app.services.checkoutService import create_checkout_session
from app.models.payment import Payment, PaymentStatus
from app.core.db import _SessionDep
from app.api.dependencies import CurrentUser
from app.models.paymentItem import PaymentItem
from sqlmodel import select
from app.models.address import Address
from app.models.product import Product
from app.models.stock import Stock


router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(payload: CreateCheckoutRequest, session: _SessionDep, user: CurrentUser): #Checkout é literalmente a tela de pagamento
     
    # Verificação de produto e estoque

    total_amount = Decimal("0")

    with session.begin():
        for item in payload.items:

            product = session.exec(select(Product).where(Product.slug == item.slug)).first()

            if not product:
                raise HTTPException(status_code=404, detail=f"Produto '{item.slug}' não encontrado")

            # 🔒 trava o estoque (EVITA concorrência)
            stock = session.exec(select(Stock).where(Stock.product_id == product.id)
                .with_for_update()
            ).first()

            if not stock:
                raise HTTPException(status_code=400, detail=f"Produto '{product.name}' sem estoque cadastrado")

            if stock.total_quantity < item.quantity:
                raise HTTPException(status_code=400, detail=f"Estoque insuficiente para '{product.name}'"
                )

            total_amount += product.price * item.quantity

            stock.total_quantity -= item.quantity
    
    
    
    address = session.exec(
        select(Address).where(
            Address.id == payload.address_id,
            Address.user_id == user.id
        )
        ).first()
    
    if not address:
        raise HTTPException(404, detail="Endereço não encontrado ou não pertence ao usuário" )

    order_id = uuid4()

    try:
        stripe_session = create_checkout_session(payload, order_id)

        payment = Payment(
            order_id=order_id,
            user_id=user.id,
            address_id= payload.address_id,
            payer_email=user.email,
            amount=total_amount,
            provider_session_id=stripe_session.id,
            status=PaymentStatus.PENDING
        )
        session.add(payment)
        session.flush()

        for item in payload.items:
            payment_item = PaymentItem(
                payment_id=payment.id,
                title=item.name,
                product_url=item.product_url,
                unit_price=Decimal(str(item.unit_price)),
                quantity=item.quantity
            )
            session.add(payment_item)

        session.commit()
        session.refresh(payment)
        

        print("Payment salvo:", payment)

    except Exception as e:
        session.rollback()
        print("Erro ao salvar payment:", e)
        raise HTTPException(500, detail="Erro ao criar checkout")
    

    return CheckoutResponse(client_secret= stripe_session.client_secret,
                            session_id = stripe_session.id)