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
        "એક ક્ષણ રાહ જુઓ, હું તમારી વિનંતી પર કામ કરી રહ્યો છું અને વિગતો તપાસી રહ્યો છું...",
        "મને તમારા માટે તે જોવા દો, આમાં થોડો સમય લાગશે...",
        "કૃપા કરીને એક ક્ષણ રાહ જુઓ, હું તમારા માટે માહિતી લાવી રહ્યો છું...",
        "હું અત્યારે તમારા માટે આ પર કામ કરી રહ્યો છું, આ જલ્દી તૈયાર થઈ જશે...",
        "મને અમારી ઇન્વેન્ટરી તપાસવા દો અને તમારા માટે ઉપલબ્ધતાની પુષ્ટિ કરું...",
        "હું અત્યારે તમારા માટે આ માહિતી એકત્રિત કરી રહ્યો છું, થોડી રાહ જુઓ...",
        "કૃપા કરીને રાહ જુઓ જ્યારે હું તમારી વિનંતી પર કામ કરું અને વિગતો ચકાસું...",
        "બસ એક સેકન્ડ, હું તમારા માટે વસ્તુઓ ગોઠવી રહ્યો છું...",
        "હું તમારી આ વિનંતીનું ધ્યાન રાખી રહ્યો છું, વધુ સમય નહીં લાગે...",
        "હું અત્યારે આને સંભાળી રહ્યો છું અને જલ્દી તમને અપડેટ આપીશ..."
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
        "બરાબર, મેં તે વિનંતી પૂર્ણ કરી છે અને અહીં વિગતો છે...",
        "ખૂબ સરસ! મેં તમારી વિનંતી પર કામ પૂર્ણ કર્યું છે અને પરિણામો મળ્યા છે...",
        "પરફેક્ટ, મેં તમારા માટે તેને સંભાળ્યું છે અને અહીં છે જે મને મળ્યું...",
        "બરાબર, મેં તેનું ધ્યાન રાખ્યું છે અને અહીં પરિણામ છે...",
        "થઈ ગયું, મેં તેને પૂર્ણ કર્યું છે અને અહીં માહિતી છે...",
        "ઉત્તમ, મેં તમારી વિનંતી પૂર્ણ કરી છે અને અહીં વિગતો છે...",
        "શાનદાર, મેં તમારા માટે તેને પૂર્ણ કર્યું છે અને અહીં છે જે મળ્યું...",
        "બધું તૈયાર! મેં બધું સંભાળ્યું છે અને અહીં પરિણામો છે...",
        "થઈ ગયું! મેં તમારા માટે તેને પ્રોસેસ કર્યું છે અને અહીં અપડેટ છે...",
        "અહીં છે, મેં તેને પૂર્ણ કર્યું છે અને અહીં છે જે મળ્યું..."
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
