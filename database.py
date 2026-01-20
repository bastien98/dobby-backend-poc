import os
import uuid
from sqlalchemy import create_engine, Column, String, UUID, JSON, Float
from sqlalchemy.orm import sessionmaker, declarative_base

# Get DATABASE_URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

# Create engine
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Create engine
engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_name = Column(String, nullable=True)
    total_paid = Column(Float, nullable=True)
    timestamp = Column(String, nullable=True)
    # Storing line items as JSON for flexibility
    line_items = Column(JSON, nullable=True) 
    s3_key = Column(String, nullable=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
