from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.user import User
from app.models.cart import Cart, CartItem
from app.models.product import Product, ProductVariant
from app.schemas.cart import CartOut, CartItemAdd, CartItemUpdate, CartItemOut

from app.api.v1.deps import get_current_active_user

router = APIRouter(prefix="/cart", tags=["Carrinho"])


def _build_cart_out(cart: Cart) -> CartOut:
    """Constrói o schema de saída do carrinho com dados dos produtos."""
    items_out = []
    for item in cart.items:
        product = item.product
        primary_image = next((img.url for img in product.images if img.is_primary), None)
        if not primary_image and product.images:
            primary_image = product.images[0].url

        items_out.append(CartItemOut(
            id=item.id,
            product_id=item.product_id,
            variant_id=item.variant_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            subtotal=item.subtotal,
            product_name=product.name,
            product_image=primary_image,
            variant_name=item.variant.name if item.variant else None,
        ))

    return CartOut(
        id=cart.id,
        user_id=cart.user_id,
        items=items_out,
        total=cart.total,
        item_count=cart.item_count,
    )


@router.get("/", response_model=CartOut)
def get_cart(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retorna o carrinho do usuário autenticado."""
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return _build_cart_out(cart)


@router.post("/items", response_model=CartOut, status_code=status.HTTP_201_CREATED)
def add_item(
    item_in: CartItemAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Adiciona um item ao carrinho."""
    # Verificar produto
    product = db.query(Product).filter(Product.id == item_in.product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")

    # Verificar variante e estoque
    unit_price = product.price
    if item_in.variant_id:
        variant = db.query(ProductVariant).filter(
            ProductVariant.id == item_in.variant_id,
            ProductVariant.product_id == product.id,
        ).first()
        if not variant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variante não encontrada.")
        if variant.stock_quantity < item_in.quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estoque insuficiente.")
        if variant.price:
            unit_price = variant.price
    else:
        if product.stock_quantity < item_in.quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estoque insuficiente.")

    # Obter ou criar carrinho
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.add(cart)
        db.flush()

    # Verificar se item já existe no carrinho
    existing_item = db.query(CartItem).filter(
        CartItem.cart_id == cart.id,
        CartItem.product_id == item_in.product_id,
        CartItem.variant_id == item_in.variant_id,
    ).first()

    if existing_item:
        existing_item.quantity += item_in.quantity
        existing_item.unit_price = unit_price
    else:
        new_item = CartItem(
            cart_id=cart.id,
            product_id=item_in.product_id,
            variant_id=item_in.variant_id,
            quantity=item_in.quantity,
            unit_price=unit_price,
        )
        db.add(new_item)

    db.commit()
    db.refresh(cart)
    return _build_cart_out(cart)


@router.put("/items/{item_id}", response_model=CartOut)
def update_item(
    item_id: int,
    item_update: CartItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Atualiza a quantidade de um item no carrinho."""
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    if not cart:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carrinho não encontrado.")

    item = db.query(CartItem).filter(
        CartItem.id == item_id, CartItem.cart_id == cart.id
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado.")

    if item_update.quantity <= 0:
        db.delete(item)
    else:
        item.quantity = item_update.quantity

    db.commit()
    db.refresh(cart)
    return _build_cart_out(cart)


@router.delete("/items/{item_id}", response_model=CartOut)
def remove_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Remove um item do carrinho."""
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    if not cart:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carrinho não encontrado.")

    item = db.query(CartItem).filter(
        CartItem.id == item_id, CartItem.cart_id == cart.id
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado.")

    db.delete(item)
    db.commit()
    db.refresh(cart)
    return _build_cart_out(cart)


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
def clear_cart(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Esvazia o carrinho do usuário."""
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    if cart:
        db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
        db.commit()
