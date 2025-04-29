# backend/models.py
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, JSON, ForeignKey, func, Boolean, Index
from sqlalchemy import sql
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
    job_type = Column(String, default="full_batch") # E.g., 'full_batch', 'line_regen', 'sts_line_regen', 'script_creation'
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

# --- NEW: VO Script Creator Models --- #

class VoScriptTemplate(Base):
    __tablename__ = "vo_script_templates"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    prompt_hint = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    categories = relationship("VoScriptTemplateCategory", back_populates="template", cascade="all, delete-orphan")
    template_lines = relationship("VoScriptTemplateLine", back_populates="template", cascade="all, delete-orphan")
    vo_scripts = relationship("VoScript", back_populates="template") # Don't cascade delete scripts if template is deleted

class VoScriptTemplateCategory(Base):
    __tablename__ = "vo_script_template_categories"
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("vo_script_templates.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    prompt_instructions = Column(Text, nullable=True)
    refinement_prompt = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    template = relationship("VoScriptTemplate", back_populates="categories")
    template_lines = relationship("VoScriptTemplateLine", back_populates="category", cascade="all, delete-orphan")

    # Ensure category names are unique within a template
    __table_args__ = (Index('uq_category_template_name', 'template_id', 'name', unique=True),)

class VoScriptTemplateLine(Base):
    __tablename__ = "vo_script_template_lines"
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("vo_script_templates.id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("vo_script_template_categories.id"), nullable=True, index=True)
    line_key = Column(String(255), nullable=False)
    order_index = Column(Integer, nullable=False)
    prompt_hint = Column(Text, nullable=True)
    static_text = Column(Text, nullable=True)  # NEW: Static text that bypasses LLM generation
    is_deleted = Column(Boolean, nullable=False, default=False, server_default=sql.false())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    template = relationship("VoScriptTemplate", back_populates="template_lines")
    category = relationship("VoScriptTemplateCategory", back_populates="template_lines")
    vo_script_lines = relationship("VoScriptLine", back_populates="template_line", cascade="all, delete-orphan")

    # Ensure line keys are unique within a template
    __table_args__ = (Index('uq_template_line_key', 'template_id', 'line_key', unique=True),)

class VoScript(Base):
    __tablename__ = "vo_scripts"
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("vo_script_templates.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True) # Allow duplicate names initially?
    character_description = Column(Text, nullable=True)
    refinement_prompt = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default='drafting', index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    template = relationship("VoScriptTemplate", back_populates="vo_scripts")
    lines = relationship("VoScriptLine", back_populates="vo_script", cascade="all, delete-orphan", order_by="VoScriptLine.id") # Order by ID or join template line order?

class VoScriptLine(Base):
    __tablename__ = "vo_script_lines"
    id = Column(Integer, primary_key=True)
    vo_script_id = Column(Integer, ForeignKey("vo_scripts.id"), nullable=False, index=True)
    template_line_id = Column(Integer, ForeignKey("vo_script_template_lines.id"), nullable=True, index=True)
    category_id = Column(Integer, ForeignKey("vo_script_template_categories.id"), nullable=True, index=True)
    line_key = Column(String(255), nullable=True)
    order_index = Column(Integer, nullable=True)
    prompt_hint = Column(Text, nullable=True)
    generated_text = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default='pending', index=True)
    generation_history = Column(JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True) # Optional history
    latest_feedback = Column(Text, nullable=True)
    is_locked = Column(Boolean, nullable=False, default=False, server_default=sql.false())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    vo_script = relationship("VoScript", back_populates="lines")
    template_line = relationship("VoScriptTemplateLine", back_populates="vo_script_lines")

# --- End VO Script Creator Models --- #

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