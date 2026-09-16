from sqlmodel import Session
from app.models import Receipt, Item, Contribution
from typing import List, Dict, Any

def finalize_receipt_splits(receipt: Receipt, db: Session) -> None:
    """
    Finalizes the receipt splits by applying the base amounts to the contributors.
    """
    for item in receipt.items:
        if not item.contributions:
            raise ValueError(f"Item '{item.name}' is not claimed by anyone")

    for item in receipt.items:
        num_claimants = len(item.contributions)
        total_price = int(round(item.price * item.quantity))
        
        base_amount = total_price // num_claimants
        remainder = total_price % num_claimants
        
        # Sort contributions by ID to make remainder distribution deterministic
        sorted_contribs = sorted(item.contributions, key=lambda c: c.id)
        
        for i, contrib in enumerate(sorted_contribs):
            contrib.amount = base_amount
            if i == 0: # First claimant gets the remainder
                contrib.amount += remainder
            db.add(contrib)
    
    receipt.status = "split"
    db.add(receipt)
    db.commit()

def split_item_quantity(item: Item, db: Session) -> Item:
    """
    Splits an item with quantity > 1 into a new item with quantity 1.
    Original item's quantity is decreased by 1.
    Preserves product_id, raw_name, sku, item_type, and unit.
    """
    if item.quantity <= 1:
        raise ValueError("Cannot split this item, quantity is already 1 or less.")
    
    new_item = Item(
        receipt_id=item.receipt_id,
        product_id=item.product_id,
        name=item.name,
        raw_name=item.raw_name,
        sku=item.sku,
        item_type=item.item_type,
        price=item.price,
        quantity=1.0,
        unit=item.unit
    )
    item.quantity -= 1.0
    
    db.add(new_item)
    db.add(item)
    db.commit()
    db.refresh(new_item)
    return new_item
