from datetime import datetime
from sheets_handler import save_cart, delete_cart, save_customer
import json
# Global data stores
shopping_carts = {}  # {call_sid: {items: [], total: 0, customer_phone: ""}}
customer_info = {}   # {call_sid: {name: "", phone: "", address: "", city: "", state: "", zip: ""}}
conversation_history = {}  # {call_sid: [{role: "user"/"assistant", content: ""}]}

def add_to_cart(call_sid, product_name, quantity, customer_phone=None):
    """Add item to shopping cart and update Google Sheets"""
    from sheets_handler import get_inventory, save_cart
    
    inventory = get_inventory()
    print(f"DEBUG: add_to_cart searching for '{product_name}' in {len(inventory)} items")
    
    # First try exact match
    matched_item = None
    for item in inventory:
        item_name = item.get("Item Name", "")
        print(f"DEBUG: Comparing '{product_name.lower()}' with '{item_name.lower()}'")
        if item_name.lower() == product_name.lower():
            matched_item = item
            print(f"DEBUG: Exact match found: {item_name}")
            break
    
    # If no exact match, try fuzzy matching
    if not matched_item:
        best_match = None
        best_score = 0
        
        for item in inventory:
            item_name = item.get("Item Name", "")
            score = 0
            
            # Calculate similarity score
            if product_name.lower() == item_name.lower():
                score = 1.0  # Exact match
            elif product_name.lower() in item_name.lower():
                score = 0.8  # Product name contained in item name
            elif item_name.lower() in product_name.lower():
                score = 0.7  # Item name contained in product name
            else:
                # Check word matches
                product_words = set(product_name.lower().split())
                item_words = set(item_name.lower().split())
                common_words = product_words.intersection(item_words)
                if common_words:
                    score = len(common_words) / max(len(product_words), len(item_words))
            
            if score > best_score and score >= 0.3:  # Minimum threshold
                best_score = score
                best_match = item
        
        if best_match:
            matched_item = best_match
            print(f"DEBUG: Best fuzzy match found: {matched_item['Item Name']} (score: {best_score:.2f}) for query '{product_name}'")
    
    if matched_item:
        available_qty = matched_item.get("Quantity", 0)
        print(f"DEBUG: Found item '{matched_item['Item Name']}' with quantity {available_qty}")
        
        if available_qty >= quantity:
            if call_sid not in shopping_carts:
                shopping_carts[call_sid] = {"items": [], "total": 0, "customer_phone": customer_phone}
            
            # Check if item already in cart
            item_found = False
            for cart_item in shopping_carts[call_sid]["items"]:
                if cart_item["name"] == matched_item["Item Name"]:
                    cart_item["quantity"] += quantity
                    cart_item["subtotal"] = cart_item["quantity"] * matched_item["Price (USD)"]
                    item_found = True
                    break
            
            if not item_found:
                shopping_carts[call_sid]["items"].append({
                    "name": matched_item["Item Name"],
                    "quantity": quantity,
                    "price": matched_item["Price (USD)"],
                    "subtotal": quantity * matched_item["Price (USD)"]
                })
            
            shopping_carts[call_sid]["total"] = sum(item["subtotal"] for item in shopping_carts[call_sid]["items"])
            
            # Save to Google Sheets
            try:
                # Format cart data for sheets
                cart_for_sheets = {
                    "Customer Phone": shopping_carts[call_sid].get("customer_phone", ""),
                    "Items": shopping_carts[call_sid]["items"],
                    "Total": shopping_carts[call_sid]["total"]
                }
                save_cart(call_sid, cart_for_sheets)
                print(f"DEBUG: Cart saved to Google Sheets for session {call_sid}")
            except Exception as e:
                print(f"ERROR: Failed to save cart to sheets: {e}")
            
            return True, f"Added {quantity} {matched_item['Item Name']} to your cart."
        else:
            return False, f"Only {available_qty} available. Would you like to add {available_qty} instead?"
    
    return False, "Product not found."

