from flask import Flask, request 
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
from dotenv import load_dotenv
import os 

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Get environment variables with default values
openai_api_key = os.getenv('OPENAI_API_KEY')
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

# Initialize OpenAI client
client_openai = OpenAI(api_key=openai_api_key)

def generate_openai_response(message):
    try:
        completion = client_openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a healthcare assistant. Keep responses concise and under 150 words."},
                {"role": "user", "content": message}
            ],
            max_tokens=150
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}"

@app.route('/', methods=['GET', 'POST'])
def whatsapp():
    if request.method == 'POST':
        incoming_msg = request.values.get('Body', '').strip()
        resp = MessagingResponse()
        msg = resp.message()
        ai_response = generate_openai_response(incoming_msg)
        msg.body(ai_response)
        return str(resp)
    return "WhatsApp Webhook is running!", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)