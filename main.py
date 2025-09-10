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
from cart_manager import shopping_carts, customer_info, conversation_history, add_to_cart, get_cart_summary, place_order, add_to_conversation_history, get_conversation_context, remove_from_cart
from product_search import search_products, find_similar_products, find_complementary_products, get_categories_summary

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
WELCOME_GREETING = "नमस्ते! Welcome to GroceryBabu! I'm Aditi, your personal shopping assistant. You can ask me about products, add items to your cart, or place an order."

# ---------------- Gemini API ----------------
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set.")

genai.configure(api_key=GOOGLE_API_KEY)

# Store active chat sessions and context
sessions = {}
conversation_context = {}  # Store what user was looking at

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
    
    # Handle context-aware responses
    user_lower = user_prompt.lower().strip()
    
    # Fix common speech-to-text errors for grocery context
    speech_corrections = {
        # Cart vs Car confusion
        "car price": "cart price",
        "car total": "cart total", 
        "my car": "my cart",
        "the car": "the cart",
        "car summary": "cart summary",
        "car items": "cart items",
        "what's in my car": "what's in my cart",
        "car contents": "cart contents",
        "car cost": "cart cost",
        "car amount": "cart amount",
        "know what is my car": "what is my cart",
        "what is my car": "what is my cart",
        
        # Common product name corrections
        "milk vicks": "milk bikis",
        "milk wicks": "milk bikis", 
        "milk wickets": "milk bikis",
        "milk best": "milk bikis",
        
        # Other common errors
        "type of them": "two of them",
        "wife of the": "five of them",
        "tour of": "two of",
        "auto": "two",
        "offline": "all fine"
    }
    
    # Apply corrections
    original_prompt = user_prompt
    for wrong, correct in speech_corrections.items():
        if wrong in user_lower:
            user_prompt = user_prompt.replace(wrong, correct)
            user_lower = user_prompt.lower().strip()
            print(f"DEBUG: Speech correction: '{original_prompt}' → '{user_prompt}'")
            break
    
    # Check for simple confirmations
    if user_lower in ["yes", "yeah", "yep", "sure", "ok", "okay"]:
        # Check what they were confirming
        if call_sid in conversation_context:
            ctx = conversation_context[call_sid]
            if ctx.get("action") == "add_to_cart" and ctx.get("product"):
                # They want to add the product we just showed them - but ask for quantity
                user_prompt = f"User wants to add {ctx['product']} - ask for quantity"
                print(f"DEBUG: Context-aware: User confirmed adding {ctx['product']}, need to ask quantity")
            elif ctx.get("action") == "ask_quantity" and ctx.get("product"):
                # They confirmed but we need quantity
                user_prompt = f"How many {ctx['product']} do you want?"
                print(f"DEBUG: Context-aware: Need quantity for {ctx['product']}")
    
    # Check for quantity responses (but not phone numbers)
    elif (any(num in user_lower for num in ["one", "two", "three", "four", "five", "1", "2", "3", "4", "5"]) and 
          not any(phone_word in user_lower for phone_word in ["phone", "number", "contact", "mobile"]) and
          len(user_prompt.replace(" ", "")) < 10):  # Phone numbers are usually longer
        if call_sid in conversation_context and conversation_context[call_sid].get("product"):
            product = conversation_context[call_sid]["product"]
            user_prompt = f"Add {product} quantity {user_prompt}"
            print(f"DEBUG: Context-aware: Adding {product} with quantity from '{user_prompt}'")
    
    # Check if user is trying to add something without specifying quantity
    elif any(phrase in user_lower for phrase in ["i want", "i need", "add"]) and not any(num in user_prompt for num in ["1", "2", "3", "4", "5", "one", "two", "three", "four", "five"]):
        # Look for product names in recent conversation
        recent_messages = conversation_history.get(call_sid, [])[-3:]  # Last 3 messages
        for msg in recent_messages:
            if msg["role"] == "assistant" and "found" in msg["content"].lower():
                # Extract product name from assistant's previous response
                import re
                product_match = re.search(r'I found ([^(]+)', msg["content"])
                if product_match:
                    product_name = product_match.group(1).strip()
                    enhanced_prompt = f"User wants to add {product_name}. Ask for quantity: {user_prompt}"
                    user_prompt = enhanced_prompt
                    break
    
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
    
    # Prepare the prompt with context and instructions
    system_instructions = """You are Aditi, a helpful grocery store assistant at GroceryBabu. ALWAYS use the available functions when appropriate:

    - When user asks about products/items/groceries (like "what do you have", "show me products", "grocery available") → USE search_products function
    - When user wants to add items WITH quantity (like "I want 2 milk biscuits") → USE add_to_cart function  
    - When user wants to add items WITHOUT quantity (like "I want milk biscuits") → ASK for quantity, don't assume 1
    - When user wants to remove items → USE remove_from_cart function
    - When user asks about cart → USE get_cart_summary function
    - When user wants to order → USE place_order function

    IMPORTANT CONTEXT RULES:
    - If user says "yes/yeah/sure" after you showed them a product, they want to add it - ASK FOR QUANTITY
    - If user gives a number after asking "how many", use add_to_cart with that quantity
    - Remember what product you just discussed
    - When collecting order info, recognize: names (like "Sanjay Patra"), phone numbers (like "7750 944 643"), addresses
    - Don't suggest products that are already in the cart
    - NEVER assume quantity = 1, always ask if not provided

    SPEECH RECOGNITION ERROR HANDLING:
    - If user mentions "car price/total/cost" they likely mean "cart price/total/cost" (shopping cart)
    - We are a GROCERY store, we don't sell cars - interpret car-related queries as cart-related
    - "What's my car price?" = "What's my cart total?" → USE get_cart_summary
    - "Car items" = "Cart items" → USE get_cart_summary
    - Always assume grocery/food context, never automotive

    Be conversational and natural. Keep responses short and friendly. You can introduce yourself as Aditi when appropriate."""
    
    # Add current context if available
    context_info = ""
    if call_sid in conversation_context:
        ctx = conversation_context[call_sid]
        if ctx.get("product"):
            context_info = f"\nCURRENT CONTEXT: User was just shown {ctx['product']} for ${ctx.get('price', 'N/A')}. "
            if ctx.get("action") == "add_to_cart":
                context_info += "They might want to add this item."
            elif ctx.get("action") == "ask_quantity":
                context_info += "You asked for quantity."
    
    full_prompt = f"{system_instructions}\n\n{context}{context_info}\n\nUser: {user_prompt}"
    
    try:
        # Send the message to Gemini
        print(f"DEBUG: Sending to Gemini: {full_prompt}")
        response = sessions[call_sid].send_message(full_prompt)
        
        print(f"DEBUG: Gemini response parts: {len(response.candidates[0].content.parts) if response.candidates else 0}")
        if response.candidates and response.candidates[0].content.parts:
            for i, part in enumerate(response.candidates[0].content.parts):
                print(f"DEBUG: Part {i}: has function_call = {hasattr(part, 'function_call') and part.function_call}")
                if hasattr(part, 'text') and part.text:
                    print(f"DEBUG: Part {i} text: {part.text[:100]}...")
        
        # Check if the response contains a function call
        has_function_call = False
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    has_function_call = True
                    function_call = part.function_call
                    function_name = function_call.name
                    args = dict(function_call.args)  # Convert protobuf to dict
                    break
        
        if has_function_call:
            
            print(f"DEBUG: Function call detected: {function_name} with args: {args}")
            
            # Execute the appropriate function
            if function_name == "search_products":
                query = args.get("query", "")
                category = args.get("category", None)
                results = search_products(query, category)
                
                print(f"DEBUG: Search query: '{query}', found results type: {type(results)}")
                
                # Handle category-organized results
                if isinstance(results, dict):
                    # Results organized by category
                    if not results:
                        response_text = "I don't have any items in stock right now. Please check back later."
                    else:
                        response_text = "Here are our available categories: "
                        for category, items in list(results.items())[:3]:  # Show top 3 categories
                            response_text += f"{category} ({len(items)} items), "
                        response_text += "Which category interests you?"
                
                elif isinstance(results, list):
                    print(f"DEBUG: Found {len(results)} products")
                    
                    if results:
                        # Check if this is a category-specific request (top 5 items)
                        category_keywords = ["grocery", "groceries", "snack", "snacks", "spice", "spices", "food", "foods"]
                        is_category_request = any(keyword in query.lower() for keyword in category_keywords)
                        
                        if is_category_request and len(results) <= 5:
                            # Show top items from specific category
                            category_name = None
                            for keyword in category_keywords:
                                if keyword in query.lower():
                                    category_name = keyword.title()
                                    break
                            
                            response_text = f"Here are our top {category_name or 'items'}: "
                            for i, item in enumerate(results, 1):
                                response_text += f"{i}. {item['Item Name']} (${item['Price (USD)']}), "
                            response_text += "Which one would you like?"
                            
                        elif len(results) == 1 or (len(results) > 1 and results[0].get('similarity_score', 0) > 0.5):
                            # Single product found OR very high similarity match - make it easy to add
                            item = results[0]
                            response_text = f"I found {item['Item Name']} for ${item['Price (USD)']}. We have {item['Quantity']} available. Would you like to add this to your cart?"
                            
                            # Store context for next interaction
                            conversation_context[call_sid] = {
                                "action": "add_to_cart",
                                "product": item['Item Name'],
                                "price": item['Price (USD)'],
                                "available": item['Quantity']
                            }
                        elif len(results) > 5:
                            response_text = f"I found {len(results)} products. Here are some popular ones: "
                            for item in results[:3]:  # Show only top 3
                                response_text += f"{item['Item Name']} (${item['Price (USD)']}), "
                            response_text += "Which one would you like?"
                        else:
                            response_text = f"I found these products: "
                            for item in results[:3]:  # Show top 3 results
                                response_text += f"{item['Item Name']} (${item['Price (USD)']}), "
                            response_text += "Which one would you like?"
                    else:
                        # Try to find similar products using vector search
                        similar = find_similar_products(query)
                        if similar:
                            if len(similar) == 1:
                                item = similar[0]
                                response_text = f"I couldn't find '{query}', but I have {item['Item Name']} for ${item['Price (USD)']}. Would you like this instead?"
                            else:
                                response_text = f"I couldn't find '{query}', but here are some similar items: "
                                for item in similar[:2]:  # Only show 2 similar items
                                    response_text += f"{item['Item Name']} (${item['Price (USD)']}), "
                                response_text += "Which one interests you?"
                        else:
                            # Show categories as fallback
                            categories = get_categories_summary()
                            if categories:
                                response_text = f"I couldn't find '{query}'. We have items in these categories: "
                                for cat, count in list(categories.items())[:3]:
                                    response_text += f"{cat} ({count} items), "
                                response_text += "Which category would you like to explore?"
                            else:
                                response_text = f"I couldn't find any products matching '{query}'. Could you try a different name?"
            
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
                
                # Clear context after successful add
                if success and call_sid in conversation_context:
                    del conversation_context[call_sid]
                
                # Suggest one complementary product only if cart is small
                if success and call_sid in shopping_carts and len(shopping_carts[call_sid]["items"]) <= 2:
                    complementary = find_complementary_products(product_name, max_results=3)
                    
                    # Filter out items already in cart
                    cart_items = [item["name"] for item in shopping_carts[call_sid]["items"]]
                    available_suggestions = [item for item in complementary if item['Item Name'] not in cart_items]
                    
                    if available_suggestions:
                        item = available_suggestions[0]
                        response_text += f" Would you also like {item['Item Name']} for ${item['Price (USD)']}?"
                        
                        # Store context for the suggestion
                        conversation_context[call_sid] = {
                            "action": "add_to_cart",
                            "product": item['Item Name'],
                            "price": item['Price (USD)'],
                            "available": item.get('Quantity', 0)
                        }
            
            elif function_name == "remove_from_cart":
                product_name = args.get("product_name", "")
                quantity = args.get("quantity", None)
                
                success, response_text = remove_from_cart(call_sid, product_name, quantity)
                
                # Clear context after removal
                if success and call_sid in conversation_context:
                    del conversation_context[call_sid]
            
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
            print(f"DEBUG: No function call detected, using text response: {response_text}")
            
            # Check for cart-related queries that might be misunderstood
            cart_keywords = ["cart price", "cart total", "cart cost", "cart summary", "cart items", "my cart", "what's in my cart", "cart contents"]
            if any(keyword in user_prompt.lower() for keyword in cart_keywords):
                print("DEBUG: Detected cart query, manually calling get_cart_summary")
                response_text = get_cart_summary(call_sid)
            
            # Check if this should have been a search function call
            elif any(keyword in user_prompt.lower() for keyword in ["grocery", "groceries", "items", "products", "available", "present", "list", "show", "what do you have", "what are", "snack", "snacks", "spice", "spices", "food", "foods"]):
                print("DEBUG: This looks like a search query, manually calling search_products")
                # Manually call search function
                results = search_products(user_prompt)
                
                if isinstance(results, dict):
                    # Results organized by category
                    if not results:
                        response_text = "I don't have any items in stock right now. Please check back later."
                    else:
                        response_text = "Here are our available categories: "
                        for category, items in list(results.items())[:3]:  # Show top 3 categories
                            response_text += f"{category} ({len(items)} items), "
                        response_text += "Which category interests you?"
                elif isinstance(results, list) and results:
                    # Check if this is a category-specific request
                    category_keywords = ["grocery", "groceries", "snack", "snacks", "spice", "spices", "food", "foods"]
                    is_category_request = any(keyword in user_prompt.lower() for keyword in category_keywords)
                    
                    if is_category_request and len(results) <= 5:
                        # Show top items from specific category
                        category_name = None
                        for keyword in category_keywords:
                            if keyword in user_prompt.lower():
                                category_name = keyword.title()
                                break
                        
                        response_text = f"Here are our top {category_name or 'items'}: "
                        for i, item in enumerate(results, 1):
                            response_text += f"{i}. {item['Item Name']} (${item['Price (USD)']}), "
                        response_text += "Which one would you like?"
                        
                    elif len(results) == 1:
                        item = results[0]
                        response_text = f"I found {item['Item Name']} for ${item['Price (USD)']}. We have {item['Quantity']} available. Would you like to add this to your cart?"
                        
                        # Store context
                        conversation_context[call_sid] = {
                            "action": "add_to_cart",
                            "product": item['Item Name'],
                            "price": item['Price (USD)'],
                            "available": item['Quantity']
                        }
                    else:
                        response_text = f"I found {len(results)} products. Here are some: "
                        for item in results[:3]:
                            response_text += f"{item['Item Name']} (${item['Price (USD)']}), "
                        response_text += "Which one would you like?"
            
            # Handle context-aware quantity questions
            elif call_sid in conversation_context and "how many" in response_text.lower():
                ctx = conversation_context[call_sid]
                if ctx.get("product"):
                    # Update context to expect quantity
                    conversation_context[call_sid]["action"] = "ask_quantity"
            
            # Clear context when order process starts
            elif any(word in user_prompt.lower() for word in ["place order", "order", "checkout"]):
                if call_sid in conversation_context:
                    del conversation_context[call_sid]
                    print("DEBUG: Cleared context for order process")
            
            # Make responses more natural and helpful
            elif "quantity" in user_prompt.lower() or any(num in user_prompt.lower() for num in ["one", "two", "three", "1", "2", "3"]):
                # User mentioned quantity but function wasn't called - help them
                if "horse gram" in user_prompt.lower():
                    response_text = "How many Horse Gram 2 lb would you like to add to your cart?"
                elif any(product in user_prompt.lower() for product in ["chora", "black eyed", "peas"]):
                    response_text = "How many Chora Black Eyed Peas 4 lb would you like to add?"
        
        # Add to conversation history
        add_to_conversation_history(call_sid, "assistant", response_text)
        
        # Default to English for now since function calling doesn't provide language info
        return "en", response_text
    
    except Exception as e:
        print(f"Error processing query with Gemini: {e}")
        
        # Handle quota exceeded error with better fallback
        if "429" in str(e) or "quota" in str(e).lower():
            # Use manual processing when quota exceeded
            user_lower = user_prompt.lower()
            
            # Handle common patterns manually
            if any(word in user_lower for word in ["cart", "car"]) and any(word in user_lower for word in ["price", "total", "cost", "summary"]):
                response_text = get_cart_summary(call_sid)
            elif any(word in user_lower for word in ["name is", "my name"]):
                response_text = "Thank you! Now I need your phone number and address to complete the order."
            elif any(word in user_lower for word in ["phone", "number", "contact"]) and any(char.isdigit() for char in user_prompt):
                response_text = "Got it! Now please provide your full address including street, city, state, and zip code."
            elif any(word in user_lower for word in ["address", "live", "location", "street", "city"]):
                response_text = "Perfect! Let me place your order now."
            elif any(word in user_lower for word in ["thank", "bye", "goodbye"]):
                response_text = "Thank you for shopping with GroceryBabu! Have a great day!"
            else:
                response_text = "I'm experiencing high traffic right now. Could you please be more specific about what you need?"
        else:
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
    return {"message": "GroceryBabu Voice Assistant API - Aditi is ready to help!"}

if __name__ == "__main__":
    print(f"Starting server on port {PORT}")
    print("Available endpoints:")
    print(f"  - Main endpoint: {DOMAIN}/twiml")
    print(f"  - Speech handler: {DOMAIN}/handle-speech")
    print("GroceryBabu assistant Aditi is ready with function calling!")
    
    # Test inventory reading and refresh search engine
    print("Testing inventory access...")
    inventory = get_inventory()
    print(f"Found {len(inventory)} items in inventory")
    
    # Refresh the search engine with latest inventory
    from intelligent_search import search_engine
    search_engine.refresh_inventory()
    print("Search engine refreshed with latest inventory")
    
    uvicorn.run(app, host="0.0.0.0", port=PORT)