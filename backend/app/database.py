import time
from sqlmodel import create_engine, Session, SQLModel
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, echo=True)

def init_db(max_retries: int = 10, retry_delay: float = 1.5):
    for attempt in range(1, max_retries + 1):
        try:
            SQLModel.metadata.create_all(engine)
            print("Database initialized successfully.")
            return
        except Exception as e:
            if attempt == max_retries:
                print(f"Failed to initialize database after {max_retries} attempts: {e}")
                raise e
            print(f"Waiting for database connection (attempt {attempt}/{max_retries})... {e}")
            time.sleep(retry_delay)

def get_session():
    with Session(engine) as session:
        yield session
