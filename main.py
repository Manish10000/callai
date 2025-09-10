import os
import json
import re
import gspread
import uvicorn
import google.generativeai as genai
from fastapi import FastAPI, Request
from fastapi.responses import Response
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from datetime import datetime

# Import modules
from functions import function_declarations
from sheets_handler import get_inventory, get_customer_by_phone, save_customer, save_cart, load_cart, delete_cart
from cart_manager import shopping_carts, customer_info, conversation_history, add_to_cart, get_cart_summary, place_order, add_to_conversation_history, get_conversation_context
from product_search import search_products, find_similar_products, find_complementary_products

# ---------------- Load environment variables ----------------
load_dotenv()

PORT = int(os.getenv("PORT", "8080"))
DOMAIN = os.getenv("NGROK_URL")
if not DOMAIN:
    raise ValueError("NGROK_URL environment variable not set.")

# ---------------- Google Sheets Setup ----------------
GOOGLE_SHEETS_CREDENTIALS = os.path.join(os.path.dirname(__file__), "service_account.json")
if not os.path.exists(GOOGLE_SHEETS_CREDENTIALS):
    raise ValueError("service_account.json file not found next to main.py")

# Parse the credentials JSON
with open(GOOGLE_SHEETS_CREDENTIALS, "r") as f:
    credentials_info = json.load(f)

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_info(credentials_info, scopes=scope)
client = gspread.authorize(creds)

# Open the Google Sheet
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
if not SPREADSHEET_ID:
    raise ValueError("SPREADSHEET_ID environment variable not set.")

# Initialize all worksheets
try:
    sheet = client.open_by_key(SPREADSHEET_ID)
    
    # Import the sheet variables from sheets_handler
    import sheets_handler
    
    # Get or create all required worksheets
    try:
        sheets_handler.inventory_sheet = sheet.worksheet("Inventory")
    except:
        sheets_handler.inventory_sheet = sheet.add_worksheet(title="Inventory", rows=100, cols=10)
        sheets_handler.inventory_sheet.append_row(["Item Name", "Category", "Quantity", "Price (USD)", "Description", "Tags"])
    
    try:
        sheets_handler.customers_sheet = sheet.worksheet("Customers")
    except:
        sheets_handler.customers_sheet = sheet.add_worksheet(title="Customers", rows=100, cols=10)
        sheets_handler.customers_sheet.append_row(["Phone Number", "Name", "Address", "City", "State", "Zip", "Last Order Date"])
    
    try:
        sheets_handler.orders_sheet = sheet.worksheet("Orders")
    except:
        sheets_handler.orders_sheet = sheet.add_worksheet(title="Orders", rows=100, cols=10)
        sheets_handler.orders_sheet.append_row(["Order ID", "Customer Phone", "Items JSON", "Total", "Status", "Date"])
    
    try:
        sheets_handler.carts_sheet = sheet.worksheet("Carts")
    except:
        sheets_handler.carts_sheet = sheet.add_worksheet(title="Carts", rows=100, cols=10)
        sheets_handler.carts_sheet.append_row(["Session ID", "Customer Phone", "Items JSON", "Last Updated"])
        
except Exception as e:
    print(f"Error accessing Google Sheets: {e}")
    # We'll use fallback data structures
    pass

# ---------------- Greeting ----------------
WELCOME_GREETING = "नमस्ते! Welcome to GroceryBabu! I'm your personal shopping assistant. You can ask me about products, add items to your cart, or place an order."

# ---------------- Gemini API ----------------
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set.")

genai.configure(api_key=GOOGLE_API_KEY)

# Store active chat sessions
sessions = {}

# Language mapping with appropriate voices
LANGUAGE_MAP = {
    "hi": {"code": "hi-IN", "voice": "Polly.Aditi"},
    "gu": {"code": "hi-IN", "voice": "Polly.Aditi"},
    "en": {"code": "en-IN", "voice": "Polly.Aditi"},
    "default": {"code": "en-IN", "voice": "Polly.Aditi"}
}

