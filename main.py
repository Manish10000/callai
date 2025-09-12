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
import time
import random

# Import modules
from functions import function_declarations
from sheets_handler import get_inventory, get_customer_by_phone, save_customer, save_cart, load_cart, delete_cart
from cart_manager import shopping_carts, customer_info, conversation_history, add_to_cart, get_cart_summary, place_order, add_to_conversation_history, get_conversation_context, remove_from_cart
from product_search import search_products, find_similar_products, find_complementary_products, get_categories_summary

# Import filler sentences
from filler_sentences import PROCESSING_PHRASES, COMPLETION_PHRASES

# Import language translations
from language import LANG

# ---------------- Load environment variables ----------------
load_dotenv()

PORT = int(os.getenv("PORT", "8080"))
DOMAIN = os.getenv("NGROK_URL")
if not DOMAIN:
    raise ValueError("NGROK_URL environment variable not set.")

# ---------------- Google Sheets Setup ----------------
print("DEBUG: Setting up Google Sheets connection...")

GOOGLE_SHEETS_CREDENTIALS = os.path.join(os.path.dirname(__file__), "service_account.json")
print(f"DEBUG: Looking for credentials at: {GOOGLE_SHEETS_CREDENTIALS}")

if not os.path.exists(GOOGLE_SHEETS_CREDENTIALS):
    print("ERROR: service_account.json file not found next to main.py")
    print("DEBUG: Please ensure you have the service_account.json file in the same directory as main.py")
    raise ValueError("service_account.json file not found next to main.py")

# Parse the credentials JSON
try:
    with open(GOOGLE_SHEETS_CREDENTIALS, "r") as f:
        credentials_info = json.load(f)
    print("DEBUG: Successfully loaded credentials JSON")
except Exception as e:
    print(f"ERROR: Failed to parse credentials JSON: {e}")
    raise

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_info(credentials_info, scopes=scope)
client = gspread.authorize(creds)
print("DEBUG: Successfully authorized gspread client")

# Open the Google Sheet
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
print(f"DEBUG: SPREADSHEET_ID from environment: {SPREADSHEET_ID}")

if not SPREADSHEET_ID:
    print("ERROR: SPREADSHEET_ID environment variable not set")
    print("DEBUG: Please set SPREADSHEET_ID in your .env file")
    raise ValueError("SPREADSHEET_ID environment variable not set.")

# Initialize all worksheets
try:
    print("DEBUG: Attempting to connect to Google Sheets...")
    sheet = client.open_by_key(SPREADSHEET_ID)
    print(f"DEBUG: Successfully opened spreadsheet: {sheet.title}")
    
    # Import the sheet variables from sheets_handler
    import sheets_handler
    
    # Get or create all required worksheets
    try:
        sheets_handler.inventory_sheet = sheet.worksheet("Inventory")
        print("DEBUG: Found existing Inventory worksheet")
    except Exception as e:
        print(f"DEBUG: Creating new Inventory worksheet: {e}")
        sheets_handler.inventory_sheet = sheet.add_worksheet(title="Inventory", rows=100, cols=10)
        sheets_handler.inventory_sheet.append_row(["Item Name", "Category", "Quantity", "Price (USD)", "Description", "Tags"])
    
    try:
        sheets_handler.customers_sheet = sheet.worksheet("Customers")
        print("DEBUG: Found existing Customers worksheet")
    except Exception as e:
        print(f"DEBUG: Creating new Customers worksheet: {e}")
        sheets_handler.customers_sheet = sheet.add_worksheet(title="Customers", rows=100, cols=10)
        sheets_handler.customers_sheet.append_row(["Phone Number", "Name", "Address", "City", "State", "Zip", "Last Order Date"])
    
    try:
        sheets_handler.orders_sheet = sheet.worksheet("Orders")
        print("DEBUG: Found existing Orders worksheet")
    except Exception as e:
        print(f"DEBUG: Creating new Orders worksheet: {e}")
        sheets_handler.orders_sheet = sheet.add_worksheet(title="Orders", rows=100, cols=10)
        sheets_handler.orders_sheet.append_row(["Order ID", "Customer Phone", "Items JSON", "Total", "Status", "Date"])
    
    try:
        sheets_handler.carts_sheet = sheet.worksheet("Carts")
        print("DEBUG: Found existing Carts worksheet")
    except Exception as e:
        print(f"DEBUG: Creating new Carts worksheet: {e}")
        sheets_handler.carts_sheet = sheet.add_worksheet(title="Carts", rows=100, cols=10)
        sheets_handler.carts_sheet.append_row(["Session ID", "Customer Phone", "Items JSON", "Last Updated"])
    
    print("DEBUG: All worksheets initialized successfully")
        
