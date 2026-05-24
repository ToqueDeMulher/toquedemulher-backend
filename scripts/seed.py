"""
Script de seed para popular o banco de dados com dados iniciais.
Execute com: python scripts/seed.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import SessionLocal, Base, engine
from app.models.user import User, UserRole
from app.models.product import Category, Product, ProductImage
from app.core.security import get_password_hash

Base.metadata.create_all(bind=engine)
db = SessionLocal()


def seed_admin():
    """Cria o usuário administrador padrão."""
    admin = db.query(User).filter(User.email == "admin@toquedemulher.com.br").first()
    if not admin:
        admin = User(
            full_name="Administrador",
            email="admin@toquedemulher.com.br",
            hashed_password=get_password_hash("Admin@123"),
            role=UserRole.admin,
            is_active=True,
            is_verified=True,
        )
        db.add(admin)
        db.commit()
        print("✅ Administrador criado: admin@toquedemulher.com.br / Admin@123")
    else:
        print("ℹ️  Administrador já existe.")


def seed_categories():
    """Cria as categorias iniciais."""
    categories_data = [
        {"name": "Perfumes Femininos", "description": "Fragrâncias exclusivas para mulheres"},
        {"name": "Perfumes Masculinos", "description": "Fragrâncias marcantes para homens"},
        {"name": "Skincare", "description": "Cuidados com a pele"},
        {"name": "Maquiagem", "description": "Produtos de maquiagem e cosméticos"},
        {"name": "Cabelos", "description": "Produtos para cuidados com os cabelos"},
        {"name": "Kits e Presentes", "description": "Kits especiais e opções de presente"},
    ]

    for cat_data in categories_data:
        from slugify import slugify
        slug = slugify(cat_data["name"])
        existing = db.query(Category).filter(Category.slug == slug).first()
        if not existing:
            category = Category(slug=slug, **cat_data)
            db.add(category)

    db.commit()
    print("✅ Categorias criadas.")


def seed_products():
    """Cria produtos de exemplo."""
    cat_perfumes = db.query(Category).filter(Category.name == "Perfumes Femininos").first()

    products_data = [
        {
            "name": "La Vie Est Belle",
            "brand": "Lancôme",
            "price": 389.90,
            "compare_at_price": 450.00,
            "description": "Um perfume floral e gourmand que celebra a liberdade de escrever sua própria história de vida.",
            "short_description": "Floral gourmand, notas de íris, baunilha e patchouli.",
            "stock_quantity": 50,
            "is_featured": True,
            "tags": ["floral", "gourmand", "feminino", "lancôme"],
            "attributes": {"volume": "50ml", "concentração": "EDP"},
        },
        {
            "name": "Chanel N°5",
            "brand": "Chanel",
            "price": 699.90,
            "description": "O perfume mais famoso do mundo. Um floral aldeídico atemporal.",
            "short_description": "Floral aldeídico clássico com notas de ylang-ylang e sândalo.",
            "stock_quantity": 30,
            "is_featured": True,
            "tags": ["floral", "clássico", "feminino", "chanel"],
            "attributes": {"volume": "50ml", "concentração": "EDP"},
        },
        {
            "name": "Good Girl",
            "brand": "Carolina Herrera",
            "price": 459.90,
            "description": "Uma fragrância floral oriental que captura a dualidade da mulher moderna.",
            "short_description": "Floral oriental com notas de jasmim, cacau e baunilha.",
            "stock_quantity": 45,
            "is_featured": True,
            "tags": ["floral", "oriental", "feminino", "carolina herrera"],
            "attributes": {"volume": "80ml", "concentração": "EDP"},
        },
    ]

    for prod_data in products_data:
        from slugify import slugify
        slug = slugify(prod_data["name"])
        existing = db.query(Product).filter(Product.slug == slug).first()
        if not existing:
            product = Product(
                slug=slug,
                category_id=cat_perfumes.id if cat_perfumes else None,
                **prod_data,
            )
            db.add(product)

    db.commit()
    print("✅ Produtos de exemplo criados.")


if __name__ == "__main__":
    print("🌱 Iniciando seed do banco de dados...")
    seed_admin()
    seed_categories()
    seed_products()
    db.close()
    print("✅ Seed concluído com sucesso!")
