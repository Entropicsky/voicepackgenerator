# backend/models.py
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, JSON, ForeignKey, func, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.dialects import postgresql # Import postgresql dialect
from datetime import datetime
import os

# Database setup (PostgreSQL or SQLite)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Fallback to SQLite for basic local testing if DATABASE_URL is not set
    # This is NOT recommended for Docker setup, use docker-compose env var instead
    print("WARNING: DATABASE_URL not set, falling back to local SQLite file './jobs.db'")
    DATABASE_URL = "sqlite:///./jobs.db" # Relative path for non-Docker fallback
    engine_args = {"connect_args": {"check_same_thread": False}}
else:
    # Heroku provides postgres://, SQLAlchemy prefers postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    # Standard engine args for PostgreSQL
    engine_args = {"pool_pre_ping": True, "pool_size": 10, "max_overflow": 20}

engine = create_engine(DATABASE_URL, **engine_args)
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
    # Use JSONB variant for Postgres
    parameters_json = Column(JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True)
    result_message = Column(Text, nullable=True)
    # Use JSONB variant for Postgres
    result_batch_ids_json = Column(JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True)
    
    # New fields for tracking job type and target
    job_type = Column(String, default="full_batch") # E.g., 'full_batch', 'line_regen'
    target_batch_id = Column(String, nullable=True) # For line_regen jobs
    target_line_key = Column(String, nullable=True) # For line_regen jobs

# --- NEW: Script Management Models --- #

class Script(Base):
    __tablename__ = "scripts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    is_archived = Column(Boolean, nullable=False, default=False, server_default='false', index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    lines = relationship(
        "ScriptLine", 
        back_populates="script", 
        cascade="all, delete-orphan", # Delete lines when script is deleted
        order_by="ScriptLine.order_index" # Default ordering when accessing script.lines
    )

class ScriptLine(Base):
    __tablename__ = "script_lines"

    id = Column(Integer, primary_key=True)
    script_id = Column(Integer, ForeignKey("scripts.id"), nullable=False, index=True)
    line_key = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    order_index = Column(Integer, nullable=False)

    script = relationship("Script", back_populates="lines")

# --- End Script Management Models --- #

def init_db():
    """Create database tables if they don't exist."""
    # This function might still be useful for initial local SQLite setup,
    # but less critical for Postgres managed by Alembic.
    # Keep it for now, but migrations are the primary mechanism.
    print("Initializing database connection (migrations handle table creation)...")
    try:
        # Test connection
        with engine.connect() as connection:
             print("Database connection successful.")
        # Base.metadata.create_all(bind=engine) # Table creation handled by Alembic
        # print("Tables checked/created (if needed).")
    except Exception as e:
        print(f"Database connection/initialization check failed: {e}")
        raise

# Dependency for FastAPI-style dependency injection (can adapt for Flask)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 