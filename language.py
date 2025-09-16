# language.py
LANG = {
    "welcome": {
        "en": "Welcome to GroceryBabu! I'm Aditi, your personal shopping assistant.",
        "hi": "GroceryBabu में आपका स्वागत है! मैं आदिति, आपकी व्यक्तिगत खरीदारी सहायक हूँ।",
        "gu": "ग्रोसरीबाबु मा तमारु स्वागत छे! हूं आदिति, तमारी व्यक्तिगत खरीदारी सहायक छूं।"
    },
    "item_added": {
        "en": "{qty} {item} added to cart.",
        "hi": "{qty} {item} कार्ट में जोड़ा गया।",
        "gu": "{qty} {item} कार्ट मा उमेरवामा आव्यू छे।"
    },
    "item_removed": {
        "en": "{qty} {item} removed from cart.",
        "hi": "{qty} {item} कार्ट से हटाया गया।",
        "gu": "{qty} {item} कार्ट मांथी काढवामा आव्यू छे।"
    },
    "cart_empty": {
        "en": "Your cart is empty.",
        "hi": "आपका कार्ट खाली है।",
        "gu": "तमारु कार्ट खाली छे।"
    },
    "cart_summary": {
        "en": "Your cart has {count} items. Total: ${total}",
        "hi": "आपके कार्ट में {count} आइटम हैं। कुल: ${total}",
        "gu": "तमारा कार्ट मा {count} आइटम छे। कुल: ${total}"
    },
    "order_placed": {
        "en": "Order placed successfully! Order ID: {order_id}",
        "hi": "आर्डर सफलतापूर्वक दिया गया! आर्डर आईडी: {order_id}",
        "gu": "आर्डर सफळतापूर्वक आपवामा आव्यू! आर्डर आईडी: {order_id}"
    },
    "product_found": {
        "en": "Found {count} products: {items}",
        "hi": "{count} उत्पाद मिले: {items}",
        "gu": "{count} उत्पाद मिल्या: {items}"
    },
    "no_products": {
        "en": "No products found matching '{query}'.",
        "hi": "'{query}' से मेल खाता कोई उत्पाद नहीं मिला।",
        "gu": "'{query}' सांगतां उत्पाद नहीं मिल्यू।"
    },
    "ask_quantity": {
        "en": "How many {item} would you like?",
        "hi": "आपको कितने {item} चाहिए?",
        "gu": "तमने कितला {item} जोइए छे?"
    },
    "ask_name": {
        "en": "What's your name?",
        "hi": "आपका नाम क्या है?",
        "gu": "तमारु नां शुं छे?"
    },
    "ask_phone": {
        "en": "What's your phone number?",
        "hi": "आपका फोन नंबर क्या है?",
        "gu": "तमारो फोन नंबर शुं छे?"
    },
    "ask_address": {
        "en": "What's your delivery address?",
        "hi": "आपका डिलीवरी पता क्या है?",
        "gu": "तमारो डिलीवरी पत्तो शुं छे?"
    },
    "processing": {
        "en": "One moment please...",
        "hi": "कृपया एक क्षण प्रतीक्षा करें...",
        "gu": "कृपा करीने एक क्षण राह जोईये..."

    },
    "goodbye": {
        "en": "Thank you for shopping with GroceryBabu! Have a great day!",
        "hi": "GroceryBabu के साथ खरीदारी करने के लिए धन्यवाद! आपका दिन शुभ हो!",
        "gu": "ग्रोसरीबाबु साथे खरीदि करवा बदल आभार! तमारो दिवस शुभ हो!"
    },
    "processing_error": {
        "en": "Sorry, I encountered an error processing your request.",
        "hi": "क्षमा करें, आपके अनुरोध को प्रोसेस करने में मुझे त्रुटि आई।",
        "gu": "माफ करशो, तमारि विनंति पर काम करतां वक्ते मने भूल आवी."
    },
    "no_inventory": {
        "en": "I don't have any items in stock right now.",
        "hi": "मेरे पास अभी कोई आइटम स्टॉक में नहीं है।",
       "gu": "मारी पासे अत्यारे कोई आइटम स्टॉकमा नथी."
    },
    "available_categories": {
        "en": "Available categories: ",
        "hi": "उपलब्ध श्रेणियां: ",
        "gu": "उपलब्ध केटेगरीओ: "
    },
    "which_category": {
        "en": "Which category interests you?",
        "hi": "कौन सी श्रेणी आपको दिलचस्प लगती है?",
        "gu": "कई केटेगरी तमे रस पडे छे?"
    },
    "which_one": {
        "en": "Which one would you like?",
        "hi": "आप कौन सा चाहेंगे?",
         "gu": "तमे कयूं जोईशो?"
    },
    "which_interests": {
        "en": "Which one interests you?",
        "hi": "कौन सा आपको दिलचस्प लगता है?",
        "gu": "कयू तमे रસ પડે છે?"
    },
    "add_failed": {
        "en": "Sorry, I couldn't add that item to your cart.",
        "hi": "क्षमा करें, मैं उस आइटम को आपके कार्ट में नहीं जोड़ सका।",
        "gu": "माफ करशो, हुं ते आइटमने तमारां कार्टमा उमेरि शक्यो नथी."
    },
    "remove_failed": {
        "en": "Sorry, I couldn't remove that item from your cart.",
        "hi": "क्षमा करें, मैं उस आइटम को आपके कार्ट से नहीं हटा सका।",
        "gu": "माफ करशो, हुं ते आइटमने तमारां कार्टमांथी काढि शक्यो नथी."
    },
    "suggest_item": {
        "en": " Would you also like {item}?",
        "hi": " क्या आप {item} भी चाहेंगे?",
        "gu": " शुं तमे {item} पण जोईशो?"
    },
    "order_check_cart": {
        "en": "I understand you want to place an order. Let me check your cart first.",
        "hi": "मैं समझ गया कि आप ऑर्डर देना चाहते हैं। पहले मैं आपका कार्ट चेक करता हूं।",
         "gu": "हूँ समझी गयो के तमे ऑर्डर आपवा मागो छो. पहला हूँ तमारु कार्ट चेक करू छू."
    },
    "proceed_order": {
        "en": "Would you like to proceed with the order?",
        "hi": "क्या आप ऑर्डर के साथ आगे बढ़ना चाहेंगे?",
        "gu": "शुं तमे ऑर्डर साथे आगळ वाढवा मागो छो?"
    },
    "cart_empty_browse": {
        "en": "Your cart is empty. Would you like to browse some products first?",
        "hi": "आपका कार्ट खाली है। क्या आप पहले कुछ उत्पाद देखना चाहेंगे?",
        "gu": "तमारु कार्ट खाली छे. शुं तमे पहला किटला उत्पाद जोवा मागो छो?"
    },
    "products_available": {
        "en": "I found these products for you. What would you like to add to your cart?",
        "hi": "मैंने आपके लिए ये उत्पाद पाए हैं। आप अपने कार्ट में क्या जोड़ना चाहेंगे?",
         "gu": "में तमारा माटे आ उत्पादो शोध्या छे. तमे तमारा कार्टमा शुं उमेरवा मागो छो?"
    },
    "unclear_request": {
        "en": "I didn't understand that clearly. Could you please repeat?",
        "hi": "मैं इसे स्पष्ट रूप से नहीं समझ पाया। क्या आप कृपया दोहरा सकते हैं?",
       "gu": "हूँ ते स्पष्टपणे समझी शक्यो नथी. शुं तमे कृपया पुनरावर्तन करी शको?"
    }
}