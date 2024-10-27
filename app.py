from flask import Flask, request 
from twilio.twiml.messaging_response import MessagingResponse
import requests
from dotenv import load_dotenv
import os 

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Get Perplexity API key
perplexity_api_key = os.getenv('PERPLEXITY_API_KEY')
if not perplexity_api_key:
    raise ValueError("PERPLEXITY_API_KEY not found in environment variables")

def generate_perplexity_response(message):
    try:
        headers = {
            "Authorization": f"Bearer {perplexity_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "llama-3.1-sonar-small-128k-online",  # or any other available model
            "messages": [
                {
                    "role": "system",
                    "content": "You are a healthcare assistant. Keep responses concise and under 150 words and give only healthcare advice if the topic is not related to healthcare say that I am sorry would you like me to connect to a human."
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
            return response.json()['choices'][0]['message']['content']
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}"

@app.route('/', methods=['GET', 'POST'])
def whatsapp():
    if request.method == 'POST':
        try:
            incoming_msg = request.values.get('Body', '').strip()
            resp = MessagingResponse()
            msg = resp.message()
            ai_response = generate_perplexity_response(incoming_msg)
            msg.body(ai_response)
            return str(resp)
        except Exception as e:
            return str(MessagingResponse().message(f"Error: {str(e)}"))
    return "WhatsApp Webhook is running!", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)