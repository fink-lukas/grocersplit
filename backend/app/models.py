from typing import List, Optional
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    color: str = Field(default="#3B82F6")
    is_active: bool = Field(default=True)

    receipts_uploaded: List["Receipt"] = Relationship(back_populates="uploader")
    contributions: List["Contribution"] = Relationship(back_populates="user")
    participations: List["ReceiptParticipant"] = Relationship(back_populates="user")
    notifications: List["Notification"] = Relationship(back_populates="user")


class Notification(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    message: str
    read: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: User = Relationship(back_populates="notifications")


class Product(SQLModel, table=True):
    """
    Canonical Master Product for habit tracking, categorizing, and price history.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)  # Clean canonical name, e.g. "Ja! Vollmilch 3.5%"
    category: Optional[str] = Field(default=None, index=True)  # e.g. "Dairy", "Produce", "Meat"
    tags: Optional[str] = Field(default="[]")  # JSON string of tags e.g. '["Dairy", "Essentials"]'
    default_unit: Optional[str] = Field(default=None)  # "piece", "kg", "l", "pack"
    
    # Future-proof nutritional / macro fields
    calories: Optional[float] = Field(default=None)
    protein: Optional[float] = Field(default=None)
    carbs: Optional[float] = Field(default=None)
    fat: Optional[float] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)

    aliases: List["ProductAlias"] = Relationship(
        back_populates="product",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    items: List["Item"] = Relationship(back_populates="product")


class ProductAlias(SQLModel, table=True):
    """
    Maps cryptic supermarket receipt strings or SKUs to a canonical Product.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    raw_text: str = Field(index=True)  # Raw receipt string, e.g. "JA! MILCH 3.5"
    sku: Optional[str] = Field(default=None, index=True)  # Barcode / article code, e.g. "106876"
    store: Optional[str] = Field(default=None)  # e.g. "HOFER", "BILLA", "SPAR"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    product: Optional[Product] = Relationship(back_populates="aliases")


class Receipt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    uploader_id: int = Field(foreign_key="user.id")
    image_path: str
    description: Optional[str] = None
    merchant_name: Optional[str] = Field(default=None)
    purchase_date: Optional[datetime] = Field(default=None, index=True)
    raw_json: Optional[str] = Field(default=None)
    total_amount: int = 0  # In cents
    status: str = Field(default="pending")  # pending, split, archived
    mismatch: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    uploader: User = Relationship(back_populates="receipts_uploaded")
    items: List["Item"] = Relationship(
        back_populates="receipt",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    participants: List["ReceiptParticipant"] = Relationship(
        back_populates="receipt",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class ReceiptParticipant(SQLModel, table=True):
    receipt_id: int = Field(foreign_key="receipt.id", primary_key=True)
    user_id: int = Field(foreign_key="user.id", primary_key=True)

    receipt: Receipt = Relationship(back_populates="participants")
    user: User = Relationship(back_populates="participations")


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    receipt_id: int = Field(foreign_key="receipt.id")
    product_id: Optional[int] = Field(default=None, foreign_key="product.id", nullable=True)

    name: str  # Display name (or canonical name if matched)
    raw_name: Optional[str] = Field(default=None)  # Raw OCR text from receipt for alias matching
    sku: Optional[str] = Field(default=None)  # Article code / barcode
    item_type: str = Field(default="product")  # "product", "deposit" (Pfand), "cart_discount"

    price: int  # Net payable amount in CENTS
    original_price: Optional[int] = Field(default=None)  # Before discount, in cents
    discount_amount: int = Field(default=0)  # Deducted discount in cents

    quantity: float = Field(default=1.0)  # Float to support weighted produce e.g. 0.646 kg
    unit: Optional[str] = Field(default=None)  # "piece", "kg", "pack"
    notes: Optional[str] = Field(default=None)  # Linked beverage or storno details

    receipt: Receipt = Relationship(back_populates="items")
    product: Optional[Product] = Relationship(back_populates="items")
    contributions: List["Contribution"] = Relationship(
        back_populates="item",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class Contribution(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="item.id")
    user_id: int = Field(foreign_key="user.id")
    amount: int  # In cents

    item: Item = Relationship(back_populates="contributions")
    user: User = Relationship(back_populates="contributions")


User.update_forward_refs()
Receipt.update_forward_refs()
Product.update_forward_refs()
ProductAlias.update_forward_refs()
Item.update_forward_refs()
Contribution.update_forward_refs()
Notification.update_forward_refs()


class Category(SQLModel, table=True):
    name: str = Field(primary_key=True)


class Tag(SQLModel, table=True):
    name: str = Field(primary_key=True)
