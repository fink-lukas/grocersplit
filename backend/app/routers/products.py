import json
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select
from app.database import get_session
from app.models import Product, ProductAlias, User, Item
from app.auth import get_current_user
from app.services.catalog_service import normalize_string, rematch_unlinked_items

router = APIRouter(prefix="/api/products", tags=["products"])

CATEGORIES_FILE = Path(__file__).resolve().parent.parent / "core" / "categories.json"


@router.get("/categories")
def get_categories():
    """Returns available product categories from configuration."""
    if CATEGORIES_FILE.exists():
        try:
            with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return [
        "Pfand", "Rabatt", "Produce", "Dairy & Eggs", "Bakery", "Meat & Fish",
        "Pantry & Dry Goods", "Beverages", "Snacks & Sweets", "Frozen",
        "Household & Cleaning", "Personal Care", "Pet Supplies", "Other"
    ]


class CategoryCreate(BaseModel):
    name: str


@router.post("/categories")
def add_category(data: CategoryCreate):
    """Adds a new custom product category to the configuration."""
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Category name cannot be empty")

    current_cats = []
    if CATEGORIES_FILE.exists():
        try:
            with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
                current_cats = json.load(f)
        except Exception:
            current_cats = []

    if name not in current_cats:
        current_cats.append(name)
        with open(CATEGORIES_FILE, "w", encoding="utf-8") as f:
            json.dump(current_cats, f, indent=2, ensure_ascii=False)

    return current_cats


class ProductCreate(BaseModel):
    name: str
    category: Optional[str] = None
    tags: List[str] = []
    default_unit: Optional[str] = None
    # Optional alias to register immediately
    alias_to_register: Optional[str] = None
    sku_to_register: Optional[str] = None
    store: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    default_unit: Optional[str] = None


class AliasCreate(BaseModel):
    raw_text: str
    sku: Optional[str] = None
    store: Optional[str] = None



def serialize_product(p: Product) -> dict:
    try:
        parsed_tags = json.loads(p.tags) if p.tags else []
    except Exception:
        parsed_tags = []
    return {
        "id": p.id,
        "name": p.name,
        "category": p.category,
        "tags": parsed_tags,
        "default_unit": p.default_unit,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "alias_count": len(p.aliases) if p.aliases else 0
    }


@router.get("")
def list_products(
    q: Optional[str] = Query(None, description="Search query for name or alias"),
    category: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    query = select(Product)
    if category:
        query = query.where(Product.category == category)

    products = db.exec(query).all()
    results = []

    search_term = q.lower().strip() if q else None

    for p in products:
        p_data = serialize_product(p)
        # Tag filter
        if tag and tag.lower() not in [t.lower() for t in p_data["tags"]]:
            continue

        # Search filter across product name, category, and aliases
        if search_term:
            matches_name = search_term in p.name.lower()
            matches_cat = p.category and search_term in p.category.lower()
            matches_alias = any(search_term in a.raw_text.lower() or (a.sku and search_term in a.sku) for a in p.aliases)
            if not (matches_name or matches_cat or matches_alias):
                continue

        results.append(p_data)

    # Sort alphabetically by name
    results.sort(key=lambda x: x["name"].lower())
    return results


@router.get("/tags")
def get_all_tags(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Returns a list of all distinct tags currently used across products."""
    products = db.exec(select(Product)).all()
    all_tags = set()
    for p in products:
        try:
            tags = json.loads(p.tags) if p.tags else []
            for t in tags:
                if t and t.strip():
                    all_tags.add(t.strip())
        except Exception:
            pass
    return sorted(list(all_tags))


@router.post("")
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    clean_name = data.name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Product name cannot be empty")

    # Check if a product with the exact clean name already exists
    existing = db.exec(select(Product).where(Product.name == clean_name)).first()
    if existing:
        product = existing
        # Merge tags if provided
        existing_tags = json.loads(existing.tags) if existing.tags else []
        merged_tags = list(set(existing_tags + data.tags))
        product.tags = json.dumps(merged_tags)
        if data.category and not product.category:
            product.category = data.category
    else:
        product = Product(
            name=clean_name,
            category=data.category.strip() if data.category else None,
            tags=json.dumps(data.tags or []),
            default_unit=data.default_unit
        )
        db.add(product)
        db.commit()
        db.refresh(product)

    # Register alias if provided
    if data.alias_to_register or data.sku_to_register:
        raw_text = data.alias_to_register.strip() if data.alias_to_register else clean_name
        sku = data.sku_to_register.strip() if data.sku_to_register else None
        
        alias_exists = db.exec(
            select(ProductAlias).where(
                ProductAlias.product_id == product.id,
                ProductAlias.raw_text == raw_text
            )
        ).first()
        if not alias_exists:
            new_alias = ProductAlias(
                product_id=product.id,
                raw_text=raw_text,
                sku=sku,
                store=data.store
            )
            db.add(new_alias)
            db.commit()

    db.refresh(product)
    return serialize_product(product)


@router.get("/{product_id}")
def get_product(
    product_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    data = serialize_product(product)
    data["aliases"] = [
        {
            "id": a.id,
            "raw_text": a.raw_text,
            "sku": a.sku,
            "store": a.store,
            "created_at": a.created_at.isoformat() if a.created_at else None
        } for a in product.aliases
    ]
    return data


@router.put("/{product_id}")
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if data.name is not None:
        product.name = data.name.strip()
    if data.category is not None:
        product.category = data.category.strip() if data.category else None
    if data.tags is not None:
        product.tags = json.dumps(data.tags)
    if data.default_unit is not None:
        product.default_unit = data.default_unit

    db.add(product)
    db.commit()
    db.refresh(product)
    return serialize_product(product)


@router.get("/{product_id}/aliases")
def get_product_aliases(
    product_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return [
        {
            "id": a.id,
            "raw_text": a.raw_text,
            "sku": a.sku,
            "store": a.store,
            "created_at": a.created_at.isoformat() if a.created_at else None
        } for a in product.aliases
    ]


@router.post("/{product_id}/aliases")
def add_alias(
    product_id: int,
    data: AliasCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    raw_text = data.raw_text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="Alias text cannot be empty")

    alias = ProductAlias(
        product_id=product_id,
        raw_text=raw_text,
        sku=data.sku.strip() if data.sku else None,
        store=data.store.strip() if data.store else None
    )
    db.add(alias)
    db.commit()
    db.refresh(alias)
    return {
        "id": alias.id,
        "raw_text": alias.raw_text,
        "sku": alias.sku,
        "store": alias.store,
        "created_at": alias.created_at.isoformat() if alias.created_at else None
    }


@router.delete("/{product_id}/aliases/{alias_id}")
def delete_alias(
    product_id: int,
    alias_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    alias = db.get(ProductAlias, alias_id)
    if not alias or alias.product_id != product_id:
        raise HTTPException(status_code=404, detail="Alias not found")

    db.delete(alias)
    db.commit()
    return {"message": "Alias deleted successfully"}


@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Unlink any items associated with this product
    items = db.exec(select(Item).where(Item.product_id == product_id)).all()
    for it in items:
        it.product_id = None
        db.add(it)

    # Delete associated aliases
    aliases = db.exec(select(ProductAlias).where(ProductAlias.product_id == product_id)).all()
    for a in aliases:
        db.delete(a)

    db.delete(product)
    db.commit()
    return {"message": "Product deleted successfully"}


@router.post("/rematch-history")
def rematch_history(
    force_all: bool = Query(False, description="Whether to re-evaluate already matched items"),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Scans historical items in the database and links them to matching products/aliases.
    """
    return rematch_unlinked_items(db=db, force_all=force_all)


