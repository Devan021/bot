from flask import Flask , request 
from twilio.twiml.messaging_response import MessagingResponse
import openai 
import requests
import os 

app= Flask(__name__)

openai.api_key='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'

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
