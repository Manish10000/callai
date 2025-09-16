import os
import json
import re
import gspread
import uvicorn
import google.generativeai as genai
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import Response
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import random
import threading
import queue
import asyncio
from typing import Dict

# Import modules
from functions import function_declarations
from sheets_handler import get_inventory, get_customer_by_phone, save_customer, save_cart, load_cart, delete_cart
from cart_manager import shopping_carts, customer_info, conversation_history, add_to_cart, get_cart_summary, place_order, add_to_conversation_history, get_conversation_context, remove_from_cart
from product_search import search_products, find_similar_products, find_complementary_products, get_categories_summary

# Import filler sentences and language utilities
from filler_sentences import get_processing_phrase, get_completion_phrase
from language import LANG

# ---------------- Load environment variables ----------------
load_dotenv()

PORT = int(os.getenv("PORT", "8080"))
DOMAIN = os.getenv("NGROK_URL")
if not DOMAIN:
    raise ValueError("NGROK_URL environment variable not set.")

# ---------------- Processing Feedback System ----------------
# Thread-safe queues for processing feedback
processing_queues: Dict[str, queue.Queue] = {}
processing_threads: Dict[str, threading.Thread] = {}
processing_results: Dict[str, Dict] = {}

def processing_worker(call_sid: str, user_input: str):
    """Background worker to process user request and provide feedback"""
    try:
        # Get the queue for this call
        if call_sid not in processing_queues:
            processing_queues[call_sid] = queue.Queue()
        
        q = processing_queues[call_sid]
        
        # Use session language from previous interactions, fallback to global language
        session_lang = get_session_language(call_sid) if call_sid in session_languages else current_language
        
        # Send processing message in appropriate language
        processing_phrase = get_processing_phrase(session_lang)
        q.put({"type": "processing", "message": processing_phrase})
        
        # Simulate processing time (or use actual processing time)
        time.sleep(0.5)
        
        # Process the actual request
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            detected_language, clean_response = loop.run_until_complete(
                process_user_query(user_input, call_sid)
            )
            
            # Send completion message in detected language
            completion_phrase = get_completion_phrase(detected_language)
            q.put({"type": "completion", "message": f"{completion_phrase} {clean_response}"})
            
            # Store the final result
            processing_results[call_sid] = {
                "language": detected_language,
                "response": clean_response,
                "ready": True
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        print(f"Error in processing worker for {call_sid}: {e}")
        if call_sid in processing_queues:
            error_msg = get_localized_text("processing_error", current_language) or "Sorry, I encountered an error processing your request."
            processing_queues[call_sid].put({"type": "error", "message": error_msg})

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
WELCOME_GREETING = "नमस्ते! Welcome to GroceryBabu! I'm Aditi, your personal shopping assistant. You can ask me about products, add items to your cart, or place an order."

# Language mapping with appropriate voices
LANGUAGE_MAP = {
    "hi": {"code": "hi-IN", "voice": "Polly.Aditi"},
    "gu": {"code": "hi-IN", "voice": "Polly.Aditi"},
    "en": {"code": "en-IN", "voice": "Polly.Aditi"},
    "default": {"code": "en-IN", "voice": "Polly.Aditi"}
}

# ---------------- Gemini API ----------------
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set.")

genai.configure(api_key=GOOGLE_API_KEY)

# Store active chat sessions and context
sessions = {}
conversation_context = {}
call_retry_counts = {}

# Global language management
current_language = "en"  # Default language
session_languages = {}  # Track language per session

# Warm-up session for faster first requests
warmup_session = None

def initialize_warmup_session():
    """Initialize a warm-up Gemini session to reduce first request latency"""
    global warmup_session
    try:
        print("DEBUG: Initializing Gemini warm-up session...")
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            tools=function_declarations
        )
        
        warmup_session = model.start_chat(history=[])
        
        # Send system prompt to warm up the session
        warmup_session.send_message(SYSTEM_PROMPT)
        
        # Send a simple test message to fully initialize
        test_response = warmup_session.send_message("Hello, test message for initialization")
        
        print("DEBUG: Gemini warm-up session initialized successfully")
        return True
        
    except Exception as e:
        print(f"DEBUG: Warm-up session initialization failed: {e}")
        warmup_session = None
        return False

def set_global_language(lang_code):
    """Set global language with fallback to English"""
    global current_language
    print("DEBUG: Setting global language to", lang_code)
    if lang_code in ["en", "hi", "gu"]:
        current_language = lang_code
    else:
        current_language = "en"
    return current_language