except Exception as e:
    print(f"ERROR: Failed to access Google Sheets: {e}")
    print("DEBUG: This could be due to:")
    print("  1. Missing or invalid service_account.json file")
    print("  2. Wrong SPREADSHEET_ID in environment variables")
    print("  3. Insufficient permissions for the service account")
    print("  4. Network connectivity issues")
    
    # Initialize sheets_handler with None values to prevent errors
    import sheets_handler
    sheets_handler.inventory_sheet = None
    sheets_handler.customers_sheet = None
    sheets_handler.orders_sheet = None
    sheets_handler.carts_sheet = None
    
    print("DEBUG: Will use fallback data only")

# ---------------- Greeting ----------------
# Welcome greeting will be dynamically generated based on detected language

# Language mapping with appropriate voices
LANGUAGE_MAP = {
    "hi": {"code": "hi-IN", "voice": "Polly.Aditi"},
    "gu": {"code": "hi-IN", "voice": "Polly.Aditi"},
    "en": {"code": "en-IN", "voice": "Polly.Aditi"},
    "default": {"code": "en-IN", "voice": "Polly.Aditi"}
}

# Store active chat sessions and context
sessions = {}
conversation_context = {}
call_retry_counts = {}

# Enhanced system prompt with multilingual support
SYSTEM_PROMPT = """You are Aditi, a multilingual grocery assistant at GroceryBabu.

LANGUAGE DETECTION RULES:
1. Detect user's language from input patterns:
   - English words/phrases → respond in English (en)
   - Hindi words (मुझे, चाहिए, खरीदना, है, हूं, etc.) → respond in Hindi (hi)
   - Gujarati words written in Hindi script (छे, छूं, तमे, तमारु, etc.) → respond in Gujarati (gu)
   
2. CRITICAL: ALL function calls MUST include the language parameter matching detected language.

3. Response format: <language>[code]</language><response>[message]</response>

4. Language consistency rules:
   - If input is English → ALL outputs (AI + functions) must be English
   - If input is Hindi → ALL outputs must be Hindi
   - If input is Gujarati → ALL outputs in Hindi letters but Gujarati words

5. Examples:
   User: "I want milk" → <language>en</language><response>What type of milk would you like?</response>
   User: "मुझे दूध चाहिए" → <language>hi</language><response>आपको किस प्रकार का दूध चाहिए?</response>
   User: "मने दूध जोइए छे" → <language>gu</language><response>तमने केवु दूध जोइए छे?</response>

FUNCTION CALLING REQUIREMENTS:
- ALWAYS pass detected language to every function call
- Functions will return responses in the specified language
- Never mix languages in a single conversation turn
- Maintain language consistency throughout entire conversation

SPEECH RECOGNITION HANDLING:
- Handle common misrecognitions gracefully
- Maintain language context even with recognition errors
- Use context clues to determine intent when speech is unclear"""

def parse_language_response(response_text):
    """Parse language-tagged response format"""
    import re
    
    language_match = re.search(r'<language>(\w+)</language>', response_text)
    response_match = re.search(r'<response>(.*?)</response>', response_text, re.DOTALL)
    
    if language_match and response_match:
        detected_language = language_match.group(1)
        clean_response = response_match.group(1).strip()
        return detected_language, clean_response
    
    return "en", response_text

def with_processing_feedback(func):
    """
    Decorator to add processing feedback for functions that might take time
    """
    def wrapper(*args, **kwargs):
        # Extract call_sid from args or kwargs
        call_sid = None
        if args and len(args) > 0:
            call_sid = args[0]
        elif 'call_sid' in kwargs:
            call_sid = kwargs['call_sid']
        
        # Start timer
        start_time = time.time()
        
        # Execute the function
        result = func(*args, **kwargs)
        
        # Check if processing took more than 1 second
        processing_time = time.time() - start_time
        if processing_time > 1 and call_sid:
            # Select a random processing phrase
            processing_phrase = random.choice(PROCESSING_PHRASES)
            completion_phrase = random.choice(COMPLETION_PHRASES)
            
            # Add to conversation history
            add_to_conversation_history(call_sid, "assistant", processing_phrase)
            
            # For a real implementation, you would send this to the user
            # For now, we'll just print it
            print(f"PROCESSING FEEDBACK: {processing_phrase}")
            
            # Wait a moment to simulate the assistant "processing"
            time.sleep(0.5)
            
            # Modify the return message to include the completion phrase
            if isinstance(result, tuple) and len(result) == 2:
                success, message = result
                new_message = f"{completion_phrase} {message.lower()}"
                return success, new_message
            elif isinstance(result, str):
                return f"{completion_phrase} {result.lower()}"
        
        return result
    
    return wrapper

