from fastapi import FastAPI, Depends, HTTPException, status, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from app.database import get_session, init_db
from app.models import User, Notification, Product, ProductAlias, Item, Receipt, ReceiptParticipant, Contribution
from app.auth import get_password_hash, verify_password, create_access_token, create_refresh_token, get_current_user
from app.receipts import router as receipts_router
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.notifications import router as notifications_router
from app.routers.products import router as products_router
from app.routers.analytics import router as analytics_router
from app.routers.review_tool import router as review_router
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import text

from fastapi.staticfiles import StaticFiles

# ...

app = FastAPI(title="GrocerSplit v2")
app.mount("/api/uploads", StaticFiles(directory="uploads"), name="uploads")
app.include_router(receipts_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(notifications_router)
app.include_router(products_router)
app.include_router(analytics_router)
app.include_router(review_router)


# CORS configuration
app.add_middleware(
    CORSMiddleware,
    # allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], 
    allow_origin_regex=r"https?://.*", # Allow any local or Tailscale origin (http or https)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    try:
        init_db()
    except Exception as e:
        print(f"init_db warning: {e}")

    # Safe additive migrations for database tables and columns
    from app.database import engine
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS color VARCHAR DEFAULT '#3B82F6';"))
            conn.execute(text("ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
            conn.execute(text("UPDATE \"user\" SET is_active = FALSE WHERE username = 'Alex';"))
            conn.execute(text("ALTER TABLE \"receipt\" ADD COLUMN IF NOT EXISTS mismatch BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE \"receipt\" ADD COLUMN IF NOT EXISTS purchase_date TIMESTAMP WITHOUT TIME ZONE;"))
            conn.execute(text("ALTER TABLE \"receipt\" ADD COLUMN IF NOT EXISTS merchant_name VARCHAR;"))
            conn.execute(text("ALTER TABLE \"receipt\" ADD COLUMN IF NOT EXISTS raw_json TEXT;"))
            conn.execute(text("ALTER TABLE \"item\" ADD COLUMN IF NOT EXISTS product_id INTEGER REFERENCES product(id) ON DELETE SET NULL;"))
            conn.execute(text("ALTER TABLE \"item\" ADD COLUMN IF NOT EXISTS raw_name VARCHAR;"))
            conn.execute(text("ALTER TABLE \"item\" ADD COLUMN IF NOT EXISTS sku VARCHAR;"))
            conn.execute(text("ALTER TABLE \"item\" ADD COLUMN IF NOT EXISTS item_type VARCHAR DEFAULT 'product';"))
            conn.execute(text("ALTER TABLE \"item\" ADD COLUMN IF NOT EXISTS original_price INTEGER;"))
            conn.execute(text("ALTER TABLE \"item\" ADD COLUMN IF NOT EXISTS discount_amount INTEGER DEFAULT 0;"))
            conn.execute(text("ALTER TABLE \"item\" ADD COLUMN IF NOT EXISTS unit VARCHAR;"))
            conn.execute(text("ALTER TABLE \"item\" ADD COLUMN IF NOT EXISTS notes VARCHAR;"))
            conn.execute(text("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'item' AND column_name = 'quantity' AND data_type = 'integer'
                    ) THEN
                        ALTER TABLE "item" ALTER COLUMN quantity TYPE DOUBLE PRECISION USING quantity::double precision;
                    END IF;
                END $$;
            """))
        print("Database migrations checked and applied successfully.")
    except Exception as e:
        print(f"Startup migration warning: {e}")