def get_session_language(call_sid):
    """Get language for specific session with fallback"""
    print("DEBUG: Getting session language for", call_sid)
    print("DEBUG: Session languages:", session_languages)
    return session_languages.get(call_sid, current_language)

def set_session_language(call_sid, lang_code):
    """Set language for specific session"""
    print("DEBUG: Setting session language for", call_sid, "to", lang_code)
    if lang_code in ["en", "hi", "gu"]:
        print("DEBUG: Setting session language to", lang_code)
        session_languages[call_sid] = lang_code
    else:
        print("DEBUG: Setting session language to default", current_language)
        session_languages[call_sid] = current_language
    return session_languages[call_sid]

def get_localized_text(key, lang_code=None, **kwargs):
    """Get localized text with fallback to English"""
    if lang_code is None:
        lang_code = current_language
    
    if key in LANG and lang_code in LANG[key]:
        text = LANG[key][lang_code]
    elif key in LANG and "en" in LANG[key]:
        text = LANG[key]["en"]
    else:
        return f"Missing translation for {key}"
    
    # Format with provided kwargs
    try:
        return text.format(**kwargs)
    except KeyError:
        return text

# Enhanced system prompt with better speech recognition error handling
SYSTEM_PROMPT = """You are Aditi, a helpful grocery assistant at GroceryBabu.

LANGUAGE: Detect user's language from input and respond in same language using format:
<language>[hi/gu/en]</language><response>[response]</response>

SPEECH RECOGNITION ERROR HANDLING:
- "Play Store app" → "place order" or "products"
- "card" → "cart", "check my card" → "check my cart"
- "milk vicks/wicks" → "milk bikis", "type of them" → "two of them"
- "wife of the" → "five of them", "tour of" → "two of"
- "auto" → "two", "offline" → "all fine"
- "mrutyunjay" → "Mrutyunjay" (name), "Patra" → "Patra" (surname)
- "place order" → "place order", "order place" → "place order"
- "Play Store" → usually means "place order" or "products"

ORDER PROCESSING RULES:
1. If user says "order", "place order", "checkout", "Play Store app" → proceed to order placement
2. For names: If unclear, use what you hear (e.g., "Mrutyunjay Patra" → accept as name)
3. For demo: Accept any reasonable name/address, don't ask for perfection
4 Text response: The user's statement "Play Store update" is still likely a mis-spoken attempt to place an order or refer to their order status.  Given the previous context, I'll assume they want to proceed with the order and request customer information. do not send the responce like this just call the funciton place_order() and pass the customer information. this is a unneccessary text response.
make the responce simple and direct.where not required do not add any text response. just call the required function with the required parameters.

CUSTOMER INFO COLLECTION:
- If user provides name: Store it and proceed
- If name unclear: Use what you hear, don't ask for clarification in demo
- For address: Accept simple addresses like "home", "office", "123 Main St"

FUNCTION SELECTION:
- search_products(): For product searches
- add_to_cart(): When user selects products
- get_cart_summary(): When user asks about cart
- remove_from_cart(): When user wants to remove items
- place_order(): When user wants to complete purchase
Detect user language:
        - Hindi words (mujhe, chahiye, kharidna, etc.) → respond in Hindi (code: hi)
        - Gujarati words (tame, cho, chhe, etc.) → respond in Gujarati (code: gu)
        - Otherwise → respond in English (code: en)
        - Transliterated Hindi/Gujarati → treat as native language

        Response format:
        <language>[code]</language><response>[reply]</response>

        Examples:
        User: "Mujhe kuchh kharidna tha"
        → <language>hi</language><response>आपको क्या चाहिए?</response>

        User: "Tame kya cho?"
        → <language>gu</language><response>हुं मजामा छूं! तमने शुं जोयए?</response>

RESPONSE FORMAT: Always use <language>code</language><response>message</response>"""

def parse_language_response(response_text):
    """Parse language-tagged response format"""
    import re
    
    language_match = re.search(r'<language>(\w+)</language>', response_text)
    response_match = re.search(r'<response>(.*?)</response>', response_text, re.DOTALL)
    
    if language_match and response_match:
        detected_language = language_match.group(1)
        clean_response = response_match.group(1).strip()
        return detected_language, clean_response
    
    return None, response_text