# Apply the decorator to functions that might have processing delays
@with_processing_feedback
def add_to_cart_wrapper(call_sid, product_name, quantity, customer_phone=None, language="en"):
    """Wrapper for add_to_cart with processing feedback"""
    return add_to_cart(call_sid, product_name, quantity, customer_phone, language)

@with_processing_feedback
def remove_from_cart_wrapper(call_sid, product_name, quantity=None, language="en"):
    """Wrapper for remove_from_cart with processing feedback"""
    return remove_from_cart(call_sid, product_name, quantity, language)

@with_processing_feedback
def get_cart_summary_wrapper(call_sid, language="en"):
    """Wrapper for get_cart_summary with processing feedback"""
    return get_cart_summary(call_sid, language)

@with_processing_feedback
def place_order_wrapper(call_sid, customer_data, language="en"):
    """Wrapper for place_order with processing feedback"""
    return place_order(call_sid, customer_data, language)

def initialize_session(call_sid):
    """Initialize a new chat session with the system prompt"""
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        tools=function_declarations
    )
    
    sessions[call_sid] = model.start_chat(history=[])
    
    # Send system prompt as the first message
    sessions[call_sid].send_message(SYSTEM_PROMPT)
    
    # Load existing cart if available
    existing_cart = load_cart(call_sid)
    if existing_cart:
        shopping_carts[call_sid] = {
            "items": existing_cart["Items"],
            "total": sum(item.get("subtotal", 0) for item in existing_cart["Items"]),
            "customer_phone": existing_cart["Customer Phone"]
        }

