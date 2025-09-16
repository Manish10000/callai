import random

# Multilingual filler sentences
PROCESSING_PHRASES = {
    "en": [
        "Just a moment, I'm processing your request and checking the details...",
        "Let me look that up for you, this will only take a short while...",
        "One moment please, I'm pulling up the information you need...",
        "I'm working on that for you now, this should be ready shortly...",
        "Let me check our inventory and confirm the availability for you...",
        "I'm gathering that information for you right now, hang tight...",
        "Please hold on while I process your request and verify the details...",
        "Just a second, I'm putting things together for you...",
        "Let me take care of that request for you, it won't be long...",
        "I'm handling that now and should have an update for you soon..."
    ],
    "hi": [
        "एक क्षण रुकिए, मैं आपके अनुरोध को प्रोसेस कर रहा हूं और विवरण चेक कर रहा हूं...",
        "मैं आपके लिए इसे देख रहा हूं, इसमें थोड़ा समय लगेगा...",
        "कृपया एक क्षण प्रतीक्षा करें, मैं आपके लिए जानकारी निकाल रहा हूं...",
        "मैं अभी आपके लिए इस पर काम कर रहा हूं, यह जल्दी तैयार हो जाएगा...",
        "मुझे हमारी इन्वेंटरी चेक करने दें और आपके लिए उपलब्धता की पुष्टि करूं...",
        "मैं अभी आपके लिए यह जानकारी इकट्ठा कर रहा हूं, थोड़ा इंतजार करें...",
        "कृपया रुकें जब तक मैं आपके अनुरोध को प्रोसेस करूं और विवरण सत्यापित करूं...",
        "बस एक सेकंड, मैं आपके लिए चीजों को व्यवस्थित कर रहा हूं...",
        "मैं आपके इस अनुरोध का ध्यान रख रहा हूं, ज्यादा समय नहीं लगेगा...",
        "मैं अभी इसे संभाल रहा हूं और जल्द ही आपको अपडेट दूंगा..."
    ],
    "gu": [
    "एक क्षण राह जोओ, हूं तमारी विनंती पर काम करी रहो छुं अने विवरण तपासी रहो छुं...",
    "मने तमारा माटे ते जोवा दो, आमा थोड़ो समय लागशे...",
    "कृपा करिने एक क्षण राह जोओ, हूं तमारा माटे माहिती लावी रहो छुं...",
    "हूं अत्यारे तमारा माटे आ पर काम करी रहो छुं, आ जल्दी तैयार थई जशे...",
    "मने अमारी इन्वेंटरी तपासवा दो अने तमारा माटे उपलबध्तानी पुष्टि करूं...",
    "हूं अत्यारे तमारा माटे आ माहिती एकत्रित करी रहो छुं, थोड़ी राह जोओ...",
    "कृपा करिने राह जोओ जरे हूं तमारी विनंती पर काम करूं अने विवरण चकासूं...",
    "बस एक सेकंड, हूं तमारा माटे वस्तुओं गोटवी रहो छुं...",
    "हूं तमारी आ विनंतीनु ध्यान राखी रहो छुं, वधु समय नहीं लागे...",
    "हूं अत्यारे आने संभाळी रहो छुं अने जल्दी तमने अपडेट आपीश..."
    ]
}

COMPLETION_PHRASES = {
    "en": [
        "Alright, I've completed that request and here are the details...",
        "Great! I've finished processing your request and got the results...",
        "Perfect, I've handled that for you and here's what I found...",
        "Okay, I've taken care of that and here's the outcome...",
        "There we go, I've wrapped that up and here's the information...",
        "Excellent, I've finished your request and here are the details...",
        "Wonderful, I've completed that for you and here's what I've got...",
        "All set! I've taken care of everything and here are the results...",
        "Done! I've processed that for you and here's the update...",
        "There you go, I've completed it and here's what I came up with..."
    ],
    "hi": [
        "ठीक है, मैंने वह अनुरोध पूरा कर लिया है और यहां विवरण हैं...",
        "बहुत बढ़िया! मैंने आपके अनुरोध को प्रोसेस कर लिया है और परिणाम मिल गए हैं...",
        "परफेक्ट, मैंने आपके लिए इसे संभाल लिया है और यहां है जो मुझे मिला...",
        "ठीक है, मैंने इसका ध्यान रख लिया है और यहां परिणाम है...",
        "हो गया, मैंने इसे पूरा कर लिया है और यहां जानकारी है...",
        "बेहतरीन, मैंने आपका अनुरोध पूरा कर लिया है और यहां विवरण हैं...",
        "शानदार, मैंने आपके लिए इसे पूरा कर लिया है और यहां है जो मिला...",
        "सब तैयार! मैंने सब कुछ संभाल लिया है और यहां परिणाम हैं...",
        "हो गया! मैंने आपके लिए इसे प्रोसेस कर लिया है और यहां अपडेट है...",
        "यहां है, मैंने इसे पूरा कर लिया है और यहां है जो मिला..."
    ],
    "gu": [
      "बराबर, मे ते विनंती पूर्ण करी छे अने अही विवरण छे...",
    "खूब सरस! मे तमारी विनंती पर काम पूर्ण कर्यु छे अने परिणामो मल्या छे...",
    "परफेक्ट, मे तमारा माटे तेने संभाळ्यु छे अने अही छे जे मने मल्यु...",
    "बराबर, मे तेनु ध्यान राख्यु छे अने अही परिणाम छे...",
    "थई गयू, मे तेने पूर्ण कर्यु छे अने अही माहिती छे...",
    "उत्तम, मे तमारी विनंती पूर्ण करी छे अने अही विवरण छे...",
    "शानदार, मे तमारा माटे तेने पूर्ण कर्यु छे अने अही छे जे मल्यु...",
    "बधु तैयार! मे बधु संभाळ्यु छे अने अही परिणामो छे...",
    "थई गयू! मे तमारा माटे तेने प्रोसेस कर्यु छे अने अही अपडेट छे...",
    "अही छे, मे तेने पूर्ण कर्यु छे अने अही छे जे मल्यु..."
    ]
}

def get_processing_phrase(lang_code="en"):
    """Get a random processing phrase in the specified language"""
    if lang_code not in PROCESSING_PHRASES:
        lang_code = "en"
    return random.choice(PROCESSING_PHRASES[lang_code])

def get_completion_phrase(lang_code="en"):
    """Get a random completion phrase in the specified language"""
    if lang_code not in COMPLETION_PHRASES:
        lang_code = "en"
    return random.choice(COMPLETION_PHRASES[lang_code])
