from fastapi import FastAPI, Depends, HTTPException, status, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from app.database import get_session, init_db
from app.models import User, Notification
from app.auth import get_password_hash, verify_password, create_access_token, create_refresh_token, get_current_user
from app.receipts import router as receipts_router
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import text, inspect

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
    # Auto-migration for color column
    from app.database import engine
    with engine.connect() as conn:
        try:
            conn.execute(text("SELECT color FROM \"user\" LIMIT 1"))
        except Exception:
            # Column likely missing
            print("Migrating database: Adding color column to user table")
            conn.rollback() # Important to rollback the failed transaction
            trans = conn.begin()
            try:
                conn.execute(text("ALTER TABLE \"user\" ADD COLUMN color VARCHAR DEFAULT '#3B82F6'"))
                trans.commit()
            except Exception as e:
                trans.rollback()
                print(f"Migration failed (color): {e}")

        try:
            conn.execute(text("SELECT mismatch FROM \"receipt\" LIMIT 1"))
        except Exception:
            print("Migrating database: Adding mismatch column to receipt table")
            conn.rollback()
            trans = conn.begin()
            try:
                conn.execute(text("ALTER TABLE \"receipt\" ADD COLUMN mismatch BOOLEAN DEFAULT FALSE"))
                trans.commit()
            except Exception as e:
                trans.rollback()
                print(f"Migration failed (mismatch): {e}")

class AuthRequest(BaseModel):
    username: str
    password: str

class UserUpdate(BaseModel):
    password: Optional[str] = None
    color: Optional[str] = None

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
    refresh_token = create_refresh_token(data={"sub": user.username})

    # Access token: short-lived, accessible
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=15 * 60,  # 15 minutes
        samesite="lax",
        secure=False,
    )

    # Refresh token: long-lived, HttpOnly, specific path
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=30 * 24 * 60 * 60,  # 30 days
        samesite="lax",
        secure=False,
        path="/api/auth/refresh", 
    )
    return {"message": "Logged in successfully", "username": user.username}

@app.post("/api/auth/refresh")
def refresh_token(request: Request, response: Response, db: Session = Depends(get_session)):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    from app.auth import SECRET_KEY, ALGORITHM
    from jose import jwt, JWTError
    
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        if username is None or token_type != "refresh":
             raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # Verify user still exists
        statement = select(User).where(User.username == username)
        user = db.exec(statement).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")

        # Create new access token
        access_token = create_access_token(data={"sub": user.username})
        
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=15 * 60,  # 15 minutes
            samesite="lax",
            secure=False,
        )
        return {"message": "Token refreshed"}

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token", path="/api/auth/refresh")
    return {"message": "Logged out successfully"}

@app.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "id": current_user.id, "color": current_user.color}

@app.put("/api/auth/me")
def update_me(data: UserUpdate, db: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if data.password:
        current_user.hashed_password = get_password_hash(data.password)
    if data.color:
        current_user.color = data.color
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return {"message": "Profile updated", "user": {"id": current_user.id, "username": current_user.username, "color": current_user.color}}

@app.get("/api/users")
def list_users(db: Session = Depends(get_session)):
    users = db.exec(select(User)).all()
    return [{"id": u.id, "username": u.username, "color": u.color} for u in users]

@app.get("/api/notifications")
def list_notifications(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    statement = select(Notification).where(Notification.user_id == current_user.id).order_by(Notification.created_at.desc())
    notifs = db.exec(statement).all()
    return notifs

@app.post("/api/notifications/{notif_id}/read")
def mark_notification_read(
    notif_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    notif = db.get(Notification, notif_id)
    if not notif or notif.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notif.read = True
    db.add(notif)
    db.commit()
    return {"message": "Marked as read"}