async def process_user_query(user_prompt, call_sid):
    """Process user query with function calling"""
    add_to_conversation_history(call_sid, "user", user_prompt)
    context = get_conversation_context(call_sid)
    
    # Initialize session if it doesn't exist
    if call_sid not in sessions:
        initialize_session(call_sid)
    
    # Enhanced context with speech recognition error handling
    enhanced_context = f"""CONVERSATION HISTORY:
{context}

SPEECH RECOGNITION CONTEXT:
User might say things that get misrecognized:
- "Play Store app" usually means "place order" or "products"
- "card" usually means "cart"
- Numbers might be misheard: "tour" → "two", "wife" → "five"
- Names might be misheard but accept them as-is for demo

CURRENT USER INPUT: "{user_prompt}"

Interpret the user's intent considering possible speech recognition errors."""

    try:
        print(f"DEBUG: Sending to Gemini: {user_prompt}")
        response = sessions[call_sid].send_message(enhanced_context)
        
        has_function_call = False
        function_call = None
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    has_function_call = True
                    function_call = part.function_call
                    break
        
        if has_function_call:
            function_name = function_call.name
            args = dict(function_call.args)
            
            print(f"DEBUG: Function call: {function_name} with args: {args}")
            
            if function_name == "search_products":
                query = args.get("query", "")
                language = args.get("language", "en")
                results = search_products(query)
                
                if isinstance(results, dict):
                    if not results:
                        response_text = LANG["no_products"][language].format(query=query)
                    else:
                        items_list = ", ".join([f"{cat} ({len(items)} items)" for cat, items in list(results.items())[:3]])
                        response_text = LANG["product_found"][language].format(count=len(results), items=items_list)
                
                elif isinstance(results, list):
                    if results:
                        if len(results) == 1:
                            item = results[0]
                            response_text = LANG["ask_quantity"][language].format(item=item['Item Name'])
                        else:
                            items_list = ", ".join([f"{item['Item Name']} (${item['Price (USD)']})" for item in results[:3]])
                            response_text = LANG["product_found"][language].format(count=len(results), items=items_list)
                    else:
                        similar = find_similar_products(query)
                        if similar:
                            items_list = ", ".join([f"{item['Item Name']} (${item['Price (USD)']})" for item in similar[:2]])
                            response_text = LANG["product_found"][language].format(count=len(similar), items=items_list)
                        else:
                            response_text = LANG["no_products"][language].format(query=query)
            
            elif function_name == "add_to_cart":
                product_name = args.get("product_name", "")
                quantity = args.get("quantity", 1)
                language = args.get("language", "en")
                
                customer_phone = None
                if call_sid in customer_info and "phone" in customer_info[call_sid]:
                    customer_phone = customer_info[call_sid]["phone"]
                elif call_sid in shopping_carts and "customer_phone" in shopping_carts[call_sid]:
                    customer_phone = shopping_carts[call_sid]["customer_phone"]
                
                success, message = add_to_cart_wrapper(call_sid, product_name, quantity, customer_phone, language)
                
                if success:
                    response_text = LANG["item_added"][language].format(qty=quantity, item=product_name)
                    
                    if call_sid in shopping_carts and len(shopping_carts[call_sid]["items"]) <= 2:
                        complementary = find_complementary_products(product_name, max_results=3)
                        cart_items = [item["name"] for item in shopping_carts[call_sid]["items"]]
                        available_suggestions = [item for item in complementary if item['Item Name'] not in cart_items]
                        
                        if available_suggestions:
                            item = available_suggestions[0]
                            response_text += f" {LANG['ask_quantity'][language].format(item=item['Item Name'])}"
                else:
                    response_text = message
            
            elif function_name == "remove_from_cart":
                product_name = args.get("product_name", "")
                quantity = args.get("quantity", 1)
                language = args.get("language", "en")
                
                success, message = remove_from_cart_wrapper(call_sid, product_name, quantity, language)
                
                if success:
                    response_text = LANG["item_removed"][language].format(qty=quantity, item=product_name)
                else:
                    response_text = message
            
            elif function_name == "get_cart_summary":
                language = args.get("language", "en")
                
                if call_sid in shopping_carts and shopping_carts[call_sid]["items"]:
                    cart = shopping_carts[call_sid]
                    item_count = len(cart["items"])
                    total = cart["total"]
                    response_text = LANG["cart_summary"][language].format(count=item_count, total=total)
                else:
                    response_text = LANG["cart_empty"][language]
            
            elif function_name == "place_order":
                # Extract customer info from args or conversation context
                name = args.get("customer_name", "")
                phone = args.get("customer_phone", "")
                address = args.get("customer_address", "")
                language = args.get("language", "en")
                
                # If info is missing from function call, check conversation context
                if (not name or name.lower() == "unknown") and call_sid in customer_info and "name" in customer_info[call_sid]:
                    name = customer_info[call_sid]["name"]
                
                if (not phone or phone.lower() == "unknown") and call_sid in customer_info and "phone" in customer_info[call_sid]:
                    phone = customer_info[call_sid]["phone"]
                
                if (not address or address.lower() == "unknown") and call_sid in customer_info and "address" in customer_info[call_sid]:
                    address = customer_info[call_sid]["address"]
                
                # For demo purposes, use placeholder if still missing
                if not name or name.lower() == "unknown":
                    name = "Customer"  # Simple placeholder
                
                if not phone or phone.lower() == "unknown":
                    phone = "0000000000"  # Placeholder phone
                
                if not address or address.lower() == "unknown":
                    address = "Default Address"  # Placeholder address
                
                # Place the order
                if call_sid in shopping_carts and shopping_carts[call_sid]["items"]:
                    address_parts = address.split(',')
                    customer_data = {
                        "name": name,
                        "phone": phone,
                        "address": address_parts[0].strip() if len(address_parts) > 0 else address,
                        "city": address_parts[1].strip() if len(address_parts) > 1 else "",
                        "state": address_parts[2].strip() if len(address_parts) > 2 else "",
                        "zip": address_parts[3].strip() if len(address_parts) > 3 else ""
                    }
                    
                    success, order_result = place_order_wrapper(call_sid, customer_data, language)
                    
                    if success:
                        # Extract order ID from result if available
                        order_id = "12345"  # Placeholder
                        response_text = LANG["order_placed"][language].format(order_id=order_id)
                    else:
                        response_text = order_result
                else:
                    response_text = LANG["cart_empty"][language]
            
            else:
                response_text = "I'm not sure how to handle that request."
        
        else:
            response_text = response.text
            print(f"DEBUG: Text response: {response_text}")
        
        detected_lang, clean_response = parse_language_response(response_text)
        add_to_conversation_history(call_sid, "assistant", clean_response)
        return detected_lang, clean_response
    
    except Exception as e:
        print(f"Error processing query: {e}")
        
        # Enhanced error handling for speech recognition issues
        user_input_lower = user_prompt.lower()
        
        # Handle common speech recognition errors with multilingual support
        # Default to English for error handling, but could be enhanced with language detection
        language = "en"
        
        if "play store" in user_input_lower or "playstore" in user_input_lower:
            # This usually means "place order" or "products"
            if "app" in user_input_lower or "application" in user_input_lower:
                if call_sid in shopping_carts and shopping_carts[call_sid]["items"]:
                    cart = shopping_carts[call_sid]
                    item_count = len(cart["items"])
                    total = cart["total"]
                    cart_summary = LANG["cart_summary"][language].format(count=item_count, total=total)
                    response_text = f"I understand you want to place an order. {cart_summary} Would you like to proceed?"
                else:
                    response_text = LANG["cart_empty"][language]
            else:
                response_text = "I found these products for you. What would you like to add to your cart?"
        
        elif "card" in user_input_lower and "check" in user_input_lower:
            # "check my card" → "check my cart"
            if call_sid in shopping_carts and shopping_carts[call_sid]["items"]:
                cart = shopping_carts[call_sid]
                item_count = len(cart["items"])
                total = cart["total"]
                response_text = LANG["cart_summary"][language].format(count=item_count, total=total)
            else:
                response_text = LANG["cart_empty"][language]
        
        elif any(word in user_input_lower for word in ["order", "place order", "checkout"]):
            # Order placement with error recovery
            if call_sid in shopping_carts and shopping_carts[call_sid]["items"]:
                # Use placeholder info for demo if missing
                if call_sid not in customer_info:
                    customer_info[call_sid] = {}
                
                if "name" not in customer_info[call_sid]:
                    # Extract name from input if possible, otherwise use placeholder
                    name_match = re.search(r'([A-Za-z]+(?:\s+[A-Za-z]+)+)', user_prompt)
                    if name_match:
                        customer_info[call_sid]["name"] = name_match.group(1)
                    else:
                        customer_info[call_sid]["name"] = "Customer"
                
                if "phone" not in customer_info[call_sid]:
                    customer_info[call_sid]["phone"] = "0000000000"
                
                if "address" not in customer_info[call_sid]:
                    customer_info[call_sid]["address"] = "Default Address"
                
                # Place the order
                success, order_result = place_order_wrapper(call_sid, customer_info[call_sid], language)
                if success:
                    order_id = "12345"  # Placeholder
                    response_text = LANG["order_placed"][language].format(order_id=order_id)
                else:
                    response_text = order_result
            else:
                response_text = LANG["cart_empty"][language]
        
        else:
            # Generic error response
            response_text = "I didn't understand that clearly. Could you please repeat?"
        
        response_text = f"<language>en</language><response>{response_text}</response>"
        detected_lang, clean_response = parse_language_response(response_text)
        add_to_conversation_history(call_sid, "assistant", clean_response)
        return detected_lang, clean_response

