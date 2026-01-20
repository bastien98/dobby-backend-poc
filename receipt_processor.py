import base64
import io
from typing import List, Literal
from pdf2image import convert_from_path
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

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

# 2. Helper: Convert PDF to Base64 Images
def load_pdf_as_images(pdf_path):
    # Convert PDF pages to PIL images with high DPI for better OCR quality
    images = convert_from_path(pdf_path, dpi=300)
    
    encoded_images = []
    for img in images:
        # Resize if necessary to save tokens/bandwidth (optional)
        # img.thumbnail((1024, 1024)) 
        
        buffered = io.BytesIO()
        # Use high quality JPEG to preserve text details without the massive size of PNG
        img.save(buffered, format="JPEG", quality=100, subsampling=0)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        encoded_images.append(img_str)
        
    return encoded_images

# 3. The Vision Agent Function
# 3. The Vision Agent Function
def analyze_receipt_visually(pdf_path):
    # Setup LLM with Structured Output
    # Ensure OPENAI_API_KEY is set in environment
    # Use gpt-4o for best multimodal performance
    llm = ChatOpenAI(model="gpt-5", temperature=0)
    structured_llm = llm.with_structured_output(ReceiptExtraction)
    
    # Get images
    base64_images = load_pdf_as_images(pdf_path)
    
    # Prepare the message content
    # We add the text instructions + all receipt images
    content_payload = [
        {
            "type": "text",
            "text": """
            Extract the receipt data from these images with high precision.
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
        },
    ]
    
    # Append each page image to the payload
    for img_str in base64_images:
        content_payload.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img_str}"}
        })

    # Create the message
    message = HumanMessage(content=content_payload)
    
    # Invoke the chain
    # Note: We pass the message list directly to the structured LLM
    result = structured_llm.invoke([message])
    
    return result
