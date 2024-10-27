from flask import Flask, request 
from twilio.twiml.messaging_response import MessagingResponse
from pymongo import MongoClient
import requests
from dotenv import load_dotenv
import os 
import urllib.parse
import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)

# MongoDB Setup with proper error handling
try:
    # Get MongoDB credentials from environment variables
    MONGODB_USERNAME = os.getenv('MONGODB_USERNAME', 'admin')
    MONGODB_PASSWORD = os.getenv('MONGODB_PASSWORD', 'admin123@')
    
    # URL encode the credentials
    username = urllib.parse.quote_plus(MONGODB_USERNAME)
    password = urllib.parse.quote_plus(MONGODB_PASSWORD)
    
    MONGODB_URI = f"mongodb+srv://{username}:{password}@bot.csjsb.mongodb.net/?retryWrites=true&w=majority&appName=bot"
    
    client = MongoClient(MONGODB_URI)
    # Test connection
    client.admin.command('ping')
    logger.info("MongoDB connection successful!")
    
    db = client['healthcare_bot']
    users_collection = db['users']
    chats_collection = db['chats']
    
except Exception as e:
    logger.error(f"MongoDB connection error: {e}")
    raise

def save_user(phone_number, data):
    """Save user data to MongoDB with error handling"""
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

def get_user(phone_number):
    """Get user data from MongoDB with error handling"""
    try:
        user = users_collection.find_one({'phone_number': phone_number})
        logger.debug(f"Retrieved user: {phone_number}")
        return user
    except Exception as e:
        logger.error(f"Database error getting user: {e}")
        return None

def save_chat(phone_number, message, response):
    """Save chat history with error handling"""
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
    """Get user's chat history with error handling"""
    try:
        chats = list(chats_collection.find(
            {'phone_number': phone_number}
        ).sort('timestamp', -1).limit(5))
        logger.debug(f"Retrieved chat history for user: {phone_number}")
        return chats
    except Exception as e:
        logger.error(f"Chat retrieval error: {e}")
        return []

def handle_new_user(phone_number):
    """Handle new user creation"""
    try:
        user_data = {
            'phone_number': phone_number,
            'state': 'welcome',
            'created_at': datetime.datetime.utcnow()
        }
        save_user(phone_number, user_data)
        return "Welcome to SolveMyHealth! Do you have an existing account? (Yes/No)"
    except Exception as e:
        logger.error(f"New user creation error: {e}")
        return "Sorry, there was an error. Please try again."

@app.route('/', methods=['GET', 'POST'])
def whatsapp():
    if request.method == 'POST':
        try:
            # Get message details
            incoming_msg = request.values.get('Body', '').strip()
            sender = request.values.get('From', '').strip()
            
            if not sender or not incoming_msg:
                return "Invalid request parameters", 400
            
            # Clean phone number format
            sender = sender.replace('whatsapp:', '')
            
            # Check if user exists
            user = get_user(sender)
            
            resp = MessagingResponse()
            msg = resp.message()
            
            if not user:
                # New user
                response = handle_new_user(sender)
            else:
                # Existing user
                response = handle_onboarding(sender, incoming_msg)
            
            msg.body(response)
            return str(resp)
            
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return "Internal server error", 500
            
    return "WhatsApp Webhook is running!"

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Check MongoDB connection
        client.admin.command('ping')
        return {
            "status": "healthy",
            "mongodb": "connected"
        }, 200
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }, 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)