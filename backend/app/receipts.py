from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlmodel import Session, select
from app.database import get_session
from app.models import User, Receipt, Item, Contribution, ReceiptParticipant, Notification, Product, ProductAlias
from app.auth import get_current_user
from app.gemini import parse_receipt, ParsingFailed, RateLimitExceeded
from app.services.catalog_service import auto_match_item, link_item_to_product, unlink_item_from_product
import shutil
import os
import uuid
import json
from datetime import datetime
from typing import List, Optional
from fastapi import BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from app.services.notification_service import send_ha_notification
from app.services.receipt_service import finalize_receipt_splits, split_item_quantity as svc_split_item
from app.core.config import settings

router = APIRouter(prefix="/api/receipts")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def can_manage_receipt(receipt: Receipt, user: User) -> bool:
    """
    Checks if a user has management permissions over a receipt.
    The uploader can always manage. If the uploader is inactive (e.g. moved out),
    any active flatmate/user can manage and edit the receipt.
    """
    if not receipt or not user:
        return False
    if receipt.uploader_id == user.id:
        return True
    if receipt.uploader and not receipt.uploader.is_active:
        return True
    return False


@router.post("/upload")
async def upload_receipt(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    participant_ids: str = Form(...),  # Comma separated IDs
    description: str = Form(None),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Save file and parse in a threadpool to avoid blocking event loop
    file_ext = os.path.splitext(file.filename)[1].lower()
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp"}
    if file_ext not in allowed_exts:
        raise HTTPException(status_code=400, detail="Invalid file type. Only JPG, PNG, and WEBP are allowed.")

    file_name = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, file_name)
    
    def save_file():
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
    await run_in_threadpool(save_file)
    
    # Process with Gemini
    try:
        parsed_data = await parse_receipt(file_path)
    except RateLimitExceeded as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=429, detail=str(e))
    except ParsingFailed as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
        
    try:
        meta = parsed_data.get("metadata", {})
        merchant_name = meta.get("store")
        date_str = meta.get("date")
        time_str = meta.get("time")
        purchase_date = None
        if date_str:
            try:
                if time_str:
                    purchase_date = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
                else:
                    purchase_date = datetime.strptime(date_str, "%Y-%m-%d")
            except Exception:
                pass

        total_val = parsed_data.get("total") or parsed_data.get("total_cents") or parsed_data.get("items_sum", 0)
        receipt = Receipt(
            uploader_id=current_user.id,
            image_path=file_path,
            description=description or merchant_name,
            merchant_name=merchant_name,
            purchase_date=purchase_date or datetime.utcnow(),
            raw_json=json.dumps(parsed_data),
            total_amount=total_val,
            status="pending",
            mismatch=parsed_data.get("mismatch", False)
        )
        db.add(receipt)
        db.commit()
        db.refresh(receipt)
        
        # Add participants
        try:
            ids = [int(i.strip()) for i in participant_ids.split(",") if i.strip()]
        except ValueError:
            ids = []
            
        if current_user.id not in ids:
            ids.append(current_user.id)
            
        for u_id in ids:
            u = db.get(User, u_id)
            if u:
                participant = ReceiptParticipant(receipt_id=receipt.id, user_id=u.id)
                db.add(participant)
                
        # Add items and run auto-catalog matching
        for item_data in parsed_data.get("items", []):
            item = Item(
                receipt_id=receipt.id,
                name=item_data.get("name", "Unknown Item"),
                raw_name=item_data.get("name"),
                sku=item_data.get("sku"),
                item_type=item_data.get("type", "product"),
                price=item_data.get("price", 0),
                original_price=item_data.get("original_price"),
                discount_amount=item_data.get("discount_amount", 0),
                quantity=item_data.get("quantity", 1.0),
                unit=item_data.get("unit"),
                notes=item_data.get("notes")
            )
            db.add(item)
            db.flush()

            # Attempt catalog matching for standard products
            if item.item_type == "product":
                auto_match_item(item, receipt, db)

        db.commit()
        db.refresh(receipt)
        
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
    # Send push notifications
    users_to_notify = db.exec(
        select(User).join(ReceiptParticipant).where(
            ReceiptParticipant.receipt_id == receipt.id
        )
    ).all()
    
    for user in users_to_notify:
        if user.id != current_user.id:
            notif = Notification(
                user_id=user.id,
                message=f"{current_user.username} uploaded a new receipt. Total: €{receipt.total_amount/100:.2f}",
                read=False
            )
            db.add(notif)
            background_tasks.add_task(
                send_ha_notification,
                f"Receipt from {current_user.username}",
                f"Total: €{receipt.total_amount/100:.2f}"
            )
    db.commit()

    return receipt


