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
            "- The emoji must be the same and must not change throughout the game 🏆",
            "Players/teams are not to chat in the room during the game \n - If you do, you will be disqualified from the game after 5 warnings \n - No exceptions",
            "Please communicate only in English and no other language during the game \n - If you do, you will be disqualified from the game after 5 warnings \n - No exceptions",
        ],
        "!announce reg": [
            "**🎲 HOW TO JOIN BINGO:**",
            "- Whisper me `hi, playing 😊` with your favorite emoji to join",
            "- Two players using the same emoji form a team 👯‍♂️",
            "- You must be on the bingo level (ground floor) to join",
            "- Each player gets 5 revs - use them wisely! 🎮"
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
    
    # 3 Dice call: Restrict !announce dice to only single dice
    match_dice = re.match(r"!announce dice\s+(\d+)$", lower_msg)
    if match_dice:
        dice_val = int(match_dice.group(1))
        if not (1 <= dice_val <= 6):
            await self.highrise.chat("Dice must be between 1 and 6.")
            return

        # cancel any previous task
        if self.dice_task and not self.dice_task.done():
            self.dice_task.cancel()

        async def roll_dice_sequence():
            try:
                await self.highrise.chat(f"🎲 Official Dice Rolled: **{dice_val}**")
            except asyncio.CancelledError:
                await self.highrise.chat("⏱️ Announce task cancelled.")
                return

        self.dice_task = asyncio.create_task(roll_dice_sequence())
        return

    # 3 Dice call: Only allow two dice for !announce dices
    match_dices = re.match(r"!announce dices\s+(\d+)\s+(\d+)(?:\s+([yn]))?$", lower_msg)
    if match_dices:
        dice1 = int(match_dices.group(1))
        dice2 = int(match_dices.group(2))
        order_flag = match_dices.group(3)
        ordered = order_flag == 'y'

        # Validate dice values
        if not (1 <= dice1 <= 6 and 1 <= dice2 <= 6):
            await self.highrise.chat("Both dice must be between 1 and 6.")
            return

        # cancel any previous task
        if self.dice_task and not self.dice_task.done():
            self.dice_task.cancel()

        async def roll_dice_sequence():
            try:
                await self.highrise.chat(f"🎲 Official Dices Rolled: **{dice1}** and **{dice2}**")
                await asyncio.sleep(getattr(self, "dice_interval", 3))
                order_text = "in order" if ordered else "not in order"
                await self.highrise.chat(f"🎲 Official Dices: **[{dice1}, {dice2}]** ({order_text})")
            except asyncio.CancelledError:
                await self.highrise.chat("⏱️ Announce task cancelled.")
                return

        self.dice_task = asyncio.create_task(roll_dice_sequence())
        return

    # Kick functionality for bingo (admin/vip only)
    match_kick = re.match(r"!announce kick\s+@?(\w+)", lower_msg)
    if match_kick:
        username = match_kick.group(1)
        # Only allow admin/vip
        if not (user.username == 'coolbuoy' or user.username == 'User_taken2'):
            await self.highrise.send_whisper(user.id, "Only the admin or vips can kick players from bingo.")
            return

        # Find user in room
        room_users = await self.highrise.get_room_users()
        if isinstance(room_users, GetRoomUsersRequest.GetRoomUsersResponse):
            target = next((u[0] for u in room_users.content if u[0].username.lower() == username.lower()), None)
            if not target:
                await self.highrise.send_whisper(user.id, f"User @{username} not found in the room.")
                return
            # Kick from room
            try:
                await self.highrise.moderate_room(target.id, "kick")
                await self.highrise.chat(f"@{username} has been kicked from the room by {user.username}.")
            except Exception as e:
                await self.highrise.send_whisper(user.id, f"Failed to kick @{username}: {e}")
        return
        
    await self.highrise.send_whisper(user.id, "❌ Couldn't understand your announce command.")
