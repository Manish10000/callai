import json
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import os

# These will be initialized by main.py
inventory_sheet = None
customers_sheet = None
orders_sheet = None
carts_sheet = None

def get_inventory():
    """Get current inventory from Google Sheets"""
    try:
        records = inventory_sheet.get_all_records()
        print(f"DEBUG: Found {len(records)} inventory records")
        
        # Ensure numeric values are properly converted
        for record in records:
            if "Quantity" in record:
                try:
                    record["Quantity"] = int(record["Quantity"]) if str(record["Quantity"]).isdigit() else 0
                except:
                    record["Quantity"] = 0
            if "Price (USD)" in record:
                try:
                    record["Price (USD)"] = float(record["Price (USD)"])
                except:
                    record["Price (USD)"] = 0.0
        
        # Print inventory for debugging
        print("DEBUG: Inventory contents:")
        for i, item in enumerate(records[:5]):  # Print first 5 items
            print(f"  {i+1}. {item.get('Item Name', 'N/A')} - Qty: {item.get('Quantity', 0)} - Price: ${item.get('Price (USD)', 0):.2f}")
        if len(records) > 5:
            print(f"  ... and {len(records) - 5} more items")
            
        return records
    except Exception as e:
        print(f"Error getting inventory: {e}")
        # Fallback to hardcoded data if Sheets is unavailable
        fallback_data = [
            {"Item Name": "Chora Black Eyed Peas 4 lb", "Category": "Grocery", "Quantity": 3, "Price (USD)": 10.49, "Description": "Organic black eyed peas", "Tags": "pulses, organic, grocery"},
            {"Item Name": "Milk Bikis Minis Wafflez 7 oz", "Category": "Snacks", "Quantity": 5, "Price (USD)": 2.29, "Description": "Crispy mini waffle biscuits", "Tags": "biscuits, snacks, crispy"},
            {"Item Name": "Maggi Masala Noodles", "Category": "Food", "Quantity": 10, "Price (USD)": 1.99, "Description": "Instant masala noodles", "Tags": "noodles, instant, masala"},
            {"Item Name": "Tomato Ketchup", "Category": "Condiments", "Quantity": 8, "Price (USD)": 3.49, "Description": "Sweet and tangy tomato ketchup", "Tags": "ketchup, tomato, condiments"},
            {"Item Name": "Basmati Rice 5kg", "Category": "Grocery", "Quantity": 4, "Price (USD)": 15.99, "Description": "Premium long grain basmati rice", "Tags": "rice, basmati, grocery"},
        ]
        print("DEBUG: Using fallback inventory data")
        return fallback_data

def get_customer_by_phone(phone):
    """Get customer details by phone number"""
    try:
        customers = customers_sheet.get_all_records()
        for customer in customers:
            if customer["Phone Number"] == phone:
                return customer
        return None
    except Exception as e:
        print(f"Error getting customer: {e}")
        return None

def save_customer(customer_data):
    """Save or update customer details"""
    try:
        customers = customers_sheet.get_all_records()
        
        # Find if customer already exists
        for i, customer in enumerate(customers):
            if customer["Phone Number"] == customer_data["Phone Number"]:
                # Update existing customer
                row_num = i + 2  # +2 for header row and 0-based index
                for col_num, key in enumerate(["Phone Number", "Name", "Address", "City", "State", "Zip", "Last Order Date"], 1):
                    if key in customer_data:
                        customers_sheet.update_cell(row_num, col_num, customer_data[key])
                return
        
        # Add new customer
        customers_sheet.append_row([
            customer_data.get("Phone Number", ""),
            customer_data.get("Name", ""),
            customer_data.get("Address", ""),
            customer_data.get("City", ""),
            customer_data.get("State", ""),
            customer_data.get("Zip", ""),
            customer_data.get("Last Order Date", "")
        ])
    except Exception as e:
        print(f"Error saving customer: {e}")

def save_cart(session_id, cart_data):
    """Save cart to Google Sheets"""
    try:
        carts = carts_sheet.get_all_records()
        
        # Find if cart already exists for this session
        for i, cart in enumerate(carts):
            if cart["Session ID"] == session_id:
                # Update existing cart
                row_num = i + 2  # +2 for header row and 0-based index
                carts_sheet.update_cell(row_num, 2, cart_data.get("Customer Phone", ""))
                carts_sheet.update_cell(row_num, 3, json.dumps(cart_data.get("Items", [])))
                carts_sheet.update_cell(row_num, 4, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                return
        
        # Add new cart
        carts_sheet.append_row([
            session_id,
            cart_data.get("Customer Phone", ""),
            json.dumps(cart_data.get("Items", [])),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ])
    except Exception as e:
        print(f"Error saving cart: {e}")

def load_cart(session_id):
    """Load cart from Google Sheets"""
    try:
        carts = carts_sheet.get_all_records()
        for cart in carts:
            if cart["Session ID"] == session_id:
                try:
                    items = json.loads(cart["Items JSON"])
                except:
                    items = []
                
                return {
                    "Customer Phone": cart.get("Customer Phone", ""),
                    "Items": items,
                    "Last Updated": cart.get("Last Updated", "")
                }
        return None
    except Exception as e:
        print(f"Error loading cart: {e}")
        return None

def delete_cart(session_id):
    """Delete cart from Google Sheets"""
    try:
        carts = carts_sheet.get_all_records()
        for i, cart in enumerate(carts):
            if cart["Session ID"] == session_id:
                carts_sheet.delete_rows(i + 2)  # +2 for header row and 0-based index
                return True
        return False
    except Exception as e:
        print(f"Error deleting cart: {e}")
        return False