class ItemCreate(BaseModel):
    name: str
    price: int
    quantity: float = 1.0
    unit: Optional[str] = None


@router.post("/{receipt_id}/items")
def add_item(
    receipt_id: int,
    item_data: ItemCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if not can_manage_receipt(receipt, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to edit items on this receipt")
    if receipt.status != "pending":
        raise HTTPException(status_code=400, detail="Can only add items to pending receipts")
    
    item = Item(
        receipt_id=receipt_id,
        name=item_data.name,
        raw_name=item_data.name,
        price=item_data.price,
        quantity=item_data.quantity,
        unit=item_data.unit
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("")
def list_receipts(
    archived: bool = False,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Receipts where user is participant, OR user is uploader, OR receipt uploader is inactive (takeover)
    statement = (
        select(Receipt)
        .outerjoin(ReceiptParticipant, Receipt.id == ReceiptParticipant.receipt_id)
        .outerjoin(User, Receipt.uploader_id == User.id)
        .where(
            (ReceiptParticipant.user_id == current_user.id) |
            (Receipt.uploader_id == current_user.id) |
            (User.is_active == False)
        )
        .distinct()
        .order_by(Receipt.id.desc())
    )
    if archived:
        statement = statement.where(Receipt.status == "archived")
    else:
        statement = statement.where(Receipt.status != "archived")
        
    receipts = db.exec(statement).all()
    return [
        {
            **r.dict(),
            "uploader": {
                "id": r.uploader.id,
                "username": r.uploader.username,
                "color": r.uploader.color,
                "is_active": r.uploader.is_active
            } if r.uploader else None,
            "can_manage": can_manage_receipt(r, current_user)
        }
        for r in receipts
    ]


@router.get("/{receipt_id}")
def get_receipt(
    receipt_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
        
    is_part = any(p.user_id == current_user.id for p in receipt.participants)
    if not is_part and not can_manage_receipt(receipt, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    # Auto-heal total_amount if it was saved as 0 due to parsed_data key mismatch
    if receipt.total_amount == 0 and receipt.items:
        healed_total = None
        if receipt.raw_json:
            try:
                rj = json.loads(receipt.raw_json)
                healed_total = rj.get("total") or rj.get("total_cents")
            except Exception:
                pass
        if not healed_total:
            healed_total = sum(int(round(it.price * it.quantity)) for it in receipt.items)
        if healed_total and healed_total > 0:
            receipt.total_amount = healed_total
            items_sum = sum(int(round(it.price * it.quantity)) for it in receipt.items)
            receipt.mismatch = abs(items_sum - receipt.total_amount) > 2
            db.add(receipt)
            db.commit()
            db.refresh(receipt)
    
    items = sorted(receipt.items, key=lambda x: x.id)

    def serialize_receipt_item(item: Item):
        d = item.dict()
        if item.product:
            try:
                tags = json.loads(item.product.tags) if item.product.tags else []
            except Exception:
                tags = []
            d["product"] = {
                "id": item.product.id,
                "name": item.product.name,
                "category": item.product.category,
                "tags": tags,
                "default_unit": item.product.default_unit
            }
        else:
            d["product"] = None

        d["contributions"] = [
            {
                **c.dict(),
                "username": c.user.username,
                "color": c.user.color
            } for c in item.contributions
        ]
        return d

    receipt_dict = receipt.dict()
    receipt_dict["uploader"] = {
        "id": receipt.uploader.id,
        "username": receipt.uploader.username,
        "color": receipt.uploader.color,
        "is_active": receipt.uploader.is_active
    } if receipt.uploader else None
    receipt_dict["can_manage"] = can_manage_receipt(receipt, current_user)

    return {
        "receipt": receipt_dict,
        "items": [serialize_receipt_item(item) for item in items],
        "participants": [
            {
                **p.dict(),
                "username": p.user.username,
                "color": p.user.color
            } for p in receipt.participants
        ]
    }


class ReceiptUpdate(BaseModel):
    description: Optional[str] = None
    merchant_name: Optional[str] = None
    purchase_date: Optional[datetime] = None


@router.put("/{receipt_id}")
def update_receipt(
    receipt_id: int,
    data: ReceiptUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    is_part = any(p.user_id == current_user.id for p in receipt.participants)
    if not is_part and not can_manage_receipt(receipt, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to edit this receipt")

    if data.description is not None:
        receipt.description = data.description.strip() if data.description else None
    if data.merchant_name is not None:
        receipt.merchant_name = data.merchant_name.strip() if data.merchant_name else None
    if data.purchase_date is not None:
        receipt.purchase_date = data.purchase_date

    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    return receipt


class TransferOwnershipRequest(BaseModel):
    new_uploader_id: int


@router.post("/{receipt_id}/transfer-ownership")
def transfer_receipt_ownership(
    receipt_id: int,
    data: TransferOwnershipRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Transfers receipt uploader to a new user without modifying any item contributions or claims.
    """
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if not can_manage_receipt(receipt, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to transfer ownership of this receipt")

    new_user = db.get(User, data.new_uploader_id)
    if not new_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    receipt.uploader_id = new_user.id
    db.add(receipt)
    db.commit()
    db.refresh(receipt)

    return {
        "message": f"Ownership transferred to {new_user.username}",
        "uploader_id": receipt.uploader_id,
        "uploader": {
            "id": new_user.id,
            "username": new_user.username,
            "color": new_user.color,
            "is_active": new_user.is_active
        }
    }


@router.get("/{receipt_id}/raw-json")
def get_receipt_raw_json(
    receipt_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if not receipt.raw_json:
        raise HTTPException(status_code=404, detail="No raw AI extraction available for this receipt")
    try:
        return json.loads(receipt.raw_json)
    except Exception:
        return {"raw": receipt.raw_json}


class ClaimRequest(BaseModel):
    quantity: int = 1
    target_user_id: Optional[int] = None


@router.post("/{receipt_id}/items/{item_id}/claim")
def claim_item(
    receipt_id: int,
    item_id: int,
    data: ClaimRequest = ClaimRequest(),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    item = db.get(Item, item_id)
    if not item or item.receipt_id != receipt_id:
        raise HTTPException(status_code=404, detail="Item not found")

    user_to_claim = current_user.id
    if data.target_user_id is not None:
        receipt = db.get(Receipt, receipt_id)
        if not can_manage_receipt(receipt, current_user):
            raise HTTPException(status_code=403, detail="Only uploader or manager can assign items to others")
        user_to_claim = data.target_user_id

    existing = db.exec(
        select(Contribution).where(
            Contribution.item_id == item_id,
            Contribution.user_id == user_to_claim
        )
    ).first()
    
    if existing:
        db.delete(existing)
        db.commit()
    else:
        contrib = Contribution(
            item_id=item_id,
            user_id=user_to_claim,
            amount=0
        )
        db.add(contrib)
        db.commit()

        if user_to_claim != current_user.id:
            item_name = item.name
            item_price = item.price
            notif = Notification(
                user_id=user_to_claim,
                message=f"{current_user.username} assigned '{item_name}' (Price: €{item_price/100:.2f}) to you.",
                read=False
            )
            db.add(notif)
            db.commit()
            
    # Recalculate amounts
    all_contribs = db.exec(select(Contribution).where(Contribution.item_id == item_id)).all()
    if all_contribs:
        split_amount = item.price // len(all_contribs)
        rem = item.price % len(all_contribs)
        for i, c in enumerate(all_contribs):
            c.amount = split_amount + (1 if i < rem else 0)
            db.add(c)
        db.commit()
        
    return {"message": "Claim toggled"}


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None


@router.put("/{receipt_id}/items/{item_id}")
def update_item(
    receipt_id: int,
    item_id: int,
    data: ItemUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    item = db.get(Item, item_id)
    if not item or item.receipt_id != receipt_id:
        raise HTTPException(status_code=404, detail="Item not found")
    
    receipt = db.get(Receipt, receipt_id)
    if not can_manage_receipt(receipt, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to edit items on this receipt")
    if receipt.status != "pending":
        raise HTTPException(status_code=400, detail="Can only edit items of pending receipts")
        
    if data.name is not None:
        item.name = data.name
    if data.price is not None:
        item.price = data.price
    if data.quantity is not None:
        item.quantity = data.quantity
    if data.unit is not None:
        item.unit = data.unit
        
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{receipt_id}/items/{item_id}/split-quantity")
def split_item_quantity_endpoint(
    receipt_id: int,
    item_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    item = db.get(Item, item_id)
    if not item or item.receipt_id != receipt_id or item.quantity <= 1:
        raise HTTPException(status_code=400, detail="Cannot split this item")
    
    try:
        svc_split_item(item, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    return {"message": "Item split"}


class SplitAmountRequest(BaseModel):
    parts: int = 2
    first_part_cents: Optional[int] = None


@router.post("/{receipt_id}/items/{item_id}/split-amount")
def split_item_amount_endpoint(
    receipt_id: int,
    item_id: int,
    data: Optional[SplitAmountRequest] = None,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if not can_manage_receipt(receipt, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to modify this receipt")
    if receipt.status != "pending":
        raise HTTPException(status_code=400, detail="Can only split items in pending receipts")

    item = db.get(Item, item_id)
    if not item or item.receipt_id != receipt_id:
        raise HTTPException(status_code=404, detail="Item not found on this receipt")

    total = item.price
    if abs(total) < 2:
        raise HTTPException(status_code=400, detail="Price too small to split")

    p1 = total // 2
    p2 = total - p1
    if data and data.first_part_cents is not None and 0 < data.first_part_cents < total:
        p1 = data.first_part_cents
        p2 = total - p1

    orig_name = item.name
    item.price = p1
    if not item.name.endswith("(1/2)"):
        item.name = f"{orig_name} (1/2)"

    new_item = Item(
        receipt_id=receipt_id,
        product_id=item.product_id,
        name=f"{orig_name} (2/2)",
        raw_name=item.raw_name,
        sku=item.sku,
        item_type=item.item_type,
        price=p2,
        quantity=1,
        unit=item.unit
    )
    db.add(item)
    db.add(new_item)
    db.commit()
    db.refresh(item)
    db.refresh(new_item)
    return {"message": "Item amount split successfully", "item1": item, "item2": new_item}



@router.post("/{receipt_id}/finalize")
def finalize_receipt(
    receipt_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    receipt = db.get(Receipt, receipt_id)
    if not can_manage_receipt(receipt, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to finalize this receipt")
    
    try:
        finalize_receipt_splits(receipt, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    return {"message": "Receipt finalized and split"}


@router.post("/{receipt_id}/archive")
def archive_receipt(
    receipt_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    receipt = db.get(Receipt, receipt_id)
    if not can_manage_receipt(receipt, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to archive this receipt")
    
    receipt.status = "archived"
    db.add(receipt)
    db.commit()
    return {"message": "Receipt archived"}


@router.post("/{receipt_id}/unarchive")
def unarchive_receipt(
    receipt_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if not can_manage_receipt(receipt, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to unarchive this receipt")
    if receipt.status != "archived":
        raise HTTPException(status_code=400, detail="Receipt is not archived")

    receipt.status = "split"
    db.add(receipt)
    db.commit()
    return {"message": "Receipt unarchived to split status"}



@router.post("/{receipt_id}/revert")
def revert_receipt(
    receipt_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if not can_manage_receipt(receipt, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to revert this receipt")
    if receipt.status != "split":
        raise HTTPException(status_code=400, detail="Can only revert finalized (split) receipts")
    
    receipt.status = "pending"
    db.add(receipt)
    db.commit()
    return {"message": "Receipt reverted to pending"}


@router.delete("/{receipt_id}")
def delete_receipt(
    receipt_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if not can_manage_receipt(receipt, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to delete this receipt")
    
    image_path = receipt.image_path
        
    db.delete(receipt)
    db.commit()

    if os.path.exists(image_path):
        try:
            os.remove(image_path)
        except OSError:
            pass
            
    return {"message": "Receipt deleted"}


class LinkProductRequest(BaseModel):
    product_id: Optional[int] = None
    new_product_name: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = []


@router.post("/{receipt_id}/items/{item_id}/link-product")
def link_item_product(
    receipt_id: int,
    item_id: int,
    data: LinkProductRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    item = db.get(Item, item_id)
    if not item or item.receipt_id != receipt_id:
        raise HTTPException(status_code=404, detail="Item not found")

    receipt = db.get(Receipt, receipt_id)
    store = (receipt.merchant_name or receipt.description) if receipt else None

    if data.product_id:
        product = db.get(Product, data.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
    elif data.new_product_name:
        clean_name = data.new_product_name.strip()
        if not clean_name:
            raise HTTPException(status_code=400, detail="Product name cannot be empty")
        existing = db.exec(select(Product).where(Product.name == clean_name)).first()
        if existing:
            product = existing
            try:
                cur_tags = json.loads(existing.tags) if existing.tags else []
            except Exception:
                cur_tags = []
            merged_tags = list(set(cur_tags + data.tags))
            product.tags = json.dumps(merged_tags)
            if data.category and not product.category:
                product.category = data.category
        else:
            product = Product(
                name=clean_name,
                category=data.category.strip() if data.category else None,
                tags=json.dumps(data.tags or [])
            )
            db.add(product)
            db.commit()
            db.refresh(product)
    else:
        raise HTTPException(status_code=400, detail="Provide product_id or new_product_name")

    updated_item = link_item_to_product(item, product, store=store, db=db)
    try:
        tags = json.loads(product.tags) if product.tags else []
    except Exception:
        tags = []

    return {
        "item": updated_item,
        "product": {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "tags": tags,
            "default_unit": product.default_unit
        }
    }


@router.post("/{receipt_id}/items/{item_id}/unlink-product")
def unlink_item_product(
    receipt_id: int,
    item_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    item = db.get(Item, item_id)
    if not item or item.receipt_id != receipt_id:
        raise HTTPException(status_code=404, detail="Item not found")

    updated_item = unlink_item_from_product(item, db)
    return {"item": updated_item, "product": None}


@router.post("/{receipt_id}/items/{item_id}/unmatch-discount")
def unmatch_discount(
    receipt_id: int,
    item_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    item = db.get(Item, item_id)
    if not item or item.receipt_id != receipt_id:
        raise HTTPException(status_code=404, detail="Item not found")

    if not item.discount_amount or item.discount_amount <= 0:
        raise HTTPException(status_code=400, detail="Item has no attached discount to unmatch.")

    discount_val = item.discount_amount
    item.price = item.original_price if item.original_price is not None else (item.price + discount_val)
    item.original_price = None
    item.discount_amount = 0
    db.add(item)

    discount_item = Item(
        receipt_id=receipt_id,
        name=f"Rabatt ({item.name})",
        raw_name="Rabatt",
        item_type="cart_discount",
        price=-discount_val,
        quantity=1.0
    )
    db.add(discount_item)
    db.commit()
    db.refresh(item)
    db.refresh(discount_item)

    return {"item": item, "discount_item": discount_item}


@router.post("/{receipt_id}/items/{discount_item_id}/attach-discount/{target_item_id}")
def attach_discount(
    receipt_id: int,
    discount_item_id: int,
    target_item_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    disc_item = db.get(Item, discount_item_id)
    target_item = db.get(Item, target_item_id)

    if not disc_item or disc_item.receipt_id != receipt_id:
        raise HTTPException(status_code=404, detail="Discount item not found")
    if not target_item or target_item.receipt_id != receipt_id:
        raise HTTPException(status_code=404, detail="Target item not found")

    discount_val = abs(disc_item.price)
    if discount_val == 0:
        raise HTTPException(status_code=400, detail="Discount amount must be non-zero.")

    target_item.original_price = target_item.original_price or target_item.price
    target_item.discount_amount = (target_item.discount_amount or 0) + discount_val
    target_item.price = max(0, target_item.original_price - target_item.discount_amount)

    db.add(target_item)
    db.delete(disc_item)
    db.commit()
    db.refresh(target_item)

    return {"target_item": target_item}
