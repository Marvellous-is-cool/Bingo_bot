from highrise import *
from highrise.models import *
from highrise.webapi import *
from highrise.models_webapi import *
import asyncio
import re

# Global state (in-memory, reset on bot restart)
players = []
player_labels = {}
player_revs = {}
recording = False
celebrating = False
ping_tasks = {}
owner_id = None
# Track which player is being pinged for rev/gg
pinged_players = set()

# Utility: Distance check
def is_within_distance(user_pos, bot_pos):
    if abs(user_pos.y - bot_pos.y) > 10:
        return False
    dx = abs(user_pos.x - bot_pos.x)
    dz = abs(user_pos.z - bot_pos.z)
    return (dx <= 10 and dz <= 10)

async def play_bingo(bot, user_id, message):
    global recording, owner_id, players, player_labels, player_revs, celebrating, pinged_players

    # Set owner_id if not set
    if owner_id is None:
        owner_id = bot.owner_id

    # Only record if recording is True and message is "hi, playing"
    if recording and message.lower().strip() == "hi, playing":
        # Get user object and position
        room_users_resp = await bot.highrise.get_room_users()
        # FIX: Use correct import for GetRoomUsersRequest
        if isinstance(room_users_resp, GetRoomUsersRequest.GetRoomUsersResponse):
            for room_user, pos in room_users_resp.content:
                if room_user.id == user_id:
                    # Check distance from bot
                    bot_pos = bot.get_bot_position()
                    if is_within_distance(pos, bot_pos):
                        if user_id not in [u.id for u in players] and len(players) < 18:
                            players.append(room_user)
                            player_revs[user_id] = 5
                            await bot.highrise.send_whisper(user_id, "You have joined the bingo game!")
                        else:
                            await bot.highrise.send_whisper(user_id, "Already joined or max players reached.")
                    else:
                        await bot.highrise.send_whisper(user_id, "You are too far from the bot to join.")
                    break

    # Owner starts the game
    if user_id == owner_id and message.lower().strip() == "!play":
        recording = False
        player_labels.clear()
        for idx, user in enumerate(players):
            player_labels[idx + 1] = user
        await bot.highrise.chat(f"Game started! Players: {', '.join([u.username for u in players])}")
        # Optionally DM each player their label
        for label, user in player_labels.items():
            await bot.highrise.send_whisper(user.id, f"Your player number is {label}. You have 5 revs.")

    # Owner/admin requests player list
    if user_id == owner_id and message.lower().strip() == "!players":
        msg = "\n".join([f"{label}: {user.username} ({player_revs[user.id]} revs left)" for label, user in player_labels.items()])
        await bot.highrise.send_whisper(user_id, f"Current players:\n{msg}")

    # Owner/admin starts recording
    if user_id == owner_id and message.lower().strip() == "!record":
        recording = True
        players.clear()
        player_labels.clear()
        player_revs.clear()
        await bot.highrise.chat("Recording players for bingo! Whisper 'hi, playing' to join.")

    # Handle !ping <n>
    m = re.match(r"!ping (\d+)", message.lower().strip())
    if m and user_id == owner_id:
        label = int(m.group(1))
        if label in player_labels:
            target_user = player_labels[label]
            # Start continuous whispering
            if label not in ping_tasks:
                ping_tasks[label] = asyncio.create_task(
                    ping_player(bot, target_user, label)
                )
            pinged_players.add(target_user.id)
            await bot.highrise.chat(f"Pinging player {label} ({target_user.username})...")
            # Stop celebration if running
            global celebrating
            celebrating = False

    # Add !show players command (anyone can use)
    if message.lower().strip() == "!show players":
        # Show 5 players per response
        items = list(player_labels.items())
        if not items:
            await bot.highrise.send_whisper(user_id, "No players in the game.")
            return
        chunks = [items[i:i+5] for i in range(0, len(items), 5)]
        for chunk in chunks:
            msg = "\n".join([f"{label}: {user.username} ({player_revs.get(user.id, 0)} revs left)" for label, user in chunk])
            await bot.highrise.send_whisper(user_id, f"Players:\n{msg}")

# Continuous whispering task
async def ping_player(bot, user, label):
    global player_revs, ping_tasks, pinged_players
    while True:
        await bot.highrise.send_whisper(user.id, "gg or rev (or tip 5g to the bot for rev)")
        await asyncio.sleep(2)
        # Stop if player is removed or out of revs
        if user.id not in player_revs or player_revs[user.id] <= 0:
            break
        # If player is no longer being pinged, stop
        if user.id not in pinged_players:
            break

