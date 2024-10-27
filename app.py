from flask import Flask, request 
from twilio.twiml.messaging_response import MessagingResponse
from pymongo import MongoClient
import requests
from dotenv import load_dotenv
import os 
import urllib.parse
import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)

# MongoDB Setup with proper URL encoding
try:
    # Get MongoDB credentials
    username = urllib.parse.quote_plus("admin")
    password = urllib.parse.quote_plus("admin123@")
    
    # Construct MongoDB URI with encoded credentials
    mongodb_uri = f"mongodb+srv://{username}:{password}@bot.csjsb.mongodb.net/?retryWrites=true&w=majority&appName=bot"
    
    # Initialize MongoDB client with timeout settings
    client = MongoClient(
        mongodb_uri,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=10000
    )
    
    # Test connection
    client.admin.command('ping')
    logger.info("MongoDB connection successful!")
    
    # Initialize database and collections
    db = client['healthcare_bot']
    users_collection = db['users']
    chats_collection = db['chats']
    
except Exception as e:
    logger.error(f"MongoDB connection error: {e}")
    raise

def get_user(phone_number):
    """Get user data from MongoDB"""
    try:
        user = users_collection.find_one({'phone_number': phone_number})
        logger.debug(f"Retrieved user: {phone_number}")
        return user
    except Exception as e:
        logger.error(f"Database error getting user: {e}")
        return None

def save_user(phone_number, data):
    """Save user data to MongoDB"""
    try:
        result = users_collection.update_one(
            {'phone_number': phone_number},
            {'$set': data},
            upsert=True
        )
        logger.debug(f"User saved: {phone_number}")
        return result
    except Exception as e:
        logger.error(f"Database error saving user: {e}")
        return None

def save_chat(phone_number, message, response):
    """Save chat history"""
    try:
        result = chats_collection.insert_one({
            'phone_number': phone_number,
            'message': message,
            'response': response,
            'timestamp': datetime.datetime.utcnow()
        })
        logger.debug(f"Chat saved for user: {phone_number}")
        return result
    except Exception as e:
        logger.error(f"Chat save error: {e}")
        return None

def get_chat_history(phone_number):
    """Get user's chat history"""
    try:
        chats = list(chats_collection.find(
            {'phone_number': phone_number}
        ).sort('timestamp', -1).limit(5))
        logger.debug(f"Retrieved chat history for user: {phone_number}")
        return chats
    except Exception as e:
        logger.error(f"Chat retrieval error: {e}")
        return []

def generate_response(message, user_data):
    """Generate AI response"""
    try:
        headers = {
            "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}",
            "Content-Type": "application/json"
        }
        
        # Get user context
        context = f"User Profile:\nName: {user_data.get('name')}\n"
        context += f"Age: {user_data.get('age')}\n"
        context += f"Medical History: {user_data.get('medical_history', 'None')}\n"
        
        data = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {
                    "role": "system",
                    "content": f"You are a healthcare assistant. Context: {context}"
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
            save_chat(user_data['phone_number'], message, ai_response)
            return ai_response
        return "I apologize, but I couldn't process your request."
            
    except Exception as e:
        logger.error(f"Response generation error: {e}")
        return "Sorry, I encountered an error generating a response."

def handle_user_state(phone_number, message, user):
    """Handle user based on their current state"""
    try:
        state = user.get('state', 'welcome')
        
        if state == 'welcome':
            user['state'] = 'get_name'
            save_user(phone_number, user)
            return "What's your name?"
            
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
            return generate_response(message, user)
            
        return "I'm not sure how to proceed. Let's start over."
        
    except Exception as e:
        logger.error(f"State handling error: {e}")
        return "Sorry, there was an error. Please try again."

@app.route('/', methods=['GET', 'POST'])
def whatsapp():
    if request.method == 'POST':
        try:
            incoming_msg = request.values.get('Body', '').strip()
            sender = request.values.get('From', '')
            
            if not sender or not incoming_msg:
                return "Invalid request parameters", 400
            
            # Clean phone number
            sender = sender.replace('whatsapp:', '')
            
            # Check if user exists
            user = get_user(sender)
            
            resp = MessagingResponse()
            msg = resp.message()
            
            if not user:
                # New user
                user_data = {
                    'phone_number': sender,
                    'state': 'welcome',
                    'created_at': datetime.datetime.utcnow()
                }
                save_user(sender, user_data)
                response = "Welcome to SolveMyHealth! Let's create your profile. What's your name?"
            else:
                # Existing user - handle their current state
                response = handle_user_state(sender, incoming_msg, user)
            
            msg.body(response)
            return str(resp)
            
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return "Internal server error", 500
            
    return "WhatsApp Webhook is running!"

@app.route('/status', methods=['POST'])
def status_callback():
    """Handle message status callbacks"""
    try:
        message_sid = request.values.get('MessageSid')
        message_status = request.values.get('MessageStatus')
        logger.info(f"Message {message_sid} status: {message_status}")
        return '', 200
    except Exception as e:
        logger.error(f"Status callback error: {e}")
        return str(e), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)