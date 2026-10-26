"""Public product data comes exclusively from persisted catalog and stock."""
import re
import unicodedata

from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.models.product import Product


def category_slug(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")


def public_products_query():
    return select(Product).where(Product.active == True).options(
        selectinload(Product.images), selectinload(Product.categories),
        selectinload(Product.description), selectinload(Product.stock),
        selectinload(Product.reviews),
    ).order_by(Product.created_at.desc(), Product.id)


def public_product(product: Product) -> dict:
    images = sorted(product.images, key=lambda image: (image.order, image.id))
    categories = sorted({category_slug(category.name) for category in product.categories})
    supported = {"maquiagem", "skincare", "corpo", "cabelos", "perfumes"}
    stock = max(0, product.stock.total_quantity) if product.stock else 0
    description = product.description
    reviews = product.reviews
    return {
        "id": str(product.id), "slug": product.slug, "name": product.name,
        "price": product.price, "image": images[0].url if images else "",
        "images": [{"url": image.url, "alt": image.alt_text or product.name} for image in images],
        "categories": categories,
        "category": next((category for category in categories if category in supported), None),
        "subcategory": product.product_type or "",
        "description": description.text if description else "",
        "composition": (description.ingredients or "") if description else "",
        "howToUse": (description.usage_tips or "") if description else "",
        "benefits": "", "volume": product.volume, "color": product.color,
        "fragrance": product.fragrance, "available": stock > 0 and product.price > 0,
        "stockQuantity": stock,
        "rating": sum(review.rating for review in reviews) / len(reviews) if reviews else 0,
        "reviews": len(reviews),
    }