# Call this from on_whisper to handle player responses
async def handle_player_response(bot, user, message):
    global player_revs, players, player_labels, ping_tasks, pinged_players
    # Find label
    label = None
    for l, u in player_labels.items():
        if u.id == user.id:
            label = l
            break
    if label is None:
        return

    if message.lower().strip() == "gg":
        await bot.highrise.send_whisper(user.id, "You are out! Thanks for playing.")
        # Remove player
        if user in players:
            players.remove(user)
        if user.id in player_revs:
            del player_revs[user.id]
        if label in player_labels:
            del player_labels[label]
        # Cancel ping task
        if label in ping_tasks:
            ping_tasks[label].cancel()
            del ping_tasks[label]
        pinged_players.discard(user.id)
        await bot.highrise.chat(f"{user.username} is out (gg).")
    elif message.lower().strip() == "rev":
        if player_revs[user.id] > 0:
            player_revs[user.id] -= 1
            await bot.highrise.send_whisper(user.id, f"Rev used! {player_revs[user.id]} revs left.")
            if player_revs[user.id] == 0:
                await bot.highrise.send_whisper(user.id, "No revs left. You are out!")
                # Remove player
                if user in players:
                    players.remove(user)
                if user.id in player_revs:
                    del player_revs[user.id]
                if label in player_labels:
                    del player_labels[label]
                if label in ping_tasks:
                    ping_tasks[label].cancel()
                    del ping_tasks[label]
                pinged_players.discard(user.id)
                await bot.highrise.chat(f"{user.username} is out (no revs left).")
        else:
            await bot.highrise.send_whisper(user.id, "No revs left. You are out!")
    # Optionally: handle 5g payment logic here

# Call this from on_tip to handle 5g payment as a rev
async def handle_player_tip(bot, sender: "User", receiver: "User", tip: int):
    global player_revs, player_labels, ping_tasks, pinged_players, players
    # Only process if sender is a player being pinged, tip is 5g, and receiver is bot
    if sender.id in player_revs and sender.id in pinged_players and tip == 5:
        player_revs[sender.id] -= 1
        await bot.highrise.send_whisper(sender.id, f"Rev used by tipping 5g! {player_revs[sender.id]} revs left.")
        # Find label
        label = None
        for l, u in player_labels.items():
            if u.id == sender.id:
                label = l
                break
        if player_revs[sender.id] == 0:
            await bot.highrise.send_whisper(sender.id, "No revs left. You are out!")
            if sender in players:
                players.remove(sender)
            if sender.id in player_revs:
                del player_revs[sender.id]
            if label in player_labels:
                del player_labels[label]
            if label in ping_tasks:
                ping_tasks[label].cancel()
                del ping_tasks[label]
            pinged_players.discard(sender.id)
            await bot.highrise.chat(f"{sender.username} is out (no revs left).")

# Call this from on_user_leave
async def handle_user_leave(bot, user):
    global players, player_labels, player_revs, ping_tasks, pinged_players
    # Remove from all lists
    if user in players:
        players.remove(user)
    for label, u in list(player_labels.items()):
        if u.id == user.id:
            del player_labels[label]
            if label in ping_tasks:
                ping_tasks[label].cancel()
                del ping_tasks[label]
    if user.id in player_revs:
        del player_revs[user.id]
    pinged_players.discard(user.id)

# Call this from on_chat to check for bingo+emoji
async def handle_bingo_celebration(bot, user, message):
    global player_labels, celebrating
    if any(u.id == user.id for u in player_labels.values()):
        if re.search(r"\bbingo\b", message.lower()) and re.search(r"\p{Emoji}", message, re.UNICODE):
            if not celebrating:
                celebrating = True
                await bot.highrise.send_emote("emoji-celebrate", user.id)

# To stop celebration on !ping, handled in play_bingo()

# To use:
# - In on_whisper: await play_bingo(bot, user.id, message); await handle_player_response(bot, user, message)
# - In on_chat: await handle_bingo_celebration(bot, user, message)
# - In on_user_leave: await handle_user_leave(bot, user)
# - In on_tip: await handle_player_tip(bot, sender, receiver, tip)
