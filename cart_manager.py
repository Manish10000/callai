from datetime import datetime
from sheets_handler import save_cart, delete_cart, save_customer
import json
# Global data stores
shopping_carts = {}  # {call_sid: {items: [], total: 0, customer_phone: ""}}
customer_info = {}   # {call_sid: {name: "", phone: "", address: "", city: "", state: "", zip: ""}}
conversation_history = {}  # {call_sid: [{role: "user"/"assistant", content: ""}]}

def add_to_cart(call_sid, product_name, quantity, customer_phone=None):
    """Add item to shopping cart and update Google Sheets"""
    from sheets_handler import get_inventory
    
    inventory = get_inventory()
    
    for item in inventory:
        if item.get("Item Name", "").lower() == product_name.lower():
            available_qty = item.get("Quantity", 0)
            if available_qty >= quantity:
                if call_sid not in shopping_carts:
                    shopping_carts[call_sid] = {"items": [], "total": 0, "customer_phone": customer_phone}
                
                # Check if item already in cart
                item_found = False
                for cart_item in shopping_carts[call_sid]["items"]:
                    if cart_item["name"] == item["Item Name"]:
                        cart_item["quantity"] += quantity
                        cart_item["subtotal"] = cart_item["quantity"] * item["Price (USD)"]
                        item_found = True
                        break
                
                if not item_found:
                    shopping_carts[call_sid]["items"].append({
                        "name": item["Item Name"],
                        "quantity": quantity,
                        "price": item["Price (USD)"],
                        "subtotal": quantity * item["Price (USD)"]
                    })
                
                shopping_carts[call_sid]["total"] = sum(item["subtotal"] for item in shopping_carts[call_sid]["items"])
                
                # Save to Google Sheets
                save_cart(call_sid, shopping_carts[call_sid])
                
                return True, f"Added {quantity} {item['Item Name']} to your cart."
            else:
                return False, f"Only {available_qty} available. Would you like to add {available_qty} instead?"
    
    return False, "Product not found."

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