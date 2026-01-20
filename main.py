import boto3
import uuid
import os
import shutil
from datetime import datetime
from collections import defaultdict
from typing import List
from tempfile import NamedTemporaryFile
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from receipt_processor import analyze_receipt_visually
from database import engine, SessionLocal, Base, Receipt

# Create tables
if engine:
    Base.metadata.create_all(bind=engine)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
async def get_success():
    return {"status": "success"}

def process_receipt_background(file_path: str, receipt_id: uuid.UUID):
    db = SessionLocal()
    try:
        print(f"Starting receipt analysis for: {file_path}")
        result = analyze_receipt_visually(file_path)
        print(f"Extraction Result: {result}")
        
        # Update DB
        receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
        if receipt:
            receipt.store_name = result.store_name
            receipt.total_paid = result.total_paid
            receipt.timestamp = result.timestamp
            # Convert Pydantic models to dicts for JSON storage
            receipt.line_items = [item.model_dump() for item in result.line_items]
            db.commit()
            print(f"Updated receipt {receipt_id} in DB")
            
    except Exception as e:
        print(f"Error processing receipt: {e}")
    finally:
        db.close()
        # Clean up the temp file
        if os.path.exists(file_path):
            os.remove(file_path)

@app.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    
    # Configure S3 Client
    s3_endpoint = os.getenv("S3_ENDPOINT_URL")
    s3_bucket = os.getenv("S3_BUCKET_NAME", "dobby-receipts")
    
    s3_client = boto3.client(
        's3',
        endpoint_url=s3_endpoint,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    )
    
    key = f"receipts/{file.filename}"
    
    # Create DB record first
    new_receipt = Receipt(s3_key=key)
    db.add(new_receipt)
    db.commit()
    db.refresh(new_receipt)
    
    # Save to temp file for processing
    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    
    # Reset cursor for S3 upload
    file.file.seek(0)
    
    try:
        s3_client.upload_fileobj(file.file, s3_bucket, key)
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))
        
    # Trigger background processing
    background_tasks.add_task(process_receipt_background, tmp_path, new_receipt.id)
    
    return {"status": "success", "s3_key": key, "receipt_id": str(new_receipt.id)}

class CategoryBreakdown(BaseModel):
    name: str
    spent: float
    percentage: int

class StoreBreakdownResponse(BaseModel):
    store_name: str
    period: str
    total_store_spend: float
    categories: List[CategoryBreakdown]

@app.get("/store-breakdown", response_model=List[StoreBreakdownResponse])
async def get_store_breakdown(db: Session = Depends(get_db)):
    receipts = db.query(Receipt).all()
    
    # Nested dictionary: results[store_name][period] = {"total_spend": 0.0, "categories": {cat_name: spent}}
    breakdown = defaultdict(lambda: defaultdict(lambda: {"total": 0.0, "categories": defaultdict(float)}))
    
    for r in receipts:
        if not r.timestamp or not r.store_name:
            continue
            
        try:
            # Parse timestamp (expected format: YYYY-MM-DD HH:MM)
            dt = datetime.strptime(r.timestamp, "%Y-%m-%d %H:%M")
            period = dt.strftime("%B %Y")
        except Exception:
            # Fallback if format is different or unparseable
            period = "Unknown Period"
            
        store = r.store_name
        
        # Aggregate data
        line_items = r.line_items or []
        for item in line_items:
            cat = item.get("category", "Unknown")
            price = item.get("price", 0.0)
            
            breakdown[store][period]["total"] += price
            breakdown[store][period]["categories"][cat] += price
            
    # Format into response structure
    response = []
    for store_name, periods in breakdown.items():
        for period, data in periods.items():
            total_spend = data["total"]
            if total_spend == 0:
                continue
                
            categories_list = []
            for cat_name, spent in data["categories"].items():
                percentage = int(round((spent / total_spend) * 100))
                categories_list.append(CategoryBreakdown(
                    name=cat_name,
                    spent=round(spent, 2),
                    percentage=percentage
                ))
            
            # Sort categories by spent descending (optional but good for UX)
            categories_list.sort(key=lambda x: x.spent, reverse=True)
            
            response.append(StoreBreakdownResponse(
                store_name=store_name,
                period=period,
                total_store_spend=round(total_spend, 2),
                categories=categories_list
            ))
            
    # Sort response by period/store (optional)
    return response
