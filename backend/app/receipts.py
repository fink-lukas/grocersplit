from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlmodel import Session, select
from app.database import get_session
from app.models import User, Receipt, Item, Contribution, ReceiptParticipant, Notification
from app.auth import get_current_user
from app.gemini import parse_receipt
import shutil
import os
import uuid
from typing import List, Optional

router = APIRouter(prefix="/api/receipts")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_receipt(
    file: UploadFile = File(...),
    participant_ids: str = Form(...), # Comma separated IDs
    description: str = Form(None),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Save file
    file_ext = os.path.splitext(file.filename)[1]
    file_name = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, file_name)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Parse with Gemini
    parsed_data = parse_receipt(file_path)
    if not parsed_data:
        os.remove(file_path)
        raise HTTPException(status_code=500, detail="Failed to parse receipt")
    
    # Create Receipt
    receipt = Receipt(
        uploader_id=current_user.id,
        image_path=file_path,
        description=description,
        total_amount=parsed_data.get("total", 0),
        status="pending",
        mismatch=parsed_data.get("mismatch", False)
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    
    # Add Participants
    ids = [int(i.strip()) for i in participant_ids.split(",") if i.strip()]
    for uid in ids:
        part = ReceiptParticipant(receipt_id=receipt.id, user_id=uid)
        db.add(part)
    
    # Add Items
    for item_data in parsed_data.get("items", []):
        item = Item(
            receipt_id=receipt.id,
            name=item_data.get("name"),
            price=item_data.get("price", 0),
            quantity=item_data.get("quantity", 1)
        )
        db.add(item)
    
    db.commit()
    return {"id": receipt.id, "message": "Receipt uploaded and parsed", "mismatch": receipt.mismatch}

class ItemCreate(BaseModel):
    name: str
    price: int
    quantity: int

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
    if receipt.uploader_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only uploader can add items")
    
    item = Item(
        receipt_id=receipt_id,
        name=item_data.name,
        price=item_data.price,
        quantity=item_data.quantity
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
    # Get receipts where user is a participant OR uploader
    status_filter = "archived" if archived else "pending" # or "split"
    
    # Simple query for now: receipts where user is participant
    statement = select(Receipt).join(ReceiptParticipant).where(
        ReceiptParticipant.user_id == current_user.id
    )
    if archived:
        statement = statement.where(Receipt.status == "archived")
    else:
        statement = statement.where(Receipt.status != "archived")
        
    receipts = db.exec(statement).all()
    return receipts

@router.get("/{receipt_id}")
def get_receipt(
    receipt_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
        
    # Check if user is participant
    is_part = any(p.user_id == current_user.id for p in receipt.participants)
    if not is_part and receipt.uploader_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Sort items by id
    items = sorted(receipt.items, key=lambda x: x.id)

    return {
        "receipt": receipt,
        "items": [
            {
                **item.dict(),
                "contributions": [
                    {
                        **c.dict(),
                        "username": c.user.username,
                        "color": c.user.color
                    } for c in item.contributions
                ]
            } for item in items
        ],
        "participants": [
            {
                **p.dict(),
                "username": p.user.username,
                "color": p.user.color
            } for p in receipt.participants
        ]
    }

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
        # Permission check: Only uploader can assign to others
        # Fetch receipt to check uploader
        receipt = db.get(Receipt, receipt_id)
        if receipt.uploader_id != current_user.id:
            raise HTTPException(status_code=403, detail="Only uploader can assign items to others")
        user_to_claim = data.target_user_id

    # For simplicity, if multiple people claim, we split the price equally
    # We create/update the contribution records
    # But wait, if user claims "1 out of 3", we need to handle that.
    # For now, let's keep it simple: "I am part of this item"
    
    existing = db.exec(
        select(Contribution).where(
            Contribution.item_id == item_id,
            Contribution.user_id == user_to_claim
        )
    ).first()
    
    if existing:
        db.delete(existing)
        # Maybe notify user that they were removed? optional.
    else:
        # Just a placeholder, split happens at "Finalize"
        contrib = Contribution(item_id=item_id, user_id=user_to_claim, amount=0)
        db.add(contrib)
        
        # Notify if claimed by someone else
        if user_to_claim != current_user.id:
            notif = Notification(
                user_id=user_to_claim, 
                message=f"{current_user.username} assigned '{item.name}' to you."
            )
            db.add(notif)
    
    db.commit()
    return {"message": "Claim updated"}

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    quantity: Optional[int] = None

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
    
    # Check permissions (uploader only)
    receipt = db.get(Receipt, receipt_id)
    if receipt.uploader_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only uploader can edit items")
        
    if data.name is not None:
        item.name = data.name
    if data.price is not None:
        item.price = data.price
    if data.quantity is not None:
        item.quantity = data.quantity
        
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.post("/{receipt_id}/items/{item_id}/split-quantity")
def split_item_quantity(
    receipt_id: int,
    item_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    item = db.get(Item, item_id)
    if not item or item.receipt_id != receipt_id or item.quantity <= 1:
        raise HTTPException(status_code=400, detail="Cannot split this item")
    
    # Create a new item with quantity 1
    new_item = Item(
        receipt_id=receipt_id,
        name=item.name,
        price=item.price,
        quantity=1
    )
    # Reduce original quantity
    item.quantity -= 1
    
    db.add(new_item)
    db.add(item)
    db.commit()
    return {"message": "Item split"}

@router.post("/{receipt_id}/finalize")
def finalize_receipt(
    receipt_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    receipt = db.get(Receipt, receipt_id)
    if receipt.uploader_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the uploader can finalize")
    
    # Check if all items are claimed
    for item in receipt.items:
        if not item.contributions:
            raise HTTPException(status_code=400, detail=f"Item '{item.name}' is not claimed by anyone")
    
    # Calculate splits
    for item in receipt.items:
        num_claimants = len(item.contributions)
        total_price = item.price * item.quantity
        
        base_amount = total_price // num_claimants
        remainder = total_price % num_claimants
        
        for i, contrib in enumerate(item.contributions):
            contrib.amount = base_amount
            if i == 0: # First claimant gets the remainder
                contrib.amount += remainder
            db.add(contrib)
    
    receipt.status = "split"
    db.add(receipt)
    db.commit()
    return {"message": "Receipt finalized and split"}

@router.post("/{receipt_id}/archive")
def archive_receipt(
    receipt_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    receipt = db.get(Receipt, receipt_id)
    if receipt.uploader_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the uploader can archive")
    
    receipt.status = "archived"
    db.add(receipt)
    db.commit()
    return {"message": "Receipt archived"}

@router.post("/{receipt_id}/revert")
def revert_receipt(
    receipt_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if receipt.uploader_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the uploader can revert")
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
    if receipt.uploader_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the uploader can delete")
    
    # Delete file if exists
    if os.path.exists(receipt.image_path):
        os.remove(receipt.image_path)
        
    db.delete(receipt)
    db.commit()
    return {"message": "Receipt deleted"}
