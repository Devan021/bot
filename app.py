from flask import Flask, request 
from twilio.twiml.messaging_response import MessagingResponse
from sentence_transformers import SentenceTransformer
import chromadb
import requests
from dotenv import load_dotenv
import os 
import json

load_dotenv()

app = Flask(__name__)

# Initialize E5-base-v2-model
embedding_model = SentenceTransformer('intfloat/e5-base-v2')

# Initialize ChromaDB
chroma_client = chromadb.Client()
collection = chroma_client.create_collection(
    name="healthcare_knowledge",
    metadata={"hnsw:space": "cosine"}
)

# Medical knowledge base
medical_knowledge = [
    # Disease information
    "Diabetes is a chronic disease affecting blood sugar levels. Common medications include metformin, insulin, and sulfonylureas.",
    "Hypertension is high blood pressure that can lead to heart problems. Treatments include ACE inhibitors, beta blockers, and diuretics.",
    "Asthma is a respiratory condition causing breathing difficulty. Common medications include albuterol and corticosteroid inhalers.",
    
    # Medication interactions
    "ACE inhibitors like lisinopril can interact dangerously with potassium supplements.",
    "Beta blockers and calcium channel blockers together may cause excessive blood pressure lowering.",
    "NSAIDs can reduce the effectiveness of many blood pressure medications.",
    
    # Treatment guidelines
    "Diabetes management requires regular blood sugar monitoring and medication adherence.",
    "Hypertension treatment often involves lifestyle changes alongside medication.",
    "Asthma control requires both preventive and rescue medications.",
    
    # Warning signs
    "Seek immediate medical attention for severe chest pain, difficulty breathing, or sudden confusion.",
    "Monitor for signs of low blood sugar when taking diabetes medications.",
    "Watch for persistent cough or shortness of breath with heart medications."
]

# Medication interaction database
medication_interactions = {
    'lisinopril': {
        'conflicts': ['spironolactone', 'potassium supplements'],
        'conditions': ['hypertension', 'heart failure'],
        'warnings': 'May increase potassium levels when combined with potassium-sparing diuretics'
    },
    'metformin': {
        'conflicts': ['iodinated contrast media'],
        'conditions': ['diabetes'],
        'warnings': 'Should be temporarily stopped before radiological studies using contrast'
    },
    'aspirin': {
        'conflicts': ['warfarin', 'heparin'],
        'conditions': ['heart disease', 'pain'],
        'warnings': 'Increases bleeding risk when combined with blood thinners'
    }
}

# Initialize ChromaDB with medical knowledge
embeddings = embedding_model.encode(medical_knowledge)
collection.add(
    embeddings=embeddings.tolist(),
    documents=medical_knowledge,
    ids=[f"doc_{i}" for i in range(len(medical_knowledge))]
)

# User management
users_db = {}
user_sessions = {}

def check_medication_interactions(medications):
    """Check for potential medication interactions"""
    interactions = []
    for med1 in medications:
        if med1.lower() in medication_interactions:
            for med2 in medications:
                if med2.lower() != med1.lower() and med2.lower() in medication_interactions[med1.lower()]['conflicts']:
                    interactions.append(f"⚠️ WARNING: {med1} and {med2} may interact: "
                                     f"{medication_interactions[med1.lower()]['warnings']}")
    return interactions

def get_relevant_context(query, user_data=None):
    """Get relevant medical context using RAG"""
    try:
        query_embedding = embedding_model.encode(query)
        results = collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=2
        )
        
        context = " ".join(results['documents'][0])
        
        if user_data:
            context += f"\nUser conditions: {', '.join(user_data.get('conditions', []))}"
            context += f"\nCurrent medications: {', '.join(user_data.get('medications', []))}"
            
        return context
    except Exception as e:
        print(f"Error getting context: {e}")
        return ""

def handle_onboarding(phone_number, message):
    """Handle user onboarding and profile creation"""
    if phone_number not in user_sessions:
        user_sessions[phone_number] = {'state': 'initial'}
        return ("Welcome to SolveMyHealth!\nDo you have an account? (Yes/No)\n"
                "I can help you manage your medications and check for interactions.")
    
    session = user_sessions[phone_number]
    
    if session['state'] == 'initial':
        if message.lower() == 'yes':
            if phone_number in users_db:
                session['state'] = 'chat'
                user_data = users_db[phone_number]
                return (f"Welcome back! I have your information:\n"
                       f"Conditions: {', '.join(user_data['conditions'])}\n"
                       f"Medications: {', '.join(user_data['medications'])}\n"
                       "How can I help you today?")
            session['state'] = 'get_name'
            return "I couldn't find your account. Let's create one. What's your name?"
        elif message.lower() == 'no':
            session['state'] = 'get_name'
            return "Let's create your profile. What's your name?"
    
    elif session['state'] == 'get_name':
        session['name'] = message
        session['state'] = 'get_conditions'
        return "What medical conditions do you have? (separate by comma)"
    
    elif session['state'] == 'get_conditions':
        conditions = [c.strip().lower() for c in message.split(',')]
        users_db[phone_number] = {
            'name': session.get('name', 'User'),
            'conditions': conditions,
            'medications': []
        }
        session['state'] = 'get_medications'
        return "What medications are you currently taking? (separate by comma)"
    
    elif session['state'] == 'get_medications':
        medications = [m.strip() for m in message.split(',')]
        users_db[phone_number]['medications'] = medications
        
        # Check for interactions
        interactions = check_medication_interactions(medications)
        session['state'] = 'chat'
        
        response = "Your profile has been created!\n"
        if interactions:
            response += "\nMedication Warnings:\n" + "\n".join(interactions)
        return response + "\nHow can I help you today?"
    
    return generate_response(message, phone_number)

def generate_response(message, phone_number):
    """Generate context-aware responses using RAG and Perplexity"""
    try:
        user_data = users_db.get(phone_number, {})
        
        # Get relevant context using RAG
        context = get_relevant_context(message, user_data)
        
        headers = {
            "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {
                    "role": "system",
                    "content": (f"You are a healthcare assistant. Use this context to answer: {context}\n"
                              "Consider the user's conditions and medications when responding.")
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
            
            # Check for medication interactions in the response
            if user_data.get('medications'):
                interactions = check_medication_interactions(user_data['medications'])
                if interactions:
                    ai_response += "\n\nImportant medication reminders:\n" + "\n".join(interactions)
            
            return ai_response
        return "I apologize, but I couldn't process your request."
            
    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}"

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