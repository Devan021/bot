from flask import Flask , request 
from twilio.twiml.messaging_response import MessagingResponse
import openai 
import requests
import os 

app= Flask(__name__)

openai.api_key='API_KEY_REMOVED'

@app.route('/',methods = ['POST'])
def whatsapp():
    incoming_msg = request.values.get('Body','').strip()
    resp = MessagingResponse()
    msg= resp.message()
    
    response_text = generate_response(incoming_msg)
    msg.body(response_text)
    return str(resp)

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=(os.environ.get("PORT",5000)))
