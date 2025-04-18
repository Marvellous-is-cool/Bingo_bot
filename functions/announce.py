from highrise import *
from highrise.models import *
from highrise.webapi import *
from highrise.models_webapi import *
import re
import asyncio


async def announce(self: BaseBot, user_id: str, message: str) -> None:
    # Admin or Owner only
    # Get User object from user_id
    room_users = await self.highrise.get_room_users()
    if isinstance(room_users, GetRoomUsersRequest.GetRoomUsersResponse):
        user = next((u[0] for u in room_users.content if u[0].id == user_id), None)
        if not user:
            return
            
        # VIP check
        if not (user.username == 'coolbuoy' or user.username == 'User_taken2'):
            await self.highrise.send_whisper(user.id, "That's a BIN but no GO, only the vips or admin can tell me to make the call, sorryyyy!")
            return
        
    lower_msg = message.lower().strip()
    
    # 0. Stop
    if lower_msg == "!announce stop":
        if hasattr(self, "dice_task") and self.dice_task and not self.dice_task.done():
            self.dice_task.cancel()
            self.dice_task = None
            await self.highrise.chat("⏱️ Announce stopped.")
        else:
            await self.highrise.chat("No active announce task to stop.")
        return
    
    # 1. RULES & ROUND COMMANDS
    round_messages = {
        "!announce rules": [
            "**🎯 BINGO RULES:**",
            "- Host will roll dice with `!announce dice ...` \n - Match numbers in the correct order unless told otherwise \n - Revs is 5g per person and you have 5 revs each",
            "- The overall team wins the prize 🏆 \n - Once the number is called, start rolling till you get the number \n - Once you get the dice, both of you will say Bingo with your favorite emoji",
            "- The emoji must be the same and must not change throughout the game 🏆"
        ],
        "!announce r1": [
            "**🎯 Welcome to Round One:**",
            "- One dice number",
            "- Match in the two dice boxes",
            "- Both say Bingo",
            "- Last team loses 🏆"
        ],
        "!announce r2 y": [
            "**🎯 Round Two - In Order:**",
            "- Two dice numbers",
            "- Match in order",
            "- Both say Bingo",
            "- Last team loses 🏆"
        ],
        "!announce r2 n": [
            "**🎯 Round Two - Not in Order:**",
            "- Two dice numbers",
            "- Match in any order",
            "- Both say Bingo",
            "- Last team loses 🏆"
        ],
        "!announce r3 one": [
            "**🎯 Round Three - One Dice:**",
            "- Match across whole row",
            "- Both say Bingo",
            "- Last team loses 🏆"
        ],
        "!announce r3 two n": [
            "**🎯 Round Three - Two Dice, Any Order:**",
            "- Match both in any order",
            "- Whole row",
            "- Both say Bingo 🏆"
        ],
        "!announce r3 two y": [
            "**🎯 Round Three - Two Dice, In Order:**",
            "- Match in exact order",
            "- Whole row",
            "- Both say Bingo 🏆"
        ]
    }

    if lower_msg in round_messages:
        for i, line in enumerate(round_messages[lower_msg]):
            await self.highrise.chat(line)
            
            if i == 0:
                await asyncio.sleep(4)
            else:
                await asyncio.sleep(2.5)
        return

    
    # 2 set dice intervals
    if lower_msg.startswith("!announce set"):
        try:
            interval = int(lower_msg.split(" ")[2])
            self.dice_interval = interval 
            await self.highrise.chat(f"⏱️ Dice interval set to {interval} seconds.")
        except: 
            await self.highrise.chat("Invalid interval. Use '!announce set <interval>' to set the dice interval.")
        return
    
    # 3 Dice call: Single dice   
    match_dice = re.match(r"!announce dice\s+([\d\sand]+)(?:\s+([yn]))?$", lower_msg)
    if match_dice:
        raw = match_dice.group(1)
        order_flag = match_dice.group(2)
        dice_values = list(map(int, re.findall(r'\d+', raw)))
        ordered = order_flag == 'y'
        
        if not all(1 <= val <= 6 for val in dice_values):
            await self.highrise.chat("Waiting for the boss to announce the dice...")
            return
        
        # cancel any previous task
        if self.dice_task and not self.dice_task.done():
            self.dice_task.cancel()
              
        # interval lopp
        async def roll_dice_sequence():
            try:
                for i, val in enumerate(dice_values):
                    await self.highrise.chat(f"🎲 Official Dice{'s' if len(dice_values) > 1 else ''} Rolled: **{val}**")
                    if i < len(dice_values) - 1:
                        await asyncio.sleep(getattr(self,"dice_interval", 3))
                        
                if len(dice_values) > 1:
                    order_text = "in order" if ordered else "not in order"
                    await self.highrise.chat(f"🎲 Official Dices Rolled: **{dice_values}** ({order_text})")
            except asyncio.CancelledError:
                await self.highrise.chat("⏱️ Announce task cancelled.")
                return
                
            
        # start new task
        self.dice_task = asyncio.create_task(roll_dice_sequence())
        return
        
    await self.highrise.send_whisper(user.id, "❌ Couldn't understand your announce command.")
    