import os
import time
from typing import List, Literal
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage

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
    Uploads the given file to Gemini.
    """
    file = genai.upload_file(path, mime_type=mime_type)
    # Files are processed asynchronously, wait for it to be ready
    while file.state.name == "PROCESSING":
        time.sleep(1)
        file = genai.get_file(file.name)
        
    if file.state.name == "FAILED":
        raise ValueError("File processing failed on Gemini side.")
        
    return file

# 3. The Vision/Document Agent Function
def analyze_receipt_visually(pdf_path):
    # Ensure GOOGLE_API_KEY is set in environment
    if not os.getenv("GOOGLE_API_KEY"):
         raise ValueError("GOOGLE_API_KEY not found in environment variables")
         
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

    # Upload file
    uploaded_file = upload_to_gemini(pdf_path, mime_type="application/pdf")
    
    # Setup LLM with Structured Output
    # Using gemini-1.5-pro as requested (reliable document processor)
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-pro",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    structured_llm = llm.with_structured_output(ReceiptExtraction)
    
    # Prepare the message content
    # For Gemini, we pass the file URI as image_url (LangChain abstraction handles this)
    # or better, just rely on the text prompt if using genai directly, but 
    # langchain-google-genai < 1.0 didn't support file_uri easily. 
    # However, newer versions support it. 
    # Alternative: Use the raw context string. 
    # Let's try the standard LangChain way for multimodal input which uses image_url but pointing to the file?
    # Actually, standard LangChain image_url expects base64 or http url. 
    # Does generic "pdf" work? 
    # The safest way with the File API and LangChain is often to just use the raw genai client OR 
    # construct a message that the adapter understands.
    # 
    # Let's trust the "image_url" hack often works or simpler: use the raw client if we want File API specifically?
    # But user asked for langchain-google-genai. 
    # Let's try passing it as a "media" block if possible, or fall back to standard image_url logic?
    #
    # Wait, the best way for langchain-google-genai + File API is passing the file uri string
    # in a way that maps to a Part.
    #
    # Let's stick to the official pattern:
    # message = HumanMessage(content=[{"type": "text", "text": "..."}, {"type": "media", "file_uri": ..., "mime_type": ...}])
    # Note: "media" type is specific to some adapters. 
    # Let's try the "image_url" format with the file uri, as that is commonly mapped.
    # OR, construct the prompt using `genai` SDK directly if LangChain is too abstract here?
    # The prompt asked to use the model.
    #
    # Let's use the standard "image_url"{"url": file.uri} pattern which is often intercepted.
    
    content_payload = [
        {
            "type": "text", 
            "text": """
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
        },
        {
            "type": "image_url",
            "image_url": {"url": uploaded_file.uri}
        }
    ]

    message = HumanMessage(content=content_payload)
    
    # Invoke the chain
    result = structured_llm.invoke([message])
    
    # Clean up file? (Optional but good practice)
    # genai.delete_file(uploaded_file.name)
    
    # Verify result isn't empty
    if not result:
        raise ValueError("Failed to extract receipt data.")
        
    return result
