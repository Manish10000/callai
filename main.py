import os
import json
import uvicorn
import google.generativeai as genai
from fastapi import FastAPI, Request
from fastapi.responses import Response
from dotenv import load_dotenv
import re

# ---------------- Load environment variables ----------------
load_dotenv()

PORT = int(os.getenv("PORT", "8080"))
DOMAIN = os.getenv("NGROK_URL")
if not DOMAIN:
    raise ValueError("NGROK_URL environment variable not set.")

# ---------------- Greeting ----------------
WELCOME_GREETING = "नमस्ते! Hi! Hello! मैं एक वॉइस असिस्टेंट हूँ जो Twilio और Google Gemini से चलता है। आप मुझसे हिंदी, अंग्रेज़ी या गुजराती में बात कर सकते हैं।"

# ---------------- System Prompt ----------------
SYSTEM_PROMPT = """You are a helpful and friendly multilingual voice assistant. This conversation is happening over a phone call, so your responses will be spoken aloud. You must support Hindi, English, and Gujarati naturally, depending on what the user speaks.

IMPORTANT: For Gujarati responses, write the Gujarati words using Hindi script (Devanagari) but keep the Gujarati pronunciation and vocabulary. This is because the text-to-speech system can read Hindi script but not Gujarati script.

Rules:
1. First, detect the language of the user's query from: Hindi, English, or Gujarati
2. Respond in the same language as the user's query
3. For Gujarati content, use Hindi script but keep Gujarati words and pronunciation
4. Always keep sentences short, clear, and natural for spoken conversation
5. Spell out numbers in words (e.g., 'एक हज़ार दो सौ' instead of 1200)
6. Do not use any special characters like *, •, or emojis
7. Keep the conversation friendly and natural

Response format:
<language>language_code</language>
<response>Your response here</response>

Example for Gujarati (using Hindi script):
User: "Kem cho?"
Response: "<language>gu</language><response>हूं मजामां छूं! आभार! तमारो दिवस कैवो चाली रहयो छे?</response>"

Example for Hindi:
User: "Aap kaise ho?"
Response: "<language>hi</language><response>मैं ठीक हूँ, धन्यवाद! आपका दिन कैसा चल रहा है?</response>"

Example for English:
User: "How are you?"
Response: "<language>en</language><response>I'm doing well, thank you! How can I help you today?</response>"
"""

# ---------------- Gemini API ----------------
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set.")

genai.configure(api_key=GOOGLE_API_KEY)

model = genai.GenerativeModel(
    model_name='gemini-2.0-flash-exp',
    system_instruction=SYSTEM_PROMPT
)

# Store active chat sessions
sessions = {}

# Language mapping with appropriate voices - Using Hindi voice for Gujarati
LANGUAGE_MAP = {
    "hi": {"code": "hi-IN", "voice": "Polly.Aditi"},  # Hindi - supported
    "gu": {"code": "hi-IN", "voice": "Polly.Aditi"},  # Gujarati - use Hindi voice with Hindi script
    "en": {"code": "en-IN", "voice": "Polly.Aditi"},  # English (India) - supported
    "default": {"code": "en-IN", "voice": "Polly.Aditi"}  # Default to English
}

# Language prompts for gathering more input
LANGUAGE_PROMPTS = {
    "hi-IN": "और कुछ पूछना चाहते हैं?",
    "gu-IN": "वधु कंयक पूछवुं छे?",  # Gujarati in Hindi script: "વધુ કંઈક પૂછવું છે?"
    "en-IN": "Would you like to ask anything else?"
}

# Goodbye messages in different languages
GOODBYE_MESSAGES = {
    "hi-IN": "धन्यवाद! अलविदा!",
    "gu-IN": "आभार! आवजो!",  # Gujarati in Hindi script: "આભાર! આવજો!"
    "en-IN": "Thank you! Goodbye!"
}

# ---------------- FastAPI app ----------------
app = FastAPI()

async def gemini_response_with_language(chat_session, user_prompt):
    """Get a response from Gemini API with language detection"""
    response = await chat_session.send_message_async(user_prompt)
    response_text = response.text
    
    print(f"Gemini raw response: {response_text}")
    
    # Parse the response to extract language and content
    language_match = re.search(r'<language>(.*?)</language>', response_text, re.IGNORECASE)
    response_match = re.search(r'<response>(.*?)</response>', response_text, re.IGNORECASE)
    
    if language_match and response_match:
        detected_language = language_match.group(1).strip().lower()
        response_content = response_match.group(1).strip()
        return detected_language, response_content
    else:
        # Fallback: if parsing fails, return English response
        print("Failed to parse Gemini response, using English as default")
        return "en", response_text

@app.post("/twiml")
async def twiml_endpoint():
    """Default TwiML endpoint"""
    xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" language="en-IN" action="https://{DOMAIN}/handle-speech" speechTimeout="auto" enhanced="true">
        <Say voice="Polly.Aditi">{WELCOME_GREETING}</Say>
    </Gather>
    <Say voice="Polly.Aditi">मुझे आपकी आवाज़ सुनाई नहीं दी। कृपया दोबारा कॉल करें।</Say>
</Response>"""
    
    return Response(content=xml_response, media_type="text/xml")

@app.post("/handle-speech")
async def handle_speech(request: Request):
    """Handle speech input from Twilio's Gather with language detection"""
    form_data = await request.form()
    speech_result = form_data.get("SpeechResult", "")
    call_sid = form_data.get("CallSid", "")
    
    print(f"Received speech from {call_sid}: {speech_result}")
    
    # Initialize chat session if not exists
    if call_sid not in sessions:
        sessions[call_sid] = model.start_chat(history=[])
    
    # Get response from Gemini with language detection
    chat_session = sessions[call_sid]
    detected_language, response_text = await gemini_response_with_language(chat_session, speech_result)
    
    # Map to Twilio language code and voice - Using Hindi voice for Gujarati
    language_info = LANGUAGE_MAP.get(detected_language, LANGUAGE_MAP["default"])
    detected_language_code = language_info["code"]
    voice = language_info["voice"]
    
    print(f"Gemini detected language: {detected_language} -> Twilio: {detected_language_code}, Voice: {voice}")
    print(f"Response text to be spoken: {response_text}")
    
    # Get appropriate prompts for the detected language
    gather_prompt = LANGUAGE_PROMPTS.get(detected_language_code, LANGUAGE_PROMPTS["en-IN"])
    goodbye_message = GOODBYE_MESSAGES.get(detected_language_code, GOODBYE_MESSAGES["en-IN"])
    
    # Return TwiML with dynamic language switching
    xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{voice}">{response_text}</Say>
    <Gather input="speech" language="{detected_language_code}" action="https://{DOMAIN}/handle-speech" speechTimeout="auto" enhanced="true">
        <Say voice="{voice}">{gather_prompt}</Say>
    </Gather>
    <Say voice="{voice}">{goodbye_message}</Say>
    <Hangup/>
</Response>"""
    
    print(f"Using language: {detected_language_code} with voice: {voice} for call {call_sid}")
    
    return Response(content=xml_response, media_type="text/xml")

@app.get("/")
async def root():
    return {"message": "Multilingual Voice Assistant API"}

if __name__ == "__main__":
    print(f"Starting server on port {PORT}")
    print("Available endpoints:")
    print(f"  - Main endpoint: {DOMAIN}/twiml")
    print(f"  - Speech handler: {DOMAIN}/handle-speech")
    print("Language detection enabled using Gemini AI")
    print("Note: Gujarati content is written in Hindi script for TTS compatibility")
    uvicorn.run(app, host="0.0.0.0", port=PORT)