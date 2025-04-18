from flask import Flask
import os
from threading import Thread
from dotenv import load_dotenv

load_dotenv()

app = Flask('')

@app.route('/')
def home():
    return "I'm alive"

def run():
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', 8081)),
        debug=True,           # Enable debug mode for auto-reload
        use_reloader=True     # Explicitly enable the reloader
    )

def keep_alive():  
    t = Thread(target=run)
    t.start()