import asyncio
import re

# Dictionary to store user tasks
user_tasks = {}

emotesava = [
"emote-kiss",
"emote-no",
"emote-sad",
"emote-yes",
"emote-laughing",
"emote-hello",
"emote-wave",
"emote-shy",
"emote-tired",
"emoji-angry",
"idle-loop-sitfloor",
"emoji-thumbsup",
"emote-lust",
"emoji-cursing",
"emote-greedy",
"emoji-flex",
"emoji-gagging",
"emoji-celebrate",
"dance-macarena",
"dance-tiktok8",
"dance-blackpink",
"emote-model",
"dance-tiktok2",
"dance-pennywise",
"emote-bow",
"dance-russian",
"emote-curtsy",
"emote-snowball",
"emote-hot",
"emote-snowangel",
"emote-charging",
"dance-shoppingcart",
"emote-confused",
"idle-enthusiastic",
"emote-telekinesis",
"emote-float",
"emote-teleporting",
"emote-swordfight",
"emote-maniac",
"emote-energyball",
"emote-snake",
"idle_singing",
"emote-frog",
"emote-superpose",
"emote-cute",
"dance-tiktok9",
"dance-weird",
"dance-tiktok10",
"emote-pose7",
"emote-pose8",
"idle-dance-casual",
"emote-pose1",
"emote-pose3",
"emote-pose5",
"emote-cutey",
"emote-punkguitar",
"emote-zombierun", 
"emote-fashionista", 
"emote-gravity", 
"dance-icecream", 
"dance-wrong",
"idle-uwu",
"idle-dance-tiktok4"]

async def send_specific_emote_periodically(self, user, emote_name):
    try:
        # Check if there's an existing task for the user and cancel it
        existing_task = user_tasks.get(user.username)
        if existing_task:
            existing_task.cancel()
            await self.highrise.chat(f"Stopping your previous emote task, {user.username}!")

        # Use regular expression to find the emote name in the user's input
        emote_match = re.match(r'^\w+$', emote_name)
        if not emote_match:
            await self.highrise.chat(f"Invalid emote name format: {emote_name}. Stopping.")
            return

        provided_emote_name = emote_name.lower()

        # Check if the provided emote_name exists in the emotesava list
        if provided_emote_name not in [name.rsplit('-', 1)[-1] for name in emotesava]:
            await self.highrise.chat(f"Emote '{provided_emote_name}' not found in the list. Stopping.")
            return

        # Create a new task for the user
        task = asyncio.create_task(send_emote_periodically(self, user, provided_emote_name))
        user_tasks[user.username] = task

    except Exception as e:
        await self.highrise.chat(f"Error sending emote: {str(e)}")

async def send_emote_periodically(self, user, emote_name):
    while True:
        user_in_room = await is_user_in_room(self, user)
        if not user_in_room:
            await self.highrise.chat(f"User {user.username} is not in the room. Stopping.")
            return

        # Check if the emote_name exists in the emotesava list
        emote_found = False
        for emotes in emotesava:
            if emote_name.startswith(f"{emotes.rsplit('-', 1)[-1]}"): 
                await self.highrise.send_emote(emotes, user.id)
                await asyncio.sleep(2)
                emote_found = True
                break

        if not emote_found:
            await self.highrise.chat(f"Emote '{emote_name}' is not available. Type !emo for suggestions")
            # Cancel the task if the emote is not available
            existing_task = user_tasks.get(user.username)
            if existing_task:
                existing_task.cancel()
                await self.highrise.chat(f"Stopped your emote task due to invalid emote name, {user.username}!")
            return

async def is_user_in_room(self, user):
    room_users = await self.highrise.get_room_users()
    return any(room_user.id == user.id for room_user, _ in room_users.content)

async def stop_emote_task(self, user):
    existing_task = user_tasks.get(user.username)
    if existing_task:
        existing_task.cancel()
        await self.highrise.chat(f"Stopped your emote task, {user.username}!")
    else:
        await self.highrise.chat(f"No active emote task to stop, {user.username}!")
