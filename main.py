import boto3
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException

app = FastAPI()

@app.get("/")
async def get_success():
    return {"status": "success"}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    s3_client = boto3.client('s3')
    key = f"receipts/{file.filename}"
    
    try:
        s3_client.upload_fileobj(file.file, "dobby-poc", key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    return {"status": "success", "s3_key": key}
