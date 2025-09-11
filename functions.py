# ---------------- Function Declarations for Gemini ----------------
function_declarations = [
    {
        "name": "search_products",
        "description": "Search for products in the inventory. Use this when user asks about available products, grocery items, snacks, spices, food items, what do you have, show me products, or any product search query. For category requests like 'grocery items' or 'snacks', it will return top 5 items from that category.",
        "parameters": {
            "type_": "OBJECT",
            "properties": {
                "query": {
                    "type_": "STRING",
                    "description": "The search query - can be product name, category (like 'grocery items', 'snacks', 'spices'), or general queries like 'what do you have', 'available items'"
                },
                "category": {
                    "type_": "STRING",
                    "description": "Optional specific category filter"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "add_to_cart",
        "description": "Add a product to the shopping cart with specified quantity. ONLY use this when user provides BOTH product name AND quantity. If quantity is missing, ask the user for quantity instead of calling this function.",
        "parameters": {
            "type_": "OBJECT",
            "properties": {
                "product_name": {
                    "type_": "STRING",
                    "description": "The exact name of the product to add to cart"
                },
                "quantity": {
                    "type_": "INTEGER",
                    "description": "The quantity of the product to add - REQUIRED, do not assume or default to 1"
                }
            },
            "required": ["product_name", "quantity"]
        }
    },
    {
        "name": "get_cart_summary",
        "description": "Get a summary of the current shopping cart contents",
        "parameters": {
            "type_": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "remove_from_cart",
        "description": "Remove a product from the shopping cart. Use when user wants to remove, delete, or take out items from cart",
        "parameters": {
            "type_": "OBJECT",
            "properties": {
                "product_name": {
                    "type_": "STRING",
                    "description": "The name of the product to remove from cart"
                },
                "quantity": {
                    "type_": "INTEGER",
                    "description": "Optional quantity to remove. If not specified, removes all of that item"
                }
            },
            "required": ["product_name"]
        }
    },
    {
        "name": "place_order",
        "description": "Place the order with the current cart contents and customer information",
        "parameters": {
            "type_": "OBJECT",
            "properties": {
                "customer_name": {
                    "type_": "STRING",
                    "description": "The customer's name it is required"
                },
                "customer_phone": {
                    "type_": "STRING",
                    "description": "The customer's phone number"
                },
                "customer_address": {
                    "type_": "STRING",
                    "description": "The customer's full address including street, city, state and zip code"
                }
            },
            "required": ["customer_name", "customer_phone", "customer_address"]
        }
    }
]