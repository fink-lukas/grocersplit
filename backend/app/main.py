from fastapi import FastAPI, Depends, HTTPException, status, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from app.database import get_session, init_db
from app.models import User
from app.auth import get_password_hash, verify_password, create_access_token, get_current_user
from app.receipts import router as receipts_router
from pydantic import BaseModel
from typing import List

from fastapi.staticfiles import StaticFiles

# ...

app = FastAPI(title="GrocerSplit v2")
app.mount("/api/uploads", StaticFiles(directory="uploads"), name="uploads")
app.include_router(receipts_router)

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

class AuthRequest(BaseModel):
    username: str
    password: str

@app.post("/api/auth/register")
def register(data: AuthRequest, db: Session = Depends(get_session)):
    statement = select(User).where(User.username == data.username)
    existing_user = db.exec(statement).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    user = User(
        username=data.username,
        hashed_password=get_password_hash(data.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User created successfully"}

@app.post("/api/auth/login")
def login(data: AuthRequest, response: Response, db: Session = Depends(get_session)):
    statement = select(User).where(User.username == data.username)
    user = db.exec(statement).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user.username})
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=10080 * 60,  # 7 days
        samesite="lax",
        secure=False, # Important for localhost http
    )
    return {"message": "Logged in successfully", "username": user.username}

@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully"}

@app.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "id": current_user.id}

@app.get("/api/users")
def list_users(db: Session = Depends(get_session)):
    users = db.exec(select(User)).all()
    return [{"id": u.id, "username": u.username} for u in users]
