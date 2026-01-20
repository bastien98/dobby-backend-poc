import os
import time
from typing import List, Literal
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# 1. Define Categories & Schema (Same as before)
CategoryType = Literal[
    "Alcohol", "Tobacco", "Fresh Produce", "Meat & Fish", "Dairy & Eggs",
    "Bakery", "Pantry", "Ready Meals", "Snacks & Sweets", "Drinks (Soft/Soda)",
    "Drinks (Water)", "Household", "Personal Care", "Pets", "Unknown"
]

class LineItem(BaseModel):
    name: str = Field(..., description="The name of the product purchased.")
    price: float = Field(..., description="The price of the item (e.g., 2.99).")
    category: CategoryType = Field(..., description="The category of the item.")

class ReceiptExtraction(BaseModel):
    store_name: Literal["ALDI", "COLLRUYT"] = Field(..., description="The store name.")
    total_paid: float = Field(..., description="The final total amount paid.")
    timestamp: str = Field(..., description="The date and time of the purchase (format: YYYY-MM-DD HH:MM). If time is missing, use 00:00.")
    line_items: List[LineItem] = Field(..., description="List of all purchased items.")

# 2. Helper: Upload PDF to Gemini File API
def upload_to_gemini(path, mime_type="application/pdf"):
    """
    Uploads the given file to Gemini using the new google.genai Client.
    """
    if not os.getenv("GOOGLE_API_KEY"):
         raise ValueError("GOOGLE_API_KEY not found in environment variables")
         
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    
    # upload_file logic for the new SDK
    # Reference: client.files.upload(file=...)
    file = client.files.upload(file=path)
    
    # Wait for processing
    while file.state.name == "PROCESSING":
        time.sleep(1)
        # Refresh file status
        file = client.files.get(name=file.name)
        
    if file.state.name == "FAILED":
        raise ValueError("File processing failed on Gemini side.")
        
    return file

# 3. The Vision/Document Agent Function
def analyze_receipt_visually(pdf_path):
    # Ensure GOOGLE_API_KEY is set in environment
    if not os.getenv("GOOGLE_API_KEY"):
         raise ValueError("GOOGLE_API_KEY not found in environment variables")
         
    # Upload file
    uploaded_file = upload_to_gemini(pdf_path, mime_type="application/pdf")

    # Setup Client
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    # Prepare Prompt
    prompt = """
    Extract the receipt data from this document.
    1. Identify store (strictly ALDI or COLLRUYT).
    2. Extract Total Paid.
    3. Extract the Timestamp (Date & Time).
    4. Extract EVERY single line item visible. Do not summarize or group items. 
       - For each item, extract the exact price (e.g. 2.99).
       - Categorize strictly using these tags:
         Alcohol, Tobacco, Fresh Produce, Meat & Fish, Dairy & Eggs, Bakery, 
         Pantry, Ready Meals, Snacks & Sweets, Drinks (Soft/Soda), Drinks (Water), 
         Household, Personal Care, Pets, Unknown.
    """

    # Generate Content using native SDK
    # We pass the file object directly (it contains the URI) and the prompt
    # We use response_schema to enforce the Pydantic model structure
    
    response = client.models.generate_content(
        model="gemini-3-pro-preview",
        contents=[uploaded_file, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ReceiptExtraction
        )
    )
    
    # Parse the result
    if not response.parsed:
        raise ValueError("Failed to extract receipt data or parse JSON.")
        
    return response.parsed
