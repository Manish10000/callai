# ---------------- Function Declarations for Gemini ----------------
function_declarations = [
    {
        "name": "search_products",
        "description": "Search for products in the inventory by name, category, or tags",
        "parameters": {
            "type_": "OBJECT",
            "properties": {
                "query": {
                    "type_": "STRING",
                    "description": "The search query to find products"
                },
                "category": {
                    "type_": "STRING",
                    "description": "Optional category filter for the search"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "add_to_cart",
        "description": "Add a product to the shopping cart with specified quantity",
        "parameters": {
            "type_": "OBJECT",
            "properties": {
                "product_name": {
                    "type_": "STRING",
                    "description": "The exact name of the product to add to cart"
                },
                "quantity": {
                    "type_": "INTEGER",
                    "description": "The quantity of the product to add"
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
        "name": "place_order",
        "description": "Place the order with the current cart contents and customer information",
        "parameters": {
            "type_": "OBJECT",
            "properties": {
                "customer_name": {
                    "type_": "STRING",
                    "description": "The customer's full name"
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