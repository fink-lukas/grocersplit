from typing import List, Optional
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    color: str = Field(default="#3B82F6")

    receipts_uploaded: List["Receipt"] = Relationship(back_populates="uploader")
    contributions: List["Contribution"] = Relationship(back_populates="user")
    participations: List["ReceiptParticipant"] = Relationship(back_populates="user")

class Receipt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    uploader_id: int = Field(foreign_key="user.id")
    image_path: str
    description: Optional[str] = None
    total_amount: int = 0  # In cents
    status: str = Field(default="pending")  # pending, split, archived
    created_at: datetime = Field(default_factory=datetime.utcnow)

    uploader: User = Relationship(back_populates="receipts_uploaded")
    items: List["Item"] = Relationship(back_populates="receipt")
    participants: List["ReceiptParticipant"] = Relationship(back_populates="receipt")

class ReceiptParticipant(SQLModel, table=True):
    receipt_id: int = Field(foreign_key="receipt.id", primary_key=True)
    user_id: int = Field(foreign_key="user.id", primary_key=True)

    receipt: Receipt = Relationship(back_populates="participants")
    user: User = Relationship(back_populates="participations")

class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    receipt_id: int = Field(foreign_key="receipt.id")
    name: str
    price: int  # In cents
    quantity: int = 1

    receipt: Receipt = Relationship(back_populates="items")
    contributions: List["Contribution"] = Relationship(back_populates="item")

class Contribution(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="item.id")
    user_id: int = Field(foreign_key="user.id")
    amount: int  # In cents

    item: Item = Relationship(back_populates="contributions")
    user: User = Relationship(back_populates="contributions")

User.update_forward_refs()
Receipt.update_forward_refs()
Item.update_forward_refs()
Contribution.update_forward_refs()
