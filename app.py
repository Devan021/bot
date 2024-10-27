from flask import Flask, request 
from twilio.twiml.messaging_response import MessagingResponse
from pymongo import MongoClient
import requests
from dotenv import load_dotenv
import os 

load_dotenv()

app = Flask(__name__)

# MongoDB Setup
MONGODB_URI = "mongodb+srv://admin:admin123@@bot.csjsb.mongodb.net/?retryWrites=true&w=majority&appName=bot"
client = MongoClient(MONGODB_URI)
db = client['healthcare_bot']
users_collection = db['users']
chats_collection = db['chats']

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
    """Retrieve user data from MongoDB"""
    try:
        return users_collection.find_one({'phone_number': phone_number})
    except Exception as e:
        print(f"Database error: {e}")
        return None

def save_chat(phone_number, message, response):
    """Save chat history to MongoDB"""
    try:
        chats_collection.insert_one({
            'phone_number': phone_number,
            'message': message,
            'response': response,
            'timestamp': datetime.datetime.utcnow()
        })
    except Exception as e:
        print(f"Chat save error: {e}")

def get_chat_history(phone_number, limit=5):
    """Get recent chat history"""
    try:
        chats = chats_collection.find(
            {'phone_number': phone_number}
        ).sort('timestamp', -1).limit(limit)
        return list(chats)
    except Exception as e:
        print(f"Chat retrieval error: {e}")
        return []

def check_medication_interactions(medications):
    """Check for medication interactions"""
    interactions = []
    medication_db = {
        'metformin': ['iodinated contrast'],
        'lisinopril': ['potassium supplements'],
        'aspirin': ['warfarin', 'heparin'],
        'ibuprofen': ['aspirin', 'warfarin']
    }
    
    for med1 in medications:
        med1 = med1.lower()
        if med1 in medication_db:
            for med2 in medications:
                med2 = med2.lower()
                if med2 in medication_db[med1]:
                    interactions.append(f"⚠️ WARNING: {med1} may interact with {med2}")
    return interactions

def generate_response(message, phone_number):
    """Generate response using Perplexity AI"""
    try:
        user = get_user(phone_number)
        chat_history = get_chat_history(phone_number)
        
        # Create context from user data and chat history
        context = ""
        if user:
            context += f"User conditions: {', '.join(user.get('conditions', []))}\n"
            context += f"Current medications: {', '.join(user.get('medications', []))}\n"
        
        if chat_history:
            context += "\nRecent chat history:\n"
            for chat in chat_history:
                context += f"User: {chat['message']}\nBot: {chat['response']}\n"
        
        headers = {
            "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}",
            "Content-Type": "application/json"
        }
        
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
            
            # Check for medication interactions
            if user and user.get('medications'):
                interactions = check_medication_interactions(user['medications'])
                if interactions:
                    ai_response += "\n\n" + "\n".join(interactions)
            
            # Save chat to history
            save_chat(phone_number, message, ai_response)
            return ai_response
            
        return "I apologize, but I couldn't process your request."
            
    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}"

def handle_onboarding(phone_number, message):
    """Handle user onboarding and profile management"""
    user = get_user(phone_number)
    
    if not user:
        user = {
            'phone_number': phone_number,
            'state': 'initial',
            'conditions': [],
            'medications': []
        }
        save_user(phone_number, user)
        return "Welcome to SolveMyHealth! Do you have any medical conditions? (Yes/No)"
    
    if user['state'] == 'initial':
        if message.lower() == 'yes':
            user['state'] = 'get_conditions'
            save_user(phone_number, user)
            return "Please list your medical conditions (separate by comma)"
        elif message.lower() == 'no':
            user['state'] = 'get_medications'
            save_user(phone_number, user)
            return "Do you take any medications? (Yes/No)"
    
    elif user['state'] == 'get_conditions':
        conditions = [c.strip() for c in message.split(',')]
        user['conditions'] = conditions
        user['state'] = 'get_medications'
        save_user(phone_number, user)
        return "What medications are you currently taking? (separate by comma, or type 'none')"
    
    elif user['state'] == 'get_medications':
        if message.lower() != 'none':
            medications = [m.strip() for m in message.split(',')]
            user['medications'] = medications
            interactions = check_medication_interactions(medications)
            interaction_warning = "\n".join(interactions) if interactions else ""
            
        user['state'] = 'chat'
        save_user(phone_number, user)
        
        response = "Profile complete! You can now ask me health-related questions."
        if interaction_warning:
            response += f"\n\nMedication Warnings:\n{interaction_warning}"
        return response
    
    return generate_response(message, phone_number)

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

@app.route('/test-db', methods=['GET'])
def test_db():
    try:
        client.list_database_names()
        return "Database connection successful!"
    except Exception as e:
        return f"Database connection failed: {str(e)}"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)