from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import Optional
from app.database import get_session
from app.models import User
from app.auth import get_password_hash, verify_password, create_access_token, create_refresh_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

class AuthRequest(BaseModel):
    username: str
    password: str

class UserUpdate(BaseModel):
    password: Optional[str] = None
    color: Optional[str] = None

@router.post("/register")
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

@router.post("/login")
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

@router.post("/refresh")
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

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token", path="/api/auth/refresh")
    return {"message": "Logged out successfully"}

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "id": current_user.id, "color": current_user.color}

@router.put("/me")
def update_me(data: UserUpdate, db: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if data.password:
        current_user.hashed_password = get_password_hash(data.password)
    if data.color:
        current_user.color = data.color
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return {"message": "Profile updated", "user": {"id": current_user.id, "username": current_user.username, "color": current_user.color}}
