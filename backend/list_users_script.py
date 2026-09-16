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

def list_users():
    print("Connecting to database...")
    try:
        with Session(engine) as session:
            users = session.exec(select(User)).all()
            if not users:
                print("No users found.")
            else:
                print(f"Found {len(users)} users:")
                for user in users:
                    print(f"ID: {user.id}, Username: {user.username}")
    except Exception as e:
        print(f"Error querying database: {e}")

if __name__ == "__main__":
    list_users()