# ---------------- FastAPI app ----------------
app = FastAPI()
call_retry_counts = {}

@app.post("/twiml")
async def twiml_endpoint():
    # Use English welcome message as default for initial greeting
    safe_greeting = LANG["welcome"]["en"]
    
    xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" language="en-IN" action="https://{DOMAIN}/handle-speech" speechTimeout="auto" enhanced="true">
        <Say voice="Polly.Aditi">{safe_greeting}</Say>
    </Gather>
    <Say voice="Polly.Aditi">I did not hear anything. Let me try again.</Say>
    <Gather input="speech" language="en-IN" action="https://{DOMAIN}/handle-speech" speechTimeout="auto" enhanced="true">
        <Say voice="Polly.Aditi">Please tell me how I can help you.</Say>
    </Gather>
    <Say voice="Polly.Aditi">I am sorry, I am having trouble hearing you. Please try calling again later.</Say>
    <Hangup/>
</Response>"""
    
    return Response(content=xml_response, media_type="text/xml")

@app.post("/handle-speech")
async def handle_speech(request: Request):
    form_data = await request.form()
    speech_result = form_data.get("SpeechResult", "")
    call_sid = form_data.get("CallSid", "")
    
    print(f"Received speech from {call_sid}: {speech_result}")
    
    unclear_speech_indicators = ["", "um", "uh", "hmm"]
    is_unclear = (not speech_result or 
                  speech_result.strip() == "" or 
                  (speech_result.strip().lower() in unclear_speech_indicators and len(speech_result.strip()) <= 3))
    
    if is_unclear:
        if call_sid not in call_retry_counts:
            call_retry_counts[call_sid] = 0
        
        call_retry_counts[call_sid] += 1
        
        if call_retry_counts[call_sid] <= 3:
            retry_messages = {
                1: "I did not hear you clearly. Please speak again.",
                2: "I am still having trouble hearing you. Please try once more.",
                3: "Let me try one more time. Please speak clearly."
            }
            
            retry_message = retry_messages[call_retry_counts[call_sid]]
            
            xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi">{retry_message}</Say>
    <Gather input="speech" language="en-IN" action="https://{DOMAIN}/handle-speech" speechTimeout="auto" enhanced="true">
        <Say voice="Polly.Aditi">Please tell me how I can help you.</Say>
    </Gather>
    <Say voice="Polly.Aditi">I still cannot hear you clearly.</Say>
    <Gather input="speech" language="en-IN" action="https://{DOMAIN}/handle-speech" speechTimeout="auto" enhanced="true">
        <Say voice="Polly.Aditi">Please speak clearly.</Say>
    </Gather>
    <Say voice="Polly.Aditi">I am sorry, I am having trouble hearing you. Please try calling again later.</Say>
    <Hangup/>
</Response>"""
            return Response(content=xml_response, media_type="text/xml")
        else:
            xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi">I am sorry, I am having trouble hearing you. Please try calling again later.</Say>
    <Hangup/>
