import sys
import os
from pathlib import Path

# Ensure backend directory is on sys.path for direct script execution
backend_dir = str(Path(__file__).resolve().parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlmodel import Session, select
from app.database import engine
from app.models import User
from app.auth import get_password_hash

def list_users():
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        for user in users:
            print(f"ID: {user.id}, Username: {user.username}, Active: {user.is_active}")

def set_user_active(username: str, is_active: bool):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if user:
            user.is_active = is_active
            session.add(user)
            session.commit()
            status_str = "activated" if is_active else "deactivated"
            print(f"User '{username}' {status_str}.")
        else:
            print(f"User '{username}' not found.")

def delete_user(username):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if user:
            session.delete(user)
            session.commit()
            print(f"User '{username}' deleted.")
        else:
            print(f"User '{username}' not found.")

def reset_password(username, new_password):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if user:
            user.hashed_password = get_password_hash(new_password)
            session.add(user)
            session.commit()
            print(f"Password for '{username}' updated.")
        else:
            print(f"User '{username}' not found.")

def create_user(username, password):
    with Session(engine) as session:
        existing = session.exec(select(User).where(User.username == username)).first()
        if existing:
            print(f"User '{username}' already exists.")
            return
        hashed_pw = get_password_hash(password)
        new_user = User(username=username, hashed_password=hashed_pw)
        session.add(new_user)
        session.commit()
        print(f"User '{username}' created.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python manage_users.py <action> [args]")
        print("Actions: list, activate <username>, deactivate <username>, delete <username>, reset <username> <new_password>, create <username> <new_password>")
        sys.exit(1)
    
    action = sys.argv[1]
    if action == "list":
        list_users()
    elif action == "activate" and len(sys.argv) == 3:
        set_user_active(sys.argv[2], True)
    elif action == "deactivate" and len(sys.argv) == 3:
        set_user_active(sys.argv[2], False)
    elif action == "delete" and len(sys.argv) == 3:
        delete_user(sys.argv[2])
    elif action == "reset" and len(sys.argv) == 4:
        reset_password(sys.argv[2], sys.argv[3])
    elif action == "create" and len(sys.argv) == 4:
        create_user(sys.argv[2], sys.argv[3])
    else:
        print("Invalid arguments.")