def initialize_session(call_sid):
    """Initialize a new chat session with the system prompt (optimized with warm-up)"""
    global warmup_session
    
    # Try to use warm-up session for faster initialization
    if warmup_session is not None:
        try:
            # Clone the warm-up session for this call
            model = genai.GenerativeModel(
                model_name='gemini-1.5-flash',
                tools=function_declarations
            )
            sessions[call_sid] = model.start_chat(history=[])
            sessions[call_sid].send_message(SYSTEM_PROMPT)
            print(f"DEBUG: Fast session initialization for {call_sid}")
        except Exception as e:
            print(f"DEBUG: Fast initialization failed, using standard method: {e}")
            # Fallback to standard initialization
            model = genai.GenerativeModel(
                model_name='gemini-1.5-flash',
                tools=function_declarations
            )
            sessions[call_sid] = model.start_chat(history=[])
            sessions[call_sid].send_message(SYSTEM_PROMPT)
    else:
        # Standard initialization
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            tools=function_declarations
        )
        sessions[call_sid] = model.start_chat(history=[])
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
    
    # Get current session language
    session_lang = get_session_language(call_sid)
    
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
            
            # Update global language immediately when detected by Gemini
            if 'language' in args and args['language'] in ["en", "hi", "gu"]:
                detected_lang = args['language']
                set_global_language(detected_lang)
                set_session_language(call_sid, detected_lang)
                print(f"DEBUG: Updated global language to {detected_lang}")
            
            if function_name == "search_products":
                query = args.get("query", "")
                lang_code = args.get("language", session_lang)
                results = search_products(query)
                
                if isinstance(results, dict):
                    if not results:
                        response_text = get_localized_text("no_inventory", lang_code) or "I don't have any items in stock right now."
                    else:
                        response_text = get_localized_text("available_categories", lang_code) or "Available categories: "
                        for category, items in list(results.items())[:3]:
                            response_text += f"{category} ({len(items)} items), "
                        response_text += get_localized_text("which_category", lang_code) or "Which category interests you?"
                
                elif isinstance(results, list):
                    if results:
                        if len(results) == 1:
                            item = results[0]
                            response_text = get_localized_text("ask_quantity", lang_code, item=item['Item Name']) or f"I found {item['Item Name']}. How many would you like?"
                        elif len(results) > 5:
                            response_text = get_localized_text("product_found", lang_code, count=len(results), items="") or f"Found {len(results)} products. Popular ones: "
                            product_names = [item['Item Name'] for item in results[:3]]
                            response_text += ", ".join(product_names) + ". "
                            response_text += get_localized_text("which_one", lang_code) or "Which one would you like?"
                        else:
                            response_text = get_localized_text("product_found", lang_code, count=len(results), items="") or "Found these products: "
                            product_names = [item['Item Name'] for item in results[:3]]
                            response_text += ", ".join(product_names) + ". "
                            response_text += get_localized_text("which_one", lang_code) or "Which one would you like?"
                    else:
                        similar = find_similar_products(query)
                        if similar:
                            response_text = get_localized_text("no_products", lang_code, query=query) or f"No '{query}' found. Similar items: "
                            similar_names = [item['Item Name'] for item in similar[:2]]
                            response_text += ", ".join(similar_names) + ". "
                            response_text += get_localized_text("which_interests", lang_code) or "Which one interests you?"
                        else:
                            categories = get_categories_summary()
                            if categories:
                                response_text = get_localized_text("no_products", lang_code, query=query) or f"No '{query}' found. Categories: "
                                for cat, count in list(categories.items())[:3]:
                                    response_text += f"{cat} ({count} items), "
                                response_text += get_localized_text("which_category", lang_code) or "Which category?"
                            else:
                                response_text = get_localized_text("no_products", lang_code, query=query) or f"No products matching '{query}' found."
            
            elif function_name == "add_to_cart":
                product_name = args.get("product_name", "")
                quantity = args.get("quantity", 1)
                lang_code = args.get("language", session_lang)
                
                customer_phone = None
                if call_sid in customer_info and "phone" in customer_info[call_sid]:
                    customer_phone = customer_info[call_sid]["phone"]
                elif call_sid in shopping_carts and "customer_phone" in shopping_carts[call_sid]:
                    customer_phone = shopping_carts[call_sid]["customer_phone"]
                
                success, response_text = add_to_cart(call_sid, product_name, quantity, customer_phone)
                
                # Localize the response
                if success:
                    response_text = get_localized_text("item_added", lang_code, qty=quantity, item=product_name) or response_text
                else:
                    response_text = get_localized_text("add_failed", lang_code) or response_text
                
                if success and call_sid in shopping_carts and len(shopping_carts[call_sid]["items"]) <= 2:
                    complementary = find_complementary_products(product_name, max_results=3)
                    cart_items = [item["name"] for item in shopping_carts[call_sid]["items"]]
                    available_suggestions = [item for item in complementary if item['Item Name'] not in cart_items]
                    
                    if available_suggestions:
                        item = available_suggestions[0]
                        suggestion_text = get_localized_text("suggest_item", lang_code, item=item['Item Name']) or f" Would you also like {item['Item Name']}?"
                        response_text += suggestion_text
            
            elif function_name == "remove_from_cart":
                product_name = args.get("product_name", "")
                lang_code = args.get("language", session_lang)
                success, response_text = remove_from_cart(call_sid, product_name)
                
                # Localize the response
                if success:
                    response_text = get_localized_text("item_removed", lang_code, item=product_name) or response_text
                else:
                    response_text = get_localized_text("remove_failed", lang_code) or response_text
            
            elif function_name == "get_cart_summary":
                lang_code = args.get("language", session_lang)
                response_text = get_cart_summary(call_sid)
                
                # Get localized cart summary if cart is empty
                if "empty" in response_text.lower():
                    response_text = get_localized_text("cart_empty", lang_code) or response_text
            
            elif function_name == "place_order":
                # Extract customer info from args or conversation context
                name = args.get("customer_name", "")
                phone = args.get("customer_phone", "")
                address = args.get("customer_address", "")
                lang_code = args.get("language", session_lang)
                
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
                    
                    success, response_text = place_order(call_sid, customer_data)
                    
                    # Localize order response
                    if success and "Order ID:" in response_text:
                        order_id = response_text.split("Order ID:")[1].strip()
                        response_text = get_localized_text("order_placed", lang_code, order_id=order_id) or response_text
                else:
                    response_text = get_localized_text("cart_empty", lang_code) or "Your cart is empty. Add items before ordering."
            
            else:
                response_text = "I'm not sure how to handle that request."
        
        else:
            response_text = response.text
            print(f"DEBUG: Text response: {response_text}")
        
        detected_lang, clean_response = parse_language_response(response_text)
        
        # Update session language if detected, otherwise preserve current session language
        if detected_lang and detected_lang in ["en", "hi", "gu"]:
            set_session_language(call_sid, detected_lang)
            set_global_language(detected_lang)  # Update global language too
        else:
            # Use existing session language if no language detected in response
            detected_lang = get_session_language(call_sid)
        
        add_to_conversation_history(call_sid, "assistant", clean_response)
        return detected_lang, clean_response
    
    except Exception as e:
        print(f"Error processing query: {e}")
        
        # Enhanced error handling for speech recognition issues
        user_input_lower = user_prompt.lower()
        session_lang = get_session_language(call_sid)
        
        # Handle common speech recognition errors
        if "play store" in user_input_lower or "playstore" in user_input_lower:
            # This usually means "place order" or "products"
            if "app" in user_input_lower or "application" in user_input_lower:
                response_text = get_localized_text("order_check_cart", session_lang) or "I understand you want to place an order. Let me check your cart first."
                if call_sid in shopping_carts and shopping_carts[call_sid]["items"]:
                    cart_summary = get_cart_summary(call_sid)
                    proceed_text = get_localized_text("proceed_order", session_lang) or "Would you like to proceed with the order?"
                    response_text = f"{response_text} {cart_summary} {proceed_text}"
                else:
                    response_text = get_localized_text("cart_empty_browse", session_lang) or "Your cart is empty. Would you like to browse some products first?"
            else:
                response_text = get_localized_text("products_available", session_lang) or "I found these products for you. What would you like to add to your cart?"
        
        elif "card" in user_input_lower and "check" in user_input_lower:
            # "check my card" → "check my cart"
            response_text = get_cart_summary(call_sid)
        
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
                success, response_text = place_order(call_sid, customer_info[call_sid])
                # Localize order response if successful
                if success and "Order ID:" in response_text:
                    order_id = response_text.split("Order ID:")[1].strip()
                    response_text = get_localized_text("order_placed", session_lang, order_id=order_id) or response_text
            else:
                response_text = get_localized_text("cart_empty", session_lang) or "Your cart is empty. Add items before ordering."
        
        else:
            # Generic error response
            response_text = get_localized_text("unclear_request", session_lang) or "I didn't understand that clearly. Could you please repeat?"
        
        response_text = f"<language>{session_lang}</language><response>{response_text}</response>"
        detected_lang, clean_response = parse_language_response(response_text)
        
        # Update session language if detected, otherwise preserve current session language
        if detected_lang and detected_lang in ["en", "hi", "gu"]:
            set_session_language(call_sid, detected_lang)
            set_global_language(detected_lang)
        else:
            # Use existing session language if no language detected in response
            detected_lang = get_session_language(call_sid)
        
        add_to_conversation_history(call_sid, "assistant", clean_response)
        return detected_lang, clean_response