</Response>"""
            if call_sid in call_retry_counts:
                del call_retry_counts[call_sid]
            return Response(content=xml_response, media_type="text/xml")
    
    if call_sid in call_retry_counts:
        del call_retry_counts[call_sid]
    
    detected_language, clean_response = await process_user_query(speech_result, call_sid)
    
    language_info = LANGUAGE_MAP.get(detected_language, LANGUAGE_MAP["default"])
    detected_language_code = language_info["code"]
    voice = language_info["voice"]
    
    print(f"Language: {detected_language} -> {detected_language_code}, Voice: {voice}")
    
    if any(word in clean_response.lower() for word in ["goodbye", "thank you", "end call", "have a great day"]):
        xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{voice}">{clean_response}</Say>
    <Hangup/>
</Response>"""
        if call_sid in call_retry_counts:
            del call_retry_counts[call_sid]
        if call_sid in conversation_context:
            del conversation_context[call_sid]
    else:
        simple_prompts = {
            "hi": "मैं सुन रहा हूँ।",
            "gu": "हुं सांभळूं छूं।",
            "en": "I am listening."
        }
        continue_prompt = simple_prompts.get(detected_language, "")
        
        xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{voice}">{clean_response}</Say>
    <Gather input="speech" language="{detected_language_code}" action="https://{DOMAIN}/handle-speech" speechTimeout="auto" enhanced="true">
    </Gather>
    <Say voice="{voice}">I did not hear you.</Say>
    <Gather input="speech" language="{detected_language_code}" action="https://{DOMAIN}/handle-speech" speechTimeout="auto" enhanced="true">
        <Say voice="{voice}">Please tell me what you need.</Say>
    </Gather>
    <Say voice="{voice}">I am having trouble hearing you. Please try calling again later.</Say>
    <Hangup/>
</Response>"""
    
    return Response(content=xml_response, media_type="text/xml")

@app.get("/")
async def root():
    return {"message": "GroceryBabu Voice Assistant API - Aditi is ready to help!"}

if __name__ == "__main__":
    print(f"Starting server on port {PORT}")
    print(f"Main endpoint: {DOMAIN}/twiml")
    print(f"Speech handler: {DOMAIN}/handle-speech")
    print("GroceryBabu assistant Aditi is ready with optimized prompts!")
    
    inventory = get_inventory()
    print(f"Found {len(inventory)} items in inventory")
    
    from intelligent_search import search_engine
    search_engine.refresh_inventory()
    print("Search engine refreshed")
    
    uvicorn.run(app, host="0.0.0.0", port=PORT)