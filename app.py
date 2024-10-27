from flask import Flask, request 
from twilio.twiml.messaging_response import MessagingResponse
from pymongo import MongoClient
import requests
from dotenv import load_dotenv
import os 
import urllib.parse
import datetime

load_dotenv()

app = Flask(__name__)

# MongoDB Setup
username = urllib.parse.quote_plus("admin")
password = urllib.parse.quote_plus("your_mongodb_password")
MONGODB_URI = f"mongodb+srv://{username}:{password}@bot.csjsb.mongodb.net/?retryWrites=true&w=majority&appName=bot"

client = MongoClient(MONGODB_URI)
db = client['healthcare_bot']
users_collection = db['users']
chats_collection = db['chats']

def is_healthcare_related(message):
    """Check if the query is healthcare related"""
    healthcare_keywords = [
        'health', 'medical', 'doctor', 'hospital', 'disease', 'symptom', 'pain',
        'medicine', 'treatment', 'diagnosis', 'clinic', 'patient', 'nurse',
        'therapy', 'surgery', 'prescription', 'infection', 'vaccine', 'blood',
        'emergency', 'pharmacy', 'dental', 'cancer', 'diabetes', 'heart'
    ]
    return any(keyword in message.lower() for keyword in healthcare_keywords)

def save_user(phone_number, data):
    """Save user data to MongoDB"""
    try:
        users_collection.update_one(
            {'phone_number': phone_number},
            {'$set': data},
            upsert=True
        )
    except Exception as e:
        print(f"Database error: {e}")

def get_user(phone_number):
    """Get user data from MongoDB"""
    return users_collection.find_one({'phone_number': phone_number})

def save_chat(phone_number, message, response):
    """Save chat history"""
    try:
        chats_collection.insert_one({
            'phone_number': phone_number,
            'message': message,
            'response': response,
            'timestamp': datetime.datetime.utcnow()
        })
    except Exception as e:
        print(f"Chat save error: {e}")

def get_chat_history(phone_number):
    """Get user's chat history"""
    try:
        chats = chats_collection.find(
            {'phone_number': phone_number}
        ).sort('timestamp', -1).limit(5)
        return list(chats)
    except Exception as e:
        print(f"Chat retrieval error: {e}")
        return []

def generate_response(message, phone_number, user_data=None):
    """Generate AI response"""
    if not is_healthcare_related(message):
        return "I apologize, but I can only assist with healthcare-related questions. Please ask something related to health or medical topics."

    try:
        chat_history = get_chat_history(phone_number)
        context = ""
        
        if user_data:
            context += f"User Profile:\nName: {user_data.get('name')}\n"
            context += f"Age: {user_data.get('age')}\n"
            context += f"Medical History: {user_data.get('medical_history', 'None')}\n\n"
        
        if chat_history:
            context += "Recent conversations:\n"
            for chat in chat_history:
                context += f"Q: {chat['message']}\nA: {chat['response']}\n"

        headers = {
            "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {
                    "role": "system",
                    "content": f"You are a healthcare assistant. Use this context: {context}"
                },
                {
                    "role": "user",
                    "content": message
                }
            ]
        }
        
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            ai_response = response.json()['choices'][0]['message']['content']
            save_chat(phone_number, message, ai_response)
            return ai_response
        return "I apologize, but I couldn't process your request."
    
    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}"

def handle_onboarding(phone_number, message):
    """Handle user onboarding process"""
    user = get_user(phone_number)
    
    if not user:
        # New user, start onboarding
        save_user(phone_number, {
            'phone_number': phone_number,
            'state': 'welcome',
            'created_at': datetime.datetime.utcnow()
        })
        return "Welcome to SolveMyHealth! Do you have an existing account? (Yes/No)"
    
    state = user.get('state', 'welcome')
    
    if state == 'welcome':
        if message.lower() == 'yes':
            # Existing user
            chat_history = get_chat_history(phone_number)
            if chat_history:
                user['state'] = 'chat'
                save_user(phone_number, user)
                return "Welcome back! I found your previous conversations. How can I help you today?"
            return "I couldn't find your chat history. Let's create a new profile. What's your name?"
        
        elif message.lower() == 'no':
            user['state'] = 'get_name'
            save_user(phone_number, user)
            return "Let's create your profile. What's your name?"
    
    elif state == 'get_name':
        user['name'] = message
        user['state'] = 'get_age'
        save_user(phone_number, user)
        return f"Nice to meet you, {message}! What's your age?"
    
    elif state == 'get_age':
        try:
            age = int(message)
            user['age'] = age
            user['state'] = 'get_medical_history'
            save_user(phone_number, user)
            return "Do you have any medical conditions or ongoing treatments? Please describe briefly."
        except ValueError:
            return "Please enter a valid age (numbers only)"
    
    elif state == 'get_medical_history':
        user['medical_history'] = message
        user['state'] = 'chat'
        save_user(phone_number, user)
        return "Thank you! Your profile is complete. How can I assist you with your health-related questions?"
    
    elif state == 'chat':
        return generate_response(message, phone_number, user)
    
    return "I'm not sure how to proceed. Let's start over. Do you have an account? (Yes/No)"

@app.route('/', methods=['GET', 'POST'])
def whatsapp():
    if request.method == 'POST':
        incoming_msg = request.values.get('Body', '').strip()
        sender = request.values.get('From', '').strip()
        
        resp = MessagingResponse()
        msg = resp.message()
        response = handle_onboarding(sender, incoming_msg)
        msg.body(response)
        
        return str(resp)
    return "WhatsApp Webhook is running!"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)