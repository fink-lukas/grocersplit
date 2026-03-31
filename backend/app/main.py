from fastapi import FastAPI, Depends, HTTPException, status, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from app.database import get_session, init_db
from app.models import User, Notification
from app.auth import get_password_hash, verify_password, create_access_token, create_refresh_token, get_current_user
from app.receipts import router as receipts_router
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.notifications import router as notifications_router
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import text, inspect

from fastapi.staticfiles import StaticFiles

# ...

app = FastAPI(title="GrocerSplit v2")
app.mount("/api/uploads", StaticFiles(directory="uploads"), name="uploads")
app.include_router(receipts_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(notifications_router)

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
    init_db()

