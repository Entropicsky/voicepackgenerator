# backend/models.py
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
import os

# Database setup (SQLite)
# Use an absolute path or path relative to where app runs (inside container: /app)
DATABASE_URL = "sqlite:////app/jobs.db" 
# For local testing without Docker, might use: "sqlite:///jobs.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}) # check_same_thread for SQLite
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id = Column(Integer, primary_key=True, index=True)
    celery_task_id = Column(String, index=True, unique=True, nullable=True)
    status = Column(String, default="PENDING", index=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    parameters_json = Column(Text, nullable=True) # Store input config as JSON string
    result_message = Column(Text, nullable=True) # Store success message or error details
    result_batch_ids_json = Column(Text, nullable=True) # Store list of generated batch IDs as JSON string

def init_db():
    """Create database tables."""
    print("Initializing database and creating tables if they don't exist...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Database initialization complete.")
    except Exception as e:
        print(f"Database initialization failed: {e}")
        raise # Re-raise the exception after logging

# Dependency for FastAPI-style dependency injection (can adapt for Flask)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 