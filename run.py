import os
import sys
import asyncio
import logging
import traceback
import time
from dotenv import load_dotenv
from main import Bot
from highrise.__main__ import main
from asyncio import run as arun

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('highrise_bot_runner')

class BotRunner:
    def __init__(self):
        load_dotenv()
        self.room_id = os.getenv("ROOM_ID")
        self.api_key = os.getenv("BOT_TOKEN")
        
        if not self.room_id or not self.api_key:
            logger.error("Missing ROOM_ID or BOT_TOKEN in environment variables")
            sys.exit(1)
            
        from highrise.__main__ import BotDefinition
        self.bot = Bot()
        self.definitions = [BotDefinition(self.bot, self.room_id, self.api_key)]
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.restart_delay = 5  # seconds
        
    async def run_with_reconnect(self):
        from connection_helper import with_retry
        try:
            await with_retry(main, self.definitions, max_retries=5)
        except Exception as e:
            logger.error(f"Bot connection error: {e}")
            await self.handle_reconnect()
    
    async def handle_reconnect(self):
        """Handle reconnection logic with exponential backoff"""
        self.reconnect_attempts += 1
        
        if self.reconnect_attempts > self.max_reconnect_attempts:
            logger.critical(f"Exceeded maximum reconnection attempts ({self.max_reconnect_attempts}). Giving up.")
            return
            
        # Calculate backoff time (exponential with jitter)
        delay = min(30, (2 ** self.reconnect_attempts) + (time.time() % 1))
        logger.info(f"Attempting to reconnect in {delay:.2f} seconds (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
        
        await asyncio.sleep(delay)
        logger.info("Reconnecting...")
        
        # Create a fresh bot instance to avoid stale connection state
        self.bot = Bot()
        self.definitions = [BotDefinition(self.bot, self.room_id, self.api_key)]
        
        # Try running again
        await self.run_with_reconnect()
        
    def run_loop(self):
        """Main entry point for the bot runner"""
        logger.info(f"Starting bot in room {self.room_id}")
        try:
            arun(self.run_with_reconnect())
        except KeyboardInterrupt:
            logger.info("Bot shutting down due to keyboard interrupt")
        except Exception as e:
            logger.critical(f"Unhandled exception in bot runner: {e}")
            logger.critical(traceback.format_exc())
            
if __name__ == "__main__":
    runner = BotRunner()
    runner.run_loop()
