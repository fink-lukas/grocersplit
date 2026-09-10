import re
import json
from typing import Optional, List
from sqlmodel import Session, select
from app.models import Product, ProductAlias, Item


def normalize_string(s: str) -> str:
    """Normalizes string for robust receipt alias matching."""
    if not s:
        return ""
    s = s.lower().strip()
    # Replace multiple spaces with a single space
    s = re.sub(r"\s+", " ", s)
    return s


def _is_text_compatible(raw_text: str, product: Product) -> bool:
    """
    Sanity check to prevent an old/reassigned SKU from matching a completely unrelated item.
    Returns True if raw_text and product share keywords or substring compatibility.
    """
    if not raw_text or not product or not product.name:
        return True

    norm_raw = normalize_string(raw_text)
    norm_prod = normalize_string(product.name)

    # Substring check
    if norm_raw in norm_prod or norm_prod in norm_raw:
        return True

    # Word-level overlap check (ignoring tiny 1-2 char noise)
    raw_words = set(w for w in re.split(r'[^a-zA-Z0-9äöüßÄÖÜ]', norm_raw) if len(w) >= 3)
    prod_words = set(w for w in re.split(r'[^a-zA-Z0-9äöüßÄÖÜ]', norm_prod) if len(w) >= 3)

    if raw_words & prod_words:
        return True

    # Check against existing aliases of the product
    if product.aliases:
        for a in product.aliases:
            a_words = set(w for w in re.split(r'[^a-zA-Z0-9äöüßÄÖÜ]', normalize_string(a.raw_text)) if len(w) >= 3)
            if raw_words & a_words:
                return True

    return False


def auto_match_item(
    raw_name: str,
    sku: Optional[str] = None,
    store: Optional[str] = None,
    db: Session = None
) -> Optional[Product]:
    """
    Attempts to auto-match a receipt item against the Master Product Catalog.
    1. SKU match (with text-compatibility guard against reused SKUs).
    2. Exact raw string match.
    3. Normalized raw string match.
    """
    if not db:
        return None

    clean_raw = raw_name.strip() if raw_name else ""

    # 1. Match by SKU if present (scoped by store if available)
    if sku and sku.strip():
        clean_sku = sku.strip()
        query = select(ProductAlias).where(ProductAlias.sku == clean_sku)
        if store:
            store_alias = db.exec(query.where(ProductAlias.store == store)).first()
            if store_alias and store_alias.product:
                if _is_text_compatible(clean_raw, store_alias.product):
                    return store_alias.product

        alias = db.exec(query).first()
        if alias and alias.product:
            if _is_text_compatible(clean_raw, alias.product):
                return alias.product

    # 2. Match by exact raw text
    if clean_raw:
        query = select(ProductAlias).where(ProductAlias.raw_text == clean_raw)
        if store:
            store_alias = db.exec(query.where(ProductAlias.store == store)).first()
            if store_alias and store_alias.product:
                return store_alias.product

        alias = db.exec(query).first()
        if alias and alias.product:
            return alias.product

        # 3. Match by normalized raw text
        norm_raw = normalize_string(clean_raw)
        aliases = db.exec(select(ProductAlias)).all()
        for a in aliases:
            if normalize_string(a.raw_text) == norm_raw and a.product:
                return a.product

        # Also check directly against Product canonical names
        products = db.exec(select(Product)).all()
        for p in products:
            if normalize_string(p.name) == norm_raw:
                return p

    return None


def link_item_to_product(
    item: Item,
    product: Product,
    store: Optional[str] = None,
    db: Session = None
) -> Item:
    """
    Links an Item to a Product, updates item's name to canonical name,
    and registers a new ProductAlias so future receipts auto-match.
    Also self-heals by reassigning any stale SKU alias to the new product.
    """
    item.product_id = product.id
    item.name = product.name
    db.add(item)

    # Register alias for future self-learning
    alias_text = item.raw_name or item.name
    clean_sku = item.sku.strip() if item.sku else None

    # Self-healing: If this SKU was previously assigned to a different product, reassign it
    if clean_sku:
        stale_sku_alias = db.exec(
            select(ProductAlias).where(ProductAlias.sku == clean_sku)
        ).first()
        if stale_sku_alias and stale_sku_alias.product_id != product.id:
            stale_sku_alias.product_id = product.id
            stale_sku_alias.raw_text = alias_text
            stale_sku_alias.store = store or stale_sku_alias.store
            db.add(stale_sku_alias)
            db.commit()
            db.refresh(item)
            return item

    # Check if this exact alias already exists for this product
    existing_alias = None
    if clean_sku:
        existing_alias = db.exec(
            select(ProductAlias).where(
                ProductAlias.product_id == product.id,
                ProductAlias.sku == clean_sku
            )
        ).first()

    if not existing_alias and alias_text:
        existing_alias = db.exec(
            select(ProductAlias).where(
                ProductAlias.product_id == product.id,
                ProductAlias.raw_text == alias_text
            )
        ).first()

    if not existing_alias and alias_text:
        new_alias = ProductAlias(
            product_id=product.id,
            raw_text=alias_text,
            sku=clean_sku,
            store=store
        )
        db.add(new_alias)

    db.commit()
    db.refresh(item)
    return item



def unlink_item_from_product(item: Item, db: Session) -> Item:
    """
    Unlinks an item from its product and reverts its display name to raw_name.
    """
    item.product_id = None
    if item.raw_name:
        item.name = item.raw_name
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def rematch_unlinked_items(db: Session, force_all: bool = False) -> dict:
    """
    Scans all items in the database (or only unlinked ones) and attempts to match
    them against the Master Product Catalog and its aliases.
    Does NOT affect user claims/splits.
    """
    query = select(Item)
    if not force_all:
        query = query.where(Item.product_id == None)
    items = db.exec(query).all()

    matched_count = 0
    for item in items:
        store = None
        if item.receipt:
            store = item.receipt.merchant_name or item.receipt.description

        matched = auto_match_item(
            raw_name=item.raw_name or item.name,
            sku=item.sku,
            store=store,
            db=db
        )
        if matched:
            item.product_id = matched.id
            if not item.raw_name:
                item.raw_name = item.name
            item.name = matched.name
            db.add(item)
            matched_count += 1

    if matched_count > 0:
        db.commit()

    return {
        "total_evaluated": len(items),
        "matched_count": matched_count
    }

