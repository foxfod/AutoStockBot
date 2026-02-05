from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

SQLC_DATABASE_URL = "sqlite:///./sql_app.db"
# Use check_same_thread=False for SQLite with FastAPI/multithreading
connect_args = {"check_same_thread": False}

engine = create_engine(
    SQLC_DATABASE_URL, connect_args=connect_args
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
