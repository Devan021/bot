from flask import Flask , request 
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import openai 
import requests
import os 


app= Flask(__name__)

os.getenv('OPENAI_API_KEY')

# Initialize Twilio client
account_sid = 'AC918ceb3462ec0214eb181b00cde9590f'
auth_token = 'fa920fc4ad226015fadcda1499a2ad23'
client = Client(account_sid, auth_token)

@app.route('/', methods=['GET', 'POST'])
def whatsapp():
    if request.method == 'POST':
        # Get the incoming message
        incoming_msg = request.values.get('Body', '').strip()
        # Get the sender's WhatsApp number
        sender = request.values.get('From', '')
        
        # Create response
        resp = MessagingResponse()
        msg = resp.message()
        msg.body("Hi I am Devan")
        
        return str(resp)
    return "WhatsApp Webhook is running!", 200

@app.route("/status", methods=['POST','GET'])
def status():
    if request.method=='GET':
        return "Status callback received via GET", 200
    elif request.method=='POST':
        return "Status callback recieved via POST", 200


if __name__ == '__main__':
    app.run(host='0.0.0.0',port=(os.environ.get("PORT",9000)))



