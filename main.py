import boto3
import uuid
import os
import shutil
from tempfile import NamedTemporaryFile
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Depends
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
            receipt.line_items = [item.dict() for item in result.line_items]
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
