import os
import uuid
from sqlalchemy import create_engine, Column, String, UUID, JSON
from sqlalchemy.orm import sessionmaker, declarative_base

# Get DATABASE_URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

# Create engine
# If no DB URL is set, this will fail at runtime, which is expected
engine = create_engine(DATABASE_URL) if DATABASE_URL else None

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_name = Column(String, nullable=True)
    total_paid = Column(String, nullable=True)
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