def remove_from_cart(call_sid, product_name, quantity=None):
    """Remove item from shopping cart"""
    from sheets_handler import save_cart
    
    if call_sid not in shopping_carts:
        return False, "Your cart is empty."
    
    cart = shopping_carts[call_sid]
    
    # Find the item in cart
    for i, cart_item in enumerate(cart["items"]):
        if product_name.lower() in cart_item["name"].lower() or cart_item["name"].lower() in product_name.lower():
            if quantity is None or quantity >= cart_item["quantity"]:
                # Remove entire item
                removed_item = cart["items"].pop(i)
                cart["total"] = sum(item["subtotal"] for item in cart["items"])
                
                # Save to Google Sheets
                try:
                    cart_for_sheets = {
                        "Customer Phone": cart.get("customer_phone", ""),
                        "Items": cart["items"],
                        "Total": cart["total"]
                    }
                    save_cart(call_sid, cart_for_sheets)
                    print(f"DEBUG: Cart updated after removing {removed_item['name']}")
                except Exception as e:
                    print(f"ERROR: Failed to save cart after removal: {e}")
                
                return True, f"Removed {removed_item['name']} from your cart."
            else:
                # Reduce quantity
                cart_item["quantity"] -= quantity
                cart_item["subtotal"] = cart_item["quantity"] * cart_item["price"]
                cart["total"] = sum(item["subtotal"] for item in cart["items"])
                
                # Save to Google Sheets
                try:
                    cart_for_sheets = {
                        "Customer Phone": cart.get("customer_phone", ""),
                        "Items": cart["items"],
                        "Total": cart["total"]
                    }
                    save_cart(call_sid, cart_for_sheets)
                    print(f"DEBUG: Cart updated after reducing {cart_item['name']} quantity")
                except Exception as e:
                    print(f"ERROR: Failed to save cart after quantity reduction: {e}")
                
                return True, f"Reduced {cart_item['name']} quantity by {quantity}. Now you have {cart_item['quantity']} in cart."
    
    return False, f"Could not find {product_name} in your cart."

def get_cart_summary(call_sid):
    """Get summary of shopping cart"""
    if call_sid not in shopping_carts or not shopping_carts[call_sid]["items"]:
        return "Your cart is empty."
    
    cart = shopping_carts[call_sid]
    summary = "Your cart contains: "
    for item in cart["items"]:
        summary += f"{item['quantity']} {item['name']}, "
    summary += f"Total: ${cart['total']:.2f}"
    return summary

def place_order(call_sid, customer_data):
    """Place order and update Google Sheets"""
    if call_sid not in shopping_carts or not shopping_carts[call_sid]["items"]:
        return False, "Your cart is empty. Cannot place order."
    
    try:
        # Update inventory
        from sheets_handler import get_inventory, inventory_sheet
        inventory = get_inventory()
        for cart_item in shopping_carts[call_sid]["items"]:
            for i, item in enumerate(inventory):
                if item["Item Name"] == cart_item["name"]:
                    new_qty = item["Quantity"] - cart_item["quantity"]
                    # Update Google Sheets
                    inventory_sheet.update_cell(i+2, 3, new_qty)  # +2 because of header row
        
        # Add to orders sheet
        from sheets_handler import orders_sheet
        order_data = [
            datetime.now().strftime("%Y%m%d%H%M%S"),  # Order ID
            customer_data.get("phone", ""),
            json.dumps(shopping_carts[call_sid]["items"]),
            shopping_carts[call_sid]["total"],
            "Pending",
            datetime.now().strftime("%Y-%m-%d")
        ]
        orders_sheet.append_row(order_data)
        
        # Save/update customer information
        save_customer({
            "Phone Number": customer_data.get("phone", ""),
            "Name": customer_data.get("name", ""),
            "Address": customer_data.get("address", ""),
            "City": customer_data.get("city", ""),
            "State": customer_data.get("state", ""),
            "Zip": customer_data.get("zip", ""),
            "Last Order Date": datetime.now().strftime("%Y-%m-%d")
        })
        
        # Clear cart
        order_total = shopping_carts[call_sid]["total"]
        shopping_carts[call_sid] = {"items": [], "total": 0, "customer_phone": customer_data.get("phone", "")}
        
        # Remove cart from Google Sheets
        delete_cart(call_sid)
        
        return True, f"Order placed successfully! Your total is ${order_total:.2f}. Thank you for shopping with GroceryBabu!"
    
    except Exception as e:
        return False, f"Error placing order: {str(e)}"

def add_to_conversation_history(call_sid, role, content):
    """Add message to conversation history"""
    if call_sid not in conversation_history:
        conversation_history[call_sid] = []
    
    conversation_history[call_sid].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    })
    
    # Keep only the last 10 messages to avoid memory issues
    if len(conversation_history[call_sid]) > 10:
        conversation_history[call_sid] = conversation_history[call_sid][-10:]

def get_conversation_context(call_sid):
    """Get recent conversation context"""
    if call_sid not in conversation_history:
        return ""
    
    context = "Recent conversation:\n"
    for msg in conversation_history[call_sid][-5:]:  # Last 5 messages
        context += f"{msg['role']}: {msg['content']}\n"
    
    return context