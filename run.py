# You can run main.py directly for development:
#   python main.py
# This will start the bot without the Flask keep-alive server.
# For production or Replit-style keep-alive, use this run.py file.

from flask import Flask
from threading import Thread
from highrise.__main__ import *
import time
import os
from dotenv import load_dotenv
import traceback

# Load environment variables from .env file
load_dotenv()

class WebServer():
  def __init__(self):
    self.app = Flask(__name__)

    @self.app.route('/')
    def index() -> str:
      return "Alive"

  def run(self) -> None:
    port = int(os.getenv('PORT', 8081))  # Default to 8080 if not set
    self.app.run(
      host='0.0.0.0',
      port=port,
      debug=False,         # Disable debug mode in thread
      use_reloader=False   # Disable reloader in thread
    )

  def keep_alive(self):
    t = Thread(target=self.run)
    t.start()
    RunBot().run_loop()


class RunBot():
  def __init__(self) -> None:
    self.room_id = os.getenv('ROOM_ID', 'default_room_id')  # Provide a default value
    self.bot_token = os.getenv('BOT_TOKEN', 'default_bot_token')  # Provide a default value
    self.bot_file = "main"
    self.bot_class = "Bot"

    self.definitions = [
        BotDefinition(
            getattr(import_module(self.bot_file), self.bot_class)(),
            self.room_id, self.bot_token)
    ]  # More BotDefinition classes can be added to the definitions list

  def run_loop(self) -> None:
    while True:
      try:
        arun(main(self.definitions))

      except Exception as e:
        print("Error: ", e)
        traceback.print_exc()
        time.sleep(5)


if __name__ == "__main__":
  WebServer().keep_alive()
