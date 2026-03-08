from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional
from app.db.base import get_db
from app.models.user import User
from app.models.product import Product, ProductImage, Category, ProductVariant, ProductStatus
from app.schemas.product import (
    ProductCreate, ProductUpdate, ProductOut, ProductListOut, PaginatedProducts,
    CategoryCreate, CategoryUpdate, CategoryOut,
    ProductVariantCreate, ProductVariantUpdate, ProductVariantOut,
    ProductImageOut,
)
from app.api.v1.deps import get_current_admin
from slugify import slugify
import os, uuid, shutil
from app.core.config import settings

router = APIRouter(prefix="/products", tags=["Produtos"])


# ─── Categorias ──────────────────────────────────────────────────────────────

@router.get("/categories", response_model=List[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    """Lista todas as categorias ativas."""
    return db.query(Category).filter(Category.is_active == True).all()


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    category_in: CategoryCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """[Admin] Cria uma nova categoria."""
    slug = slugify(category_in.name)
    # Garantir slug único
    existing = db.query(Category).filter(Category.slug == slug).first()
    if existing:
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    category = Category(slug=slug, **category_in.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.put("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int,
    category_update: CategoryUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """[Admin] Atualiza uma categoria."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada.")
    for field, value in category_update.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return category


# ─── Produtos ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=PaginatedProducts)
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: Optional[int] = None,
    brand: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    search: Optional[str] = None,
    featured: Optional[bool] = None,
    sort_by: str = Query("created_at", regex="^(created_at|price|name|average_rating)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    """Lista produtos com filtros, paginação e ordenação."""
    query = db.query(Product).filter(Product.status == ProductStatus.active)

    if category_id:
        query = query.filter(Product.category_id == category_id)
    if brand:
        query = query.filter(Product.brand.ilike(f"%{brand}%"))
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if search:
        query = query.filter(
            or_(
                Product.name.ilike(f"%{search}%"),
                Product.description.ilike(f"%{search}%"),
                Product.brand.ilike(f"%{search}%"),
            )
        )
    if featured is not None:
        query = query.filter(Product.is_featured == featured)

    # Ordenação
    sort_col = getattr(Product, sort_by)
    if sort_order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = query.count()
    products = query.offset((page - 1) * page_size).limit(page_size).all()

    # Montar lista com imagem primária
    items = []
    for p in products:
        primary_image = next((img.url for img in p.images if img.is_primary), None)
        if not primary_image and p.images:
            primary_image = p.images[0].url
        item = ProductListOut(
            id=p.id, name=p.name, slug=p.slug, brand=p.brand,
            price=p.price, compare_at_price=p.compare_at_price,
            stock_quantity=p.stock_quantity, status=p.status,
            is_featured=p.is_featured, average_rating=p.average_rating,
            review_count=p.review_count, primary_image=primary_image,
            category=p.category,
        )
        items.append(item)

    return PaginatedProducts(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{slug}", response_model=ProductOut)
def get_product(slug: str, db: Session = Depends(get_db)):
    """Retorna os detalhes de um produto pelo slug."""
    product = db.query(Product).filter(Product.slug == slug).first()
    if not product or product.status == ProductStatus.inactive:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")
    return product


@router.post("/", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    product_in: ProductCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """[Admin] Cria um novo produto."""
    slug = slugify(product_in.name)
    existing = db.query(Product).filter(Product.slug == slug).first()
    if existing:
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    product = Product(slug=slug, **product_in.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    product_update: ProductUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """[Admin] Atualiza um produto."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")
    for field, value in product_update.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """[Admin] Remove um produto (soft delete: muda status para inactive)."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")
    product.status = ProductStatus.inactive
    db.commit()


# ─── Imagens de Produto ───────────────────────────────────────────────────────

@router.post("/{product_id}/images", response_model=ProductImageOut, status_code=status.HTTP_201_CREATED)
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    is_primary: bool = False,
    alt_text: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """[Admin] Faz upload de uma imagem para um produto."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")

    if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Formato inválido.")

    upload_dir = os.path.join(settings.UPLOAD_DIR, "products", str(product_id))
    os.makedirs(upload_dir, exist_ok=True)

    ext = file.filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if is_primary:
        db.query(ProductImage).filter(ProductImage.product_id == product_id).update(
            {"is_primary": False}
        )

    image = ProductImage(
        product_id=product_id,
        url=f"/uploads/products/{product_id}/{filename}",
        alt_text=alt_text or product.name,
        is_primary=is_primary,
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    return image


@router.delete("/{product_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product_image(
    product_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """[Admin] Remove uma imagem de produto."""
    image = db.query(ProductImage).filter(
        ProductImage.id == image_id, ProductImage.product_id == product_id
    ).first()
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imagem não encontrada.")
    db.delete(image)
    db.commit()


# ─── Variantes ────────────────────────────────────────────────────────────────

@router.post("/{product_id}/variants", response_model=ProductVariantOut, status_code=status.HTTP_201_CREATED)
def create_variant(
    product_id: int,
    variant_in: ProductVariantCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """[Admin] Adiciona uma variante a um produto."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")
    variant = ProductVariant(product_id=product_id, **variant_in.model_dump())
    db.add(variant)
    db.commit()
    db.refresh(variant)
    return variant


@router.put("/{product_id}/variants/{variant_id}", response_model=ProductVariantOut)
def update_variant(
    product_id: int,
    variant_id: int,
    variant_update: ProductVariantUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """[Admin] Atualiza uma variante de produto."""
    variant = db.query(ProductVariant).filter(
        ProductVariant.id == variant_id, ProductVariant.product_id == product_id
    ).first()
    if not variant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variante não encontrada.")
    for field, value in variant_update.model_dump(exclude_unset=True).items():
        setattr(variant, field, value)
    db.commit()
    db.refresh(variant)
    return variant
