from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from app.database import get_session
from app.models import User
from app.auth import get_current_user

router = APIRouter(prefix="/api/users", tags=["users"])


class UserStatusUpdate(BaseModel):
    is_active: bool


@router.get("")
def list_users(db: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    users = db.exec(select(User).order_by(User.id.asc())).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "color": u.color,
            "is_active": u.is_active
        }
        for u in users
    ]


@router.put("/{user_id}/status")
def update_user_status(
    user_id: int,
    data: UserStatusUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = data.is_active
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "color": user.color,
        "is_active": user.is_active
    }
