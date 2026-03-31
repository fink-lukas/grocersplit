from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models import User, Notification
from app.auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

@router.get("")
def list_notifications(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    statement = select(Notification).where(Notification.user_id == current_user.id).order_by(Notification.created_at.desc())
    notifs = db.exec(statement).all()
    return notifs

@router.post("/{notif_id}/read")
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
