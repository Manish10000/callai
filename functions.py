# functions.py
function_declarations = [
    {
        "name": "search_products",
        "description": "Search for products in the inventory.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "The search query"
                },
                "category": {
                    "type": "STRING",
                    "description": "Optional category filter"
                },
                "language": {
                    "type": "STRING",
                    "description": "Language code: en, hi, or gu",
                    "enum": ["en", "hi", "gu"]
                }
            },
            "required": ["query", "language"]
        }
    },
    {
        "name": "add_to_cart",
        "description": "Add a product to the shopping cart",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "product_name": {
                    "type": "STRING",
                    "description": "The exact product name"
                },
                "quantity": {
                    "type": "INTEGER",
                    "description": "The quantity to add"
                },
                "language": {
                    "type": "STRING",
                    "description": "Language code: en, hi, or gu",
                    "enum": ["en", "hi", "gu"]
                }
            },
            "required": ["product_name", "quantity", "language"]
        }
    },
    {
        "name": "get_cart_summary",
        "description": "Get shopping cart summary",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "language": {
                    "type": "STRING",
                    "description": "Language code: en, hi, or gu",
                    "enum": ["en", "hi", "gu"]
                }
            },
            "required": ["language"]
        }
    },
    {
        "name": "remove_from_cart",
        "description": "Remove items from cart",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "product_name": {
                    "type": "STRING",
                    "description": "Product name to remove"
                },
                "quantity": {
                    "type": "INTEGER",
                    "description": "Quantity to remove"
                },
                "language": {
                    "type": "STRING",
                    "description": "Language code: en, hi, or gu",
                    "enum": ["en", "hi", "gu"]
                }
            },
            "required": ["product_name", "language"]
        }
    },
    {
        "name": "place_order",
        "description": "Place order with customer info",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "customer_name": {
                    "type": "STRING",
                    "description": "Customer name"
                },
                "customer_phone": {
                    "type": "STRING",
                    "description": "Phone number"
                },
                "customer_address": {
                    "type": "STRING",
                    "description": "Delivery address"
                },
                "language": {
                    "type": "STRING",
                    "description": "Language code: en, hi, or gu",
                    "enum": ["en", "hi", "gu"]
                }
            },
            "required": ["customer_name", "customer_phone", "customer_address", "language"]
        }
    }
]