from flask import Flask , request 
from twilio.twiml.messaging_response import MessagingResponse
import openai 
import requests
import os 

app= Flask(__name__)

os.getenv('OPENAI_API_KEY')

@app.route('/',methods = ['POST'])
def whatsapp():
    incoming_msg = request.values.get('Body','').strip()
    resp = MessagingResponse()
    msg= resp.message()
    
    response_text = generate_response(incoming_msg)
    msg.body(response_text)
    return str(resp)

@app.route("/status", methods=['POST','GET'])
def status():
    if request.method=='GET':
        return "Status callback received via GET", 200
    elif request.method=='POST':
        return "Status callback recieved via POST", 200


if __name__ == '__main__':
    app.run(host='0.0.0.0',port=(os.environ.get("PORT",5000)))



