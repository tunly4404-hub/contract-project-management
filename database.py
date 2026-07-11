import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Support external persistent PostgreSQL (or fallback to SQLite)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL or not DATABASE_URL.strip():
    persistent_dir = "/data" if os.path.exists("/data") and os.path.isdir("/data") else "."
    DATABASE_URL = f"sqlite:///{persistent_dir}/projects.db"

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    try:
        # Test connection to ensure host is reachable and credentials are valid
        temp_engine = create_engine(DATABASE_URL)
        with temp_engine.connect() as conn:
            pass
        engine = create_engine(
            DATABASE_URL,
            pool_size=10,
            max_overflow=20,
            pool_recycle=1800
        )
        print("Successfully connected to external PostgreSQL database.")
    except Exception as e:
        print(f"Warning: Failed to connect to PostgreSQL database. Falling back to local SQLite. Error: {e}")
        persistent_dir = "/data" if os.path.exists("/data") and os.path.isdir("/data") else "."
        DATABASE_URL = f"sqlite:///{persistent_dir}/projects.db"
        engine = create_engine(
            DATABASE_URL, connect_args={"check_same_thread": False}
        )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