# ---------------- FastAPI app ----------------
app = FastAPI()
call_retry_counts = {}

@app.post("/twiml")
async def twiml_endpoint():
    safe_greeting = "Namaste! Welcome to GroceryBabu! I am Aditi, your personal shopping assistant."
    
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
    
    # Start processing in background thread
    if call_sid not in processing_threads or not processing_threads[call_sid].is_alive():
        # Clear any previous results
        if call_sid in processing_results:
            del processing_results[call_sid]
        
        # Start new processing thread
        thread = threading.Thread(
            target=processing_worker,
            args=(call_sid, speech_result),
            daemon=True
        )
        processing_threads[call_sid] = thread
        thread.start()
        
        # Return immediate processing feedback in appropriate language
        processing_phrase = get_processing_phrase(current_language)
        
        xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi">{processing_phrase}</Say>
    <Pause length="2"/>
    <Redirect>https://{DOMAIN}/check-status/{call_sid}</Redirect>
</Response>"""
        
        return Response(content=xml_response, media_type="text/xml")
    
    else:
        # Already processing, check status
        return Response(content=generate_status_check_response(call_sid), media_type="text/xml")

@app.post("/check-status/{call_sid}")
async def check_status(call_sid: str):
    """Check processing status and return appropriate response"""
    if call_sid in processing_results and processing_results[call_sid]["ready"]:
        # Processing complete, return final response
        result = processing_results[call_sid]
        detected_language = result["language"]
        clean_response = result["response"]
        
        language_info = LANGUAGE_MAP.get(detected_language, LANGUAGE_MAP["default"])
        voice = language_info["voice"]
        
        # Clean up
        if call_sid in processing_results:
            del processing_results[call_sid]
        if call_sid in processing_queues:
            del processing_queues[call_sid]
        
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
    <Gather input="speech" language="{language_info['code']}" action="https://{DOMAIN}/handle-speech" speechTimeout="auto" enhanced="true">
    </Gather>
    <Say voice="{voice}">I did not hear you.</Say>
    <Gather input="speech" language="{language_info['code']}" action="https://{DOMAIN}/handle-speech" speechTimeout="auto" enhanced="true">
        <Say voice="{voice}">Please tell me what you need.</Say>
    </Gather>
    <Say voice="{voice}">I am having trouble hearing you. Please try calling again later.</Say>
    <Hangup/>
</Response>"""
        
        return Response(content=xml_response, media_type="text/xml")
    
    else:
        # Still processing, check again
        xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Pause length="2"/>
    <Redirect>https://{DOMAIN}/check-status/{call_sid}</Redirect>
</Response>"""
        
        return Response(content=xml_response, media_type="text/xml")

def generate_status_check_response(call_sid):
    """Generate XML response for status checking"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Pause length="2"/>
    <Redirect>https://{DOMAIN}/check-status/{call_sid}</Redirect>
</Response>"""

@app.get("/")
async def root():
    return {"message": "GroceryBabu Voice Assistant API - Aditi is ready to help!"}

if __name__ == "__main__":
    print(f"Starting server on port {PORT}")
    print(f"Main endpoint: {DOMAIN}/twiml")
    print(f"Speech handler: {DOMAIN}/handle-speech")
    print("GroceryBabu assistant Aditi is ready with processing feedback!")
    
    # Initialize inventory and search engine
    inventory = get_inventory()
    print(f"Found {len(inventory)} items in inventory")
    
    from intelligent_search import search_engine
    search_engine.refresh_inventory()
    print("Search engine refreshed")
    
    # Initialize Gemini warm-up session for faster first requests
    initialize_warmup_session()
    
    uvicorn.run(app, host="0.0.0.0", port=PORT)