from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.database import get_session
from app.models import User

from app.auth import get_current_user

router = APIRouter(prefix="/api/users", tags=["users"])

@router.get("")
def list_users(db: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    users = db.exec(select(User)).all()
    return [{"id": u.id, "username": u.username, "color": u.color} for u in users]
