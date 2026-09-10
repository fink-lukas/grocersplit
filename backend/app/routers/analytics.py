import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, func
from app.database import get_session
from app.models import Receipt, Item, Product, User, Contribution
from app.auth import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

CATEGORY_PALETTE = [
    "#3B82F6",  # Blue
    "#10B981",  # Emerald
    "#F59E0B",  # Amber
    "#EC4899",  # Pink
    "#8B5CF6",  # Purple
    "#06B6D4",  # Cyan
    "#F97316",  # Orange
    "#84CC16",  # Lime
    "#6366F1",  # Indigo
    "#14B8A6",  # Teal
    "#E11D48",  # Rose
    "#64748B",  # Slate
]


@router.get("/spending")
def get_spending_analytics(
    time_range: str = Query("all", description="all, month, 30d, year"),
    scope: str = Query("flat", description="flat or me"),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Computes aggregated spending analytics:
    - Entire Flat (household total) OR My Spending (filtered by current user's claims)
    - Breakdown by Category
    - Breakdown by Tag
    - Breakdown by Store / Merchant
    - Breakdown by User
    """
    # Base query for receipts
    query = select(Receipt)

    # Filter using effective date (actual receipt purchase_date if set, else upload created_at)
    effective_date = func.coalesce(Receipt.purchase_date, Receipt.created_at)

    now = datetime.utcnow()
    if time_range == "30d":
        start_date = now - timedelta(days=30)
        query = query.where(effective_date >= start_date)
    elif time_range == "month":
        start_of_month = datetime(now.year, now.month, 1)
        query = query.where(effective_date >= start_of_month)
    elif time_range == "year":
        start_of_year = datetime(now.year, 1, 1)
        query = query.where(effective_date >= start_of_year)

    receipts = db.exec(query).all()
    receipt_map = {r.id: r for r in receipts}
    receipt_ids = list(receipt_map.keys())

    if not receipt_ids:
        return {
            "total_spent": 0,
            "total_items": 0,
            "receipt_count": 0,
            "scope": scope,
            "by_category": [],
            "by_tag": [],
            "by_store": [],
            "by_user": []
        }

    # Fetch all items in these receipts
    items = db.exec(select(Item).where(Item.receipt_id.in_(receipt_ids))).all()
    item_ids = [it.id for it in items]

    # Pre-fetch contributions for all items
    contrib_map: Dict[int, Dict[int, int]] = {}  # item_id -> {user_id: amount}
    user_contributions: Dict[int, int] = {}
    if item_ids:
        contribs = db.exec(select(Contribution).where(Contribution.item_id.in_(item_ids))).all()
        for c in contribs:
            if c.item_id not in contrib_map:
                contrib_map[c.item_id] = {}
            contrib_map[c.item_id][c.user_id] = c.amount or 0
            user_contributions[c.user_id] = user_contributions.get(c.user_id, 0) + (c.amount or 0)

    total_spent = 0
    total_items = 0
    active_receipt_ids = set()

    category_stats: Dict[str, Dict[str, Any]] = {}
    tag_stats: Dict[str, Dict[str, Any]] = {}
    store_stats: Dict[str, Dict[str, Any]] = {}

    for item in items:
        # Determine item effective cost
        if scope == "me":
            # Only count current user's contribution
            user_spent = contrib_map.get(item.id, {}).get(current_user.id, 0)
            if user_spent <= 0:
                continue
            effective_item_cost = user_spent
        else:
            # Entire flat
            effective_item_cost = int(round(item.price * item.quantity))

        total_spent += effective_item_cost
        total_items += 1
        active_receipt_ids.add(item.receipt_id)

        # 1. Determine Category
        if item.item_type == "deposit":
            cat = "Pfand / Deposit"
        elif item.item_type == "cart_discount":
            cat = "Discounts & Vouchers"
        elif item.product and item.product.category:
            cat = item.product.category
        else:
            cat = "Uncategorized"

        if cat not in category_stats:
            category_stats[cat] = {"name": cat, "amount": 0, "item_count": 0}
        category_stats[cat]["amount"] += effective_item_cost
        category_stats[cat]["item_count"] += 1

        # 2. Determine Tags
        if item.product and item.product.tags:
            try:
                tags = json.loads(item.product.tags) if isinstance(item.product.tags, str) else item.product.tags
            except Exception:
                tags = []

            for t in tags:
                clean_tag = t.strip()
                if clean_tag:
                    if clean_tag not in tag_stats:
                        tag_stats[clean_tag] = {"tag": clean_tag, "amount": 0, "item_count": 0}
                    tag_stats[clean_tag]["amount"] += effective_item_cost
                    tag_stats[clean_tag]["item_count"] += 1

        # 3. Determine Store
        r = receipt_map.get(item.receipt_id)
        store_name = (r.merchant_name or "Other / Unknown").strip() if r else "Other / Unknown"
        if not store_name:
            store_name = "Other / Unknown"

        if store_name not in store_stats:
            store_stats[store_name] = {
                "name": store_name,
                "amount": 0,
                "item_count": 0,
                "receipt_ids": set()
            }
        store_stats[store_name]["amount"] += effective_item_cost
        store_stats[store_name]["item_count"] += 1
        store_stats[store_name]["receipt_ids"].add(item.receipt_id)

    # Format Categories
    by_category = []
    sorted_cats = sorted(category_stats.values(), key=lambda x: x["amount"], reverse=True)
    for idx, c in enumerate(sorted_cats):
        pct = round((c["amount"] / total_spent * 100), 1) if total_spent > 0 else 0.0
        by_category.append({
            "name": c["name"],
            "amount": c["amount"],
            "percentage": pct,
            "item_count": c["item_count"],
            "color": CATEGORY_PALETTE[idx % len(CATEGORY_PALETTE)]
        })

    # Format Tags
    by_tag = []
    sorted_tags = sorted(tag_stats.values(), key=lambda x: x["amount"], reverse=True)
    for idx, t in enumerate(sorted_tags):
        pct = round((t["amount"] / total_spent * 100), 1) if total_spent > 0 else 0.0
        by_tag.append({
            "name": t["tag"],
            "amount": t["amount"],
            "percentage": pct,
            "item_count": t["item_count"],
            "color": CATEGORY_PALETTE[(idx + 4) % len(CATEGORY_PALETTE)]
        })

    # Format Stores
    by_store = []
    sorted_stores = sorted(store_stats.values(), key=lambda x: x["amount"], reverse=True)
    for idx, s in enumerate(sorted_stores):
        pct = round((s["amount"] / total_spent * 100), 1) if total_spent > 0 else 0.0
        by_store.append({
            "name": s["name"],
            "amount": s["amount"],
            "percentage": pct,
            "item_count": s["item_count"],
            "receipt_count": len(s["receipt_ids"]),
            "color": CATEGORY_PALETTE[(idx + 2) % len(CATEGORY_PALETTE)]
        })

    # Format Users
    by_user = []
    users = db.exec(select(User)).all()
    user_map = {u.id: u for u in users}

    if scope == "me":
        # In personal mode, current user accounts for 100% of their spending
        by_user.append({
            "user_id": current_user.id,
            "username": current_user.username,
            "color": current_user.color or "#3B82F6",
            "amount": total_spent,
            "percentage": 100.0
        })
    else:
        total_user_contrib = sum(user_contributions.values())
        for u_id, amt in sorted(user_contributions.items(), key=lambda x: x[1], reverse=True):
            u = user_map.get(u_id)
            if u:
                pct = round((amt / total_user_contrib * 100), 1) if total_user_contrib > 0 else 0.0
                by_user.append({
                    "user_id": u.id,
                    "username": u.username,
                    "color": u.color or "#3B82F6",
                    "amount": amt,
                    "percentage": pct
                })

    return {
        "total_spent": total_spent,
        "total_items": total_items,
        "receipt_count": len(active_receipt_ids) if scope == "me" else len(receipts),
        "scope": scope,
        "by_category": by_category,
        "by_tag": by_tag,
        "by_store": by_store,
        "by_user": by_user
    }