async def process_user_query(user_prompt, call_sid):
    """Process user query with function calling"""
    # Add to conversation history
    add_to_conversation_history(call_sid, "user", user_prompt)
    
    # Get conversation context
    context = get_conversation_context(call_sid)
    
    # Initialize the model with function declarations
    model = genai.GenerativeModel(
        model_name='gemini-2.0-flash-exp',
        tools=function_declarations
    )
    
    # Start a chat session if not exists
    if call_sid not in sessions:
        sessions[call_sid] = model.start_chat(history=[])
        
        # Try to load existing cart for this session
        existing_cart = load_cart(call_sid)
        if existing_cart:
            shopping_carts[call_sid] = {
                "items": existing_cart["Items"],
                "total": sum(item.get("subtotal", 0) for item in existing_cart["Items"]),
                "customer_phone": existing_cart["Customer Phone"]
            }
    
    # Prepare the prompt with context
    full_prompt = f"{context}\n\nUser: {user_prompt}"
    
    try:
        # Send the message to Gemini
        response = sessions[call_sid].send_message(full_prompt)
        
        # Check if the response contains a function call
        if response.candidates and response.candidates[0].content.parts[0].function_call:
            function_call = response.candidates[0].content.parts[0].function_call
            function_name = function_call.name
            args = dict(function_call.args)  # Convert protobuf to dict
            
            print(f"DEBUG: Function call detected: {function_name} with args: {args}")
            
            # Execute the appropriate function
            if function_name == "search_products":
                query = args.get("query", "")
                category = args.get("category", None)
                results = search_products(query, category)
                
                print(f"DEBUG: Search query: '{query}', found {len(results)} results")
                
                if results:
                    if len(results) > 5:
                        response_text = f"I found {len(results)} products. Here are some popular ones: "
                        for item in results[:5]:  # Show top 5 results
                            response_text += f"{item['Item Name']} (${item['Price (USD)']}, {item['Quantity']} available), "
                    else:
                        response_text = f"I found these products: "
                        for item in results[:3]:  # Show top 3 results
                            response_text += f"{item['Item Name']} (${item['Price (USD)']}, {item['Quantity']} available), "
                    
                    # Suggest similar products if few results
                    if len(results) < 3:
                        similar = find_similar_products(query)
                        if similar:
                            response_text += "You might also like: "
                            for item in similar[:2]:
                                response_text += f"{item['Item Name']}, "
                    
                    response_text += "Would you like to add any of these to your cart?"
                else:
                    # Try to find similar products using vector search
                    similar = find_similar_products(query)
                    if similar:
                        response_text = f"I couldn't find exact matches for '{query}', but you might like: "
                        for item in similar[:3]:
                            response_text += f"{item['Item Name']} (${item['Price (USD)']}), "
                        response_text += "Would you like to add any of these to your cart?"
                    else:
                        response_text = f"I couldn't find any products matching '{query}'. Could you please try a different name?"
            
            elif function_name == "add_to_cart":
                product_name = args.get("product_name", "")
                quantity = args.get("quantity", 1)
                
                # Get customer phone if available
                customer_phone = None
                if call_sid in customer_info and "phone" in customer_info[call_sid]:
                    customer_phone = customer_info[call_sid]["phone"]
                elif call_sid in shopping_carts and "customer_phone" in shopping_carts[call_sid]:
                    customer_phone = shopping_carts[call_sid]["customer_phone"]
                
                success, response_text = add_to_cart(call_sid, product_name, quantity, customer_phone)
                
                # Suggest complementary products
                if success:
                    complementary = find_complementary_products(product_name)
                    if complementary:
                        response_text += " You might also need: "
                        for item in complementary:
                            response_text += f"{item['Item Name']}, "
                        response_text += "Would you like to add any of these too?"
            
            elif function_name == "get_cart_summary":
                response_text = get_cart_summary(call_sid)
            
            elif function_name == "place_order":
                if call_sid in shopping_carts and shopping_carts[call_sid]["items"]:
                    # Extract address components from the full address
                    address_parts = args.get("customer_address", "").split(',')
                    customer_data = {
                        "name": args.get("customer_name", ""),
                        "phone": args.get("customer_phone", ""),
                        "address": address_parts[0].strip() if len(address_parts) > 0 else "",
                        "city": address_parts[1].strip() if len(address_parts) > 1 else "",
                        "state": address_parts[2].strip() if len(address_parts) > 2 else "",
                        "zip": address_parts[3].strip() if len(address_parts) > 3 else ""
                    }
                    
                    success, response_text = place_order(call_sid, customer_data)
                else:
                    response_text = "Your cart is empty. Please add some items before placing an order."
            
            else:
                response_text = "I'm not sure how to handle that request. Could you please rephrase?"
        
        else:
            # No function call, use the text response directly
            response_text = response.text
        
        # Add to conversation history
        add_to_conversation_history(call_sid, "assistant", response_text)
        
        # Default to English for now since function calling doesn't provide language info
        return "en", response_text
    
    except Exception as e:
        print(f"Error processing query with Gemini: {e}")
        response_text = "I'm sorry, I didn't understand that. Could you please repeat?"
        add_to_conversation_history(call_sid, "assistant", response_text)
        return "en", response_text

# ---------------- FastAPI app ----------------
app = FastAPI()

@app.post("/twiml")
async def twiml_endpoint():
    """Return TwiML for Twilio"""
    xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" language="en-IN" action="https://{DOMAIN}/handle-speech" speechTimeout="auto" enhanced="true">
        <Say voice="Polly.Aditi">{WELCOME_GREETING}</Say>
    </Gather>
    <Say voice="Polly.Aditi">I didn't hear anything. Please call back again.</Say>
</Response>"""
    
    return Response(content=xml_response, media_type="text/xml")

@app.post("/handle-speech")
async def handle_speech(request: Request):
    """Handle speech input from Twilio's Gather"""
    form_data = await request.form()
    speech_result = form_data.get("SpeechResult", "")
    call_sid = form_data.get("CallSid", "")
    
    print(f"Received speech from {call_sid}: {speech_result}")
    
    # Process the user query
    detected_language, response_text = await process_user_query(speech_result, call_sid)
    
    # Map to Twilio language code and voice
    language_info = LANGUAGE_MAP.get(detected_language, LANGUAGE_MAP["default"])
    detected_language_code = language_info["code"]
    voice = language_info["voice"]
    
    print(f"Detected language: {detected_language} -> Twilio: {detected_language_code}, Voice: {voice}")
    print(f"Response: {response_text}")
    
    # Check if this is a goodbye message to end the call
    if any(word in response_text.lower() for word in ["goodbye", "thank you", "end call", "have a great day"]):
        xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{voice}">{response_text}</Say>
    <Hangup/>
</Response>"""
    else:
        # Return TwiML with dynamic language switching
        xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{voice}">{response_text}</Say>
    <Gather input="speech" language="{detected_language_code}" action="https://{DOMAIN}/handle-speech" speechTimeout="auto" enhanced="true">
        <Say voice="{voice}">Please continue, I'm listening.</Say>
    </Gather>
    <Say voice="{voice}">I didn't hear anything. Please call back if you need assistance.</Say>
    <Hangup/>
</Response>"""
    
    print(f"Using language: {detected_language_code} with voice: {voice} for call {call_sid}")
    
    return Response(content=xml_response, media_type="text/xml")

@app.get("/")
async def root():
    return {"message": "GroceryBabu Voice Assistant API"}

if __name__ == "__main__":
    print(f"Starting server on port {PORT}")
    print("Available endpoints:")
    print(f"  - Main endpoint: {DOMAIN}/twiml")
    print(f"  - Speech handler: {DOMAIN}/handle-speech")
    print("GroceryBabu assistant is ready with function calling!")
    
    # Test inventory reading
    print("Testing inventory access...")
    inventory = get_inventory()
    print(f"Found {len(inventory)} items in inventory")
    
    uvicorn.run(app, host="0.0.0.0", port=PORT)