from highrise import *
from highrise.models import *
from highrise.webapi import *
from highrise.models_webapi import *
import asyncio
import re

# Global state (in-memory, reset on bot restart)
players = []  # List of players
player_labels = {}  # Maps label to user
player_revs = {}  # Maps user_id to rev count
player_emojis = {}  # Maps user_id to their emoji
teams = {}  # Maps team number to list of user_ids
team_emojis = {}  # Maps emoji to team number
emoji_users = {}  # Maps emoji to list of users with that emoji
recording = False
celebrating = False
ping_tasks = {}
owner_id = None
# Track which player is being pinged for rev/gg
pinged_players = set()
# Track team celebrations
team_celebrations = {}  # Maps team_number to list of users who said bingo
player_celebrations = set()  # Set of users who said bingo
# Flag to continue celebration
continue_celebration = False

# Add new global variables to track bingo calls in current round
round_bingos = set()  # Set of user IDs who've said bingo in this round
team_round_bingos = {}  # Maps team numbers to sets of user IDs who've said bingo
auto_ping_task = None  # Task for auto-pinging last player/team

# Add global variables to track bingo timestamps
bingo_timestamps = {}  # Maps user_id to timestamp when they said bingo
team_bingo_timestamps = {}  # Maps team_num to timestamp when team completed bingo
game_ended = False  # Flag to track if game has already ended

# Utility: Distance check
def is_within_distance(user_pos, bot, bot_pos=None):
    """
    Check if a user is within the bingo playing area.
    Eligible zone requires:
    - y-coordinate must be ≤ 5 (ground level or slightly above)
    - z-coordinate must be between 3-30
    - x-coordinate can be any value
    """
    # Debug the position
    print(f"[BINGO] Position check - Type: {type(user_pos)}")
    
    try:
        # Position object (standard format with x, y, z attributes)
        if hasattr(user_pos, "x") and hasattr(user_pos, "y") and hasattr(user_pos, "z"):
            x, y, z = user_pos.x, user_pos.y, user_pos.z
            print(f"[BINGO] Position extracted from attributes: x={x}, y={y}, z={z}")
            
            # Return both eligibility and reason code
            if y > 5:
                return False, "not_ground_level"
            elif z < 3:
                return False, "before_bingo_peg"
            elif z > 30:
                return False, "past_bingo_area"
            else:
                return True, "eligible"
            
        # AnchorPosition (has anchor attribute)
        elif hasattr(user_pos, "anchor"):
            print(f"[BINGO] Anchor position: {user_pos.anchor}")
            # For anchor positions, we can't be sure of coordinates
            # Consider eligible only if it's likely a ground floor anchor
            ground_anchors = ["FrontLeft", "FrontRight", "BackLeft", "BackRight", "Center"]
            if user_pos.anchor in ground_anchors:
                return True, "eligible"
            else:
                return False, "invalid_anchor"
            
        else:
            # Unknown position type - log details for debugging
            print(f"[BINGO] Unknown position format: {repr(user_pos)}")
            return False, "unknown_position"
            
    except Exception as e:
        print(f"[BINGO] Error checking position: {e}")
        return False, "error"

# Extract emoji from message
def extract_emoji(message):
    """Extract the first emoji from a message"""
    # Simple pattern to match common emoji
    emoji_pattern = r'[\U0001F300-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251]+'
    match = re.search(emoji_pattern, message)
    if match:
        return match.group(0)
    return None

async def play_bingo(bot, user_id, message):
    global recording, owner_id, players, player_labels, player_revs, celebrating
    global player_emojis, teams, team_emojis, emoji_users, pinged_players, continue_celebration
    global round_bingos, team_round_bingos, auto_ping_task, game_ended
    
    # Set owner_id if not set
    if owner_id is None:
        owner_id = bot.owner_id

    # Only record if recording is True and message begins with "hi, playing"
    if recording and message.lower().strip().startswith("hi, playing"):
        # Check if game already started (!play executed)
        if player_labels:
            await bot.highrise.send_whisper(user_id, "The game has already started. Please wait for the next round.")
            return
            
        # Check if max players/teams reached (9 teams max)
        if len(teams) + len(players) >= 9:
            await bot.highrise.send_whisper(user_id, "Maximum number of teams/players (9) already reached. Please wait for the next round.")
            return
            
        # Extract emoji from message
        emoji = extract_emoji(message)
        if not emoji:
            await bot.highrise.send_whisper(user_id, "Please include an emoji in your message! For example: 'hi, playing 😊'")
            return
            
        try:
            room_users_resp = await bot.highrise.get_room_users()
            if isinstance(room_users_resp, GetRoomUsersRequest.GetRoomUsersResponse):
                for room_user, pos in room_users_resp.content:
                    if room_user.id == user_id:
                        print(f"[BINGO] Found user {room_user.username} at position: {pos}")
                        
                        # Check if user is at eligible location
                        eligible, reason = is_within_distance(pos, bot)
                        if eligible:
                            # Check if user already registered
                            if user_id in player_emojis:
                                await bot.highrise.send_whisper(user_id, "You've already joined the game!")
                                return
                                
                            # Register with emoji
                            player_emojis[user_id] = emoji
                            player_revs[user_id] = 5
                            
                            # Check if emoji already in use
                            if emoji in emoji_users:
                                # If already 2 users with this emoji, reject
                                if len(emoji_users[emoji]) >= 2:
                                    await bot.highrise.send_whisper(user_id, f"Emoji {emoji} is already being used by two players. Please use a different emoji.")
                                    del player_emojis[user_id]
                                    del player_revs[user_id]
                                    return
                                
                                # Add to existing team
                                emoji_users[emoji].append(room_user)
                                
                                # Notify both users they're now a team
                                team_number = len(teams) + 1
                                teams[team_number] = [u.id for u in emoji_users[emoji]]
                                team_emojis[emoji] = team_number
                                
                                # Remove first user from individual players if they were there
                                first_user = emoji_users[emoji][0]
                                if first_user in players:
                                    players.remove(first_user)
                                
                                # Make sure second user isn't in individual players
                                if room_user in players:
                                    players.remove(room_user)
                                
                                await bot.highrise.send_whisper(user_id, f"You've joined Team {team_number} with {emoji_users[emoji][0].username}! You have 5 revs.")
                                await bot.highrise.send_whisper(emoji_users[emoji][0].id, f"{room_user.username} has joined your team (Team {team_number})!")
                                await bot.highrise.chat(f"Team {team_number} formed with {emoji_users[emoji][0].username} and {room_user.username}! {emoji}")
                            else:
                                # New emoji, create new entry
                                emoji_users[emoji] = [room_user]
                                players.append(room_user)
                                await bot.highrise.send_whisper(user_id, f"You've joined as a player with emoji {emoji}! You have 5 revs.")
                                await bot.highrise.chat(f"{room_user.username} has joined the game with {emoji}!")
                        else:
                            # Send specific message based on reason
                            if reason == "before_bingo_peg":
                                await bot.highrise.send_whisper(user_id, "You're not inside the bingo peg area. Please move forward (z ≥ 3) and try again.")
                            elif reason == "past_bingo_area":
                                await bot.highrise.send_whisper(user_id, "You've gone too far into the room. Please move back to the bingo area (z ≤ 30) and try again.")
                            elif reason == "not_ground_level":
                                await bot.highrise.send_whisper(user_id, "Please make sure you're not sitting down when joining. Stand up and try again.")
                            else:
                                await bot.highrise.send_whisper(user_id, "You need to be on the bingo level (y ≤ 5, z between 3-30) to join.")
                        break
        except Exception as e:
            print(f"[BINGO] Error in play_bingo when checking positions: {e}")
            await bot.highrise.send_whisper(user_id, "Error checking your position. Please try again.")

    # Owner starts the game
    if user_id == owner_id and message.lower().strip() == "!play":
        recording = False
        # Assign player numbers
        player_labels.clear()
        
        # Number individual players
        for idx, user in enumerate(players):
            player_num = idx + 1
            player_labels[player_num] = user
            
        # Teams are already numbered during registration
        await bot.highrise.chat(f"Game started! {len(players)} individual players and {len(teams)} teams registered!")
        
        # Reset celebration tracking
        team_celebrations.clear()
        player_celebrations.clear()
        continue_celebration = False

    # Owner/admin requests player list
    if user_id == owner_id and message.lower().strip() == "!players":
        response = []
        
        # List individual players
        if players:
            response.append("Players:")
            for idx, user in enumerate(players):
                player_num = idx + 1
                emoji = player_emojis.get(user.id, "")
                revs = player_revs.get(user.id, 0)
                response.append(f"Player {player_num}: @{user.username} {emoji} ({revs} revs left)")
                
        # List teams
        if teams:
            response.append("\nTeams:")
            for team_num, user_ids in teams.items():
                team_members = []
                emoji = ""
                for uid in user_ids:
                    for user in emoji_users.get(player_emojis.get(uid, ""), []):
                        if user.id == uid:
                            team_members.append(f"@{user.username}")
                            emoji = player_emojis.get(uid, "")
                            break
                revs = [player_revs.get(uid, 0) for uid in user_ids]
                response.append(f"Team {team_num}: {' & '.join(team_members)} {emoji} ({', '.join(str(r) for r in revs)} revs)")
        
        if not response:
            response = ["No players or teams registered yet."]
            
        await bot.highrise.send_whisper(user_id, "\n".join(response))

    # Owner/admin starts recording
    if user_id == owner_id and message.lower().strip() == "!record":
        recording = True
        players.clear()
        player_labels.clear()
        player_revs.clear()
        player_emojis.clear()
        teams.clear()
        team_emojis.clear()
        emoji_users.clear()
        team_celebrations.clear()
        player_celebrations.clear()
        continue_celebration = False
        await bot.highrise.chat("Recording players for bingo! Whisper 'hi, playing 😊' to join (include your favorite emoji).")

    # Reset celebration with !nxt command
    if (user_id == owner_id or any(u.id == user_id for u in player_labels.values())) and message.lower().strip() == "!nxt":
        celebrating = False
        continue_celebration = False
        team_celebrations.clear()
        player_celebrations.clear()
        
        # Reset round tracking for new round
        round_bingos.clear()
        team_round_bingos.clear()
        
        # Cancel any auto ping task
        if auto_ping_task and not auto_ping_task.done():
            auto_ping_task.cancel()
            auto_ping_task = None
            
        # Remove all users from being pinged
        pinged_players.clear()
        
        await bot.highrise.chat("Ready for the next round! 🎲")
        
        # Check for missing bingos after a short delay
        await asyncio.sleep(1)
        await check_for_last_players(bot)

    # Withdraw celebration with !not command
    if user_id == owner_id and message.lower().strip().startswith("!not "):
        target = message.lower().strip()[5:].strip()
        if target.startswith("t"):
            # Team withdrawal
            try:
                team_num = int(target[1:])
                if team_num in teams:
                    # Remove from celebrations
                    if team_num in team_celebrations:
                        team_celebrations.pop(team_num)
                    
                    # Also remove from round_bingos tracking for auto-ping
                    if team_num in team_round_bingos:
                        # For each user in the team, remove from round_bingos
                        for user_id in teams[team_num]:
                            if user_id in round_bingos:
                                round_bingos.remove(user_id)
                        # Remove team from team_round_bingos
                        team_round_bingos.pop(team_num)
                    
                    # Stop any celebration
                    celebrating = False
                    continue_celebration = False
                    
                    # Cancel auto-ping task if it was for this team
                    if auto_ping_task and not auto_ping_task.done():
                        auto_ping_task.cancel()
                        auto_ping_task = None
                    
                    await bot.highrise.chat("⛔ Celebration withdrawn, the dice are not correct!")
                    
                    # Recheck for last players to auto-ping after a short delay
                    await asyncio.sleep(1)
                    await check_for_last_players(bot)
                else:
                    await bot.highrise.send_whisper(user_id, f"Team {team_num} not found.")
            except ValueError:
                await bot.highrise.send_whisper(user_id, "Invalid team number. Use !not t<number>")
        else:
            # Player withdrawal
            try:
                player_num = int(target)
                if player_num in player_labels:
                    user = player_labels[player_num]
                    
                    # Remove from celebrations
                    if user.id in player_celebrations:
                        player_celebrations.remove(user.id)
                    
                    # Also remove from round_bingos tracking for auto-ping
                    if user.id in round_bingos:
                        round_bingos.remove(user.id)
                    
                    # Stop any celebration
                    celebrating = False
                    continue_celebration = False
                    
                    # Cancel auto-ping task if it was for this player
                    if auto_ping_task and not auto_ping_task.done():
                        auto_ping_task.cancel()
                        auto_ping_task = None
                        
                    await bot.highrise.chat("⛔ Celebration withdrawn, the dice are not correct!")
                    
                    # Recheck for last players to auto-ping after a short delay
                    await asyncio.sleep(1)
                    await check_for_last_players(bot)
                else:
                    await bot.highrise.send_whisper(user_id, f"Player {player_num} not found.")
            except ValueError:
                await bot.highrise.send_whisper(user_id, "Invalid player number. Use !not <number>")

    # Handle !ping <n> for individual players
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
            celebrating = False
            continue_celebration = False
    
    # Handle !ping t<n> for teams
    m = re.match(r"!ping t(\d+)", message.lower().strip())
    if m and user_id == owner_id:
        team_num = int(m.group(1))
        if team_num in teams:
            # Get team member user objects
            team_members = []
            for uid in teams[team_num]:
                # Find user object for each team member
                for emoji, users in emoji_users.items():
                    for user in users:
                        if user.id == uid:
                            team_members.append(user)
                            break
            
            # Start pinging both team members
            for i, member in enumerate(team_members):
                # Use team_num*100+i as unique task label
                task_label = team_num * 100 + i
                if task_label not in ping_tasks:
                    ping_tasks[task_label] = asyncio.create_task(
                        ping_player(bot, member, f"t{team_num}")
                    )
                pinged_players.add(member.id)
            
            # Get team member usernames for message
            member_names = [member.username for member in team_members]
            await bot.highrise.chat(f"Pinging Team {team_num} ({' & '.join(member_names)})...")
            
            # Stop celebration if running
            celebrating = False
            continue_celebration = False

    # Add !show players command (anyone can use)
    if message.lower().strip() == "!show players":
        response = []
        
        # List individual players
        if players:
            response.append("Players:")
            for idx, user in enumerate(players):
                player_num = idx + 1
                emoji = player_emojis.get(user.id, "")
                revs = player_revs.get(user.id, 0)
                response.append(f"Player {player_num}: @{user.username} {emoji} ({revs} revs left)")
                
        # List teams
        if teams:
            response.append("\nTeams:")
            for team_num, user_ids in teams.items():
                team_members = []
                emoji = ""
                for uid in user_ids:
                    for user in emoji_users.get(player_emojis.get(uid, ""), []):
                        if user.id == uid:
                            team_members.append(f"@{user.username}")
                            emoji = player_emojis.get(uid, "")
                            break
                revs = [player_revs.get(uid, 0) for uid in user_ids]
                response.append(f"Team {team_num}: {' & '.join(team_members)} {emoji} ({', '.join(str(r) for r in revs)} revs)")
        
        if not response:
            response = ["No players or teams registered yet."]
            
        await bot.highrise.send_whisper(user_id, "\n".join(response))

    # Owner ends the game and announces winner
    if user_id == owner_id and message.lower().strip() == "!end":
        # Only allow !end if the game hasn't automatically ended
        if not game_ended:
            if len(player_labels) + len(teams) == 1:
                # Find the winner
                if player_labels:
                    winner = next(iter(player_labels.values()))
                    winner_emoji = player_emojis.get(winner.id, "")
                    await bot.highrise.chat(f"🎉 The game has ended! The winner is {winner.username} {winner_emoji}! Congratulations! 🎉")
                elif teams:
                    team_num = next(iter(teams.keys()))
                    team_members = []
                    team_emoji = ""
                    for uid in teams[team_num]:
                        for user in emoji_users.get(player_emojis.get(uid, ""), []):
                            if user.id == uid:
                                team_members.append(f"@{user.username}")
                                team_emoji = player_emojis.get(uid, "")
                                break
                    await bot.highrise.chat(f"🎉 The game has ended! Team {team_num} ({' & '.join(team_members)}) {team_emoji} wins! Congratulations! 🎉")
            elif len(player_labels) + len(teams) == 0:
                await bot.highrise.chat("The game has ended! There is no winner.")
            else:
                await bot.highrise.chat("The game has ended! No single winner could be determined.")
                
            # Reset all game state
            await reset_game()
        else:
            await bot.highrise.send_whisper(user_id, "The game has already ended automatically. Use !record to start a new game.")

# Check who hasn't said bingo and auto-ping the last player(s)
async def check_for_last_players(bot):
    global players, teams, round_bingos, team_round_bingos, auto_ping_task, pinged_players
    global bingo_timestamps, team_bingo_timestamps, game_ended
    
    # If there's already an auto-ping task running, cancel it
    if auto_ping_task and not auto_ping_task.done():
        auto_ping_task.cancel()
        auto_ping_task = None
    
    # Log the current state for debugging
    print(f"[BINGO AUTO-PING] Checking for last players...")
    print(f"[BINGO AUTO-PING] Total players: {len(players)}")
    print(f"[BINGO AUTO-PING] Total teams: {len(teams)}")
    print(f"[BINGO AUTO-PING] Players who said bingo: {len(round_bingos)}")
    print(f"[BINGO AUTO-PING] Team bingos: {team_round_bingos}")
    
    # Remove any users who are already being manually pinged 
    # from consideration for auto-pinging
    active_players = [p for p in players if p.id not in pinged_players]
    active_teams = {t_num: members for t_num, members in teams.items() 
                    if not any(uid in pinged_players for uid in members)}
    
    # Check individual players who haven't said bingo
    missing_players = []
    for player in active_players:
        if player.id not in round_bingos:
            missing_players.append(player)
            print(f"[BINGO AUTO-PING] Player {player.username} hasn't said bingo")
    
    # Check teams where not all members have said bingo
    missing_teams = []
    for team_num, user_ids in active_teams.items():
        # Get users who said bingo in this team for this round
        team_bingos = team_round_bingos.get(team_num, set())
        
        # If not all team members said bingo, team is missing
        if len(team_bingos) < len(user_ids):
            missing_teams.append(team_num)
            print(f"[BINGO AUTO-PING] Team {team_num} hasn't fully said bingo. Members said: {team_bingos}")
    
    print(f"[BINGO AUTO-PING] Missing players: {len(missing_players)}")
    print(f"[BINGO AUTO-PING] Missing teams: {len(missing_teams)}")
    
    # If only one player or team left, auto-ping them
    if len(missing_players) == 1 and len(missing_teams) == 0:
        # Auto-ping last individual player
        last_player = missing_players[0]
        print(f"[BINGO AUTO-PING] Auto-pinging last player: {last_player.username}")
        await bot.highrise.chat(f"Only {last_player.username} hasn't said bingo! Auto-pinging...")
        auto_ping_task = asyncio.create_task(auto_ping_player(bot, last_player))
        
    elif len(missing_players) == 0 and len(missing_teams) == 1:
        # Auto-ping last team
        last_team_num = missing_teams[0]
        team_members = []
        team_member_objects = []
        
        # Get team members
        for uid in teams[last_team_num]:
            for emoji, users in emoji_users.items():
                for user in users:
                    if user.id == uid:
                        team_members.append(user.username)
                        team_member_objects.append(user)
                        break
        
        print(f"[BINGO AUTO-PING] Auto-pinging last team: {team_members}")
        await bot.highrise.chat(f"Only Team {last_team_num} ({', '.join(team_members)}) hasn't said bingo! Auto-pinging...")
        
        # Start auto-pinging each team member
        auto_ping_task = asyncio.create_task(auto_ping_team(bot, last_team_num, team_member_objects))
    
    # If everyone said bingo, announce it
    if len(missing_players) == 0 and len(missing_teams) == 0 and (active_players or active_teams):
        print("[BINGO AUTO-PING] Everyone has said bingo! Round complete! 🎉")
        await bot.highrise.chat("Everyone said bingo! Round complete! 🎉")
        
        # Check if we recorded timestamps and find the last one to say bingo
        if bingo_timestamps or team_bingo_timestamps:
            # Combine individual and team timestamps
            all_timestamps = {}
            
            # Add individual player timestamps
            for user_id, timestamp in bingo_timestamps.items():
                all_timestamps[user_id] = {"timestamp": timestamp, "is_team": False}
            
            # Add team timestamps (use the second team member's timestamp as completion time)
            for team_num, timestamp in team_bingo_timestamps.items():
                # Use team number as key with special prefix to avoid collision with user IDs
                team_key = f"team_{team_num}"
                all_timestamps[team_key] = {"timestamp": timestamp, "is_team": True, "team_num": team_num}
            
            # Find the last timestamp
            if all_timestamps:
                last_bingo = max(all_timestamps.items(), key=lambda x: x[1]["timestamp"])
                last_key = last_bingo[0]
                
                # Check if it's a team or individual player
                if last_bingo[1]["is_team"]:
                    team_num = last_bingo[1]["team_num"]
                    
                    # Get team members
                    team_members = []
                    team_member_objects = []
                    for uid in teams[team_num]:
                        for emoji, users in emoji_users.items():
                            for user in users:
                                if user.id == uid:
                                    team_members.append(user.username)
                                    team_member_objects.append(user)
                                    break
                    
                    await bot.highrise.chat(f"Team {team_num} ({', '.join(team_members)}) was the last to say bingo! You lose this round!")
                    
                    # Start pinging team as losers
                    for i, member in enumerate(team_member_objects):
                        # Use team_num*100+i as unique task label
                        task_label = team_num * 100 + i
                        if task_label not in ping_tasks:
                            ping_tasks[task_label] = asyncio.create_task(
                                ping_player(bot, member, f"t{team_num}")
                            )
                        pinged_players.add(member.id)
                else:
                    # Find user from ID
                    for p in players:
                        if p.id == last_key:
                            await bot.highrise.chat(f"{p.username} was the last to say bingo! You lose this round!")
                            
                            # Find label for player
                            label = None
                            for l, u in player_labels.items():
                                if u.id == p.id:
                                    label = l
                                    break
                            
                            # Start pinging player as loser
                            if label not in ping_tasks:
                                ping_tasks[label] = asyncio.create_task(
                                    ping_player(bot, p, label)
                                )
                            pinged_players.add(p.id)
                            break
        
        # Clear timestamps for next round
        bingo_timestamps.clear()
        team_bingo_timestamps.clear()
    
    print(f"[BINGO AUTO-PING] Multiple players/teams still need to say bingo: {len(missing_players)} players, {len(missing_teams)} teams")

# Check if there's only one player/team left and declare them winner
async def check_for_winner(bot):
    global players, teams, player_labels, game_ended
    
    # If game already ended, don't proceed
    if game_ended:
        return
    
    total_players_teams = len(player_labels) + len(teams)
    print(f"[BINGO] Checking for winner: {total_players_teams} players/teams left")
    
    if total_players_teams == 1:
        game_ended = True
        
        # Find the winner
        if player_labels:
            winner = next(iter(player_labels.values()))
            winner_emoji = player_emojis.get(winner.id, "")
            await bot.highrise.chat(f"🏆 GAME OVER! We have a winner! {winner.username} {winner_emoji} is the last player standing! 🎉")
            
            # Send celebration emotes to winner
            for _ in range(3):
                try:
                    await bot.highrise.send_emote("emoji-celebrate", winner.id)
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"[BINGO] Error sending celebration to winner: {e}")
                    
        elif teams:
            team_num = next(iter(teams.keys()))
            team_members = []
            team_emoji = ""
            for uid in teams[team_num]:
                for user in emoji_users.get(player_emojis.get(uid, ""), []):
                    if user.id == uid:
                        team_members.append(f"{user.username}")
                        team_emoji = player_emojis.get(uid, "")
                        
                        # Send celebration emotes to team members
                        try:
                            for _ in range(3):
                                await bot.highrise.send_emote("emoji-celebrate", uid)
                                await asyncio.sleep(1)
                        except Exception as e:
                            print(f"[BINGO] Error sending celebration to team member: {e}")
                            
            await bot.highrise.chat(f"🏆 GAME OVER! We have winners! Team {team_num} ({' & '.join(team_members)}) {team_emoji} is the last team standing! 🎉")
            
        # Reset all game state
        await reset_game()
        await bot.highrise.chat("The game has ended. Use !record to start a new game!")
        return True
    
    return False

# Reset all game state
async def reset_game():
    global players, player_labels, player_revs, player_emojis, teams, team_emojis
    global emoji_users, pinged_players, team_celebrations, player_celebrations
    global celebrating, continue_celebration, round_bingos, team_round_bingos
    global auto_ping_task, ping_tasks, game_ended
    
    players.clear()
    player_labels.clear()
    player_revs.clear()
    player_emojis.clear()
    teams.clear()
    team_emojis.clear()
    emoji_users.clear()
    pinged_players.clear()
    team_celebrations.clear()
    player_celebrations.clear()
    
    # Cancel any running tasks
    if auto_ping_task and not auto_ping_task.done():
        auto_ping_task.cancel()
    auto_ping_task = None
    
    for task in ping_tasks.values():
        task.cancel()
    ping_tasks.clear()
    
    celebrating = False
    continue_celebration = False
    round_bingos.clear()
    team_round_bingos.clear()
    game_ended = False

# Auto-ping an individual player until they respond
async def auto_ping_player(bot, player):
    global pinged_players
    
    print(f"[BINGO AUTO-PING] Started auto-pinging player: {player.username}")
    pinged_players.add(player.id)
    try:
        ping_count = 0
        while player.id in pinged_players and ping_count < 10:  # Max 10 pings
            await bot.highrise.send_whisper(player.id, "You're the last one! Say 'bingo' with your emoji, or 'gg' to give up!")
            
            # Send sad emote every other ping to indicate they're losing
            if ping_count % 2 == 0:
                try:
                    await bot.highrise.send_emote("emote-sad", player.id)
                except Exception as e:
                    print(f"[BINGO] Error sending sad emote: {e}")
                    
            await asyncio.sleep(5)  # Ping every 5 seconds
            ping_count += 1
            print(f"[BINGO AUTO-PING] Ping {ping_count}/10 sent to {player.username}")
    except Exception as e:
        print(f"[BINGO AUTO-PING] Error auto-pinging player: {e}")
    finally:
        print(f"[BINGO AUTO-PING] Finished auto-pinging player: {player.username}")
        pinged_players.discard(player.id)

# Auto-ping a team until they respond
async def auto_ping_team(bot, team_num, team_members):
    global pinged_players, teams
    
    member_names = [member.username for member in team_members]
    print(f"[BINGO AUTO-PING] Started auto-pinging team {team_num}: {member_names}")
    
    # Add all team members to pinged players
    for member in team_members:
        pinged_players.add(member.id)
    
    try:
        ping_count = 0
        # Get team's user IDs
        team_ids = teams.get(team_num, [])
        
        while any(uid in pinged_players for uid in team_ids) and ping_count < 10:  # Max 10 pings
            # Send whisper to each team member
            for member in team_members:
                if member.id in pinged_players:
                    await bot.highrise.send_whisper(member.id, "Your team is the last one! Say 'bingo' with your team emoji, or 'gg' to give up!")
                    
                    # Send sad emote every other ping
                    if ping_count % 2 == 0:
                        try:
                            await bot.highrise.send_emote("emote-sad", member.id)
                        except Exception as e:
                            print(f"[BINGO] Error sending sad emote: {e}")
            
            await asyncio.sleep(5)  # Ping every 5 seconds
            ping_count += 1
            print(f"[BINGO AUTO-PING] Ping {ping_count}/10 sent to team {team_num}")
    except Exception as e:
        print(f"[BINGO AUTO-PING] Error auto-pinging team: {e}")
    finally:
        print(f"[BINGO AUTO-PING] Finished auto-pinging team {team_num}")
        for member in team_members:
            pinged_players.discard(member.id)

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
    global teams, emoji_users, player_emojis, team_emojis, auto_ping_task
    
    # Find label for individual players
    label = None
    for l, u in player_labels.items():
        if u.id == user.id:
            label = l
            break
    
    # Find team for team players
    user_team = None
    for team_num, user_ids in teams.items():
        if user.id in user_ids:
            user_team = team_num
            break

    if label is None and user_team is None:
        return  # Not a player in the game

    # Handle "gg" command (give up)
    if message.lower().strip() == "gg":
        await handle_player_gg(bot, user, label, user_team)
        
    # Handle "rev" command (use revival)
    elif message.lower().strip() == "rev":
        await handle_player_rev(bot, user, label, user_team)

# Call this from on_tip to handle 5g payment as a rev
async def handle_player_tip(bot, sender: "User", receiver: "User", tip: int):
    global player_revs, player_labels, ping_tasks, pinged_players, players
    global teams, emoji_users, player_emojis, team_emojis, auto_ping_task
    
    # Only process if sender is a player being pinged, tip is 5g, and receiver is bot
    if sender.id in player_revs and sender.id in pinged_players and tip == 5:
        # Find if player is in a team
        user_team = None
        for team_num, user_ids in teams.items():
            if sender.id in user_ids:
                user_team = team_num
                break
                
        # Find individual player label
        label = None
        for l, u in player_labels.items():
            if u.id == sender.id:
                label = l
                break
                
        # Process rev
        player_revs[sender.id] -= 1
        await bot.highrise.send_whisper(sender.id, f"Rev used by tipping 5g! {player_revs[sender.id]} revs left.")
        
        # Check if out of revs
        if player_revs[sender.id] == 0:
            await bot.highrise.send_whisper(sender.id, "No revs left. You are out!")
            
            # Handle team case - if in a team, make teammate individual player
            if user_team is not None:
                # Find the teammate who will become an individual player
                teammate_id = next((uid for uid in teams[user_team] if uid != sender.id), None)
                
                if teammate_id:
                    # Find the teammate user object
                    teammate = None
                    user_emoji = player_emojis.get(sender.id)
                    if user_emoji and user_emoji in emoji_users:
                        for u in emoji_users[user_emoji]:
                            if u.id == teammate_id:
                                teammate = u
                                break
                    
                    if teammate:
                        # Add teammate to individual players if not already there
                        if teammate not in players:
                            players.append(teammate)
                        
                        # Notify about team change
                        await bot.highrise.chat(f"Team {user_team} has been split. {sender.username} is out of revs, {teammate.username} continues as an individual player.")
                
                # Remove team
                del teams[user_team]
                
                # Clean up team-specific pingings
                for i in range(2):  # Check both potential team member task IDs
                    task_label = user_team * 100 + i
                    if task_label in ping_tasks:
                        ping_tasks[task_label].cancel()
                        del ping_tasks[task_label]
            
            # Remove individual player if applicable
            if sender in players:
                players.remove(sender)
            
            # Clean up player data
            if sender.id in player_revs:
                del player_revs[sender.id]
            if label in player_labels:
                del player_labels[label]
            
            # Clean up emoji_users entries
            user_emoji = player_emojis.get(sender.id)
            if user_emoji and user_emoji in emoji_users:
                emoji_users[user_emoji] = [u for u in emoji_users[user_emoji] if u.id != sender.id]
                if not emoji_users[user_emoji]:
                    del emoji_users[user_emoji]
                elif user_emoji in team_emojis and user_team is None:  # Only cleanup team_emojis if not already handled
                    del team_emojis[user_emoji]
            
            if sender.id in player_emojis:
                del player_emojis[sender.id]
            
            # Cancel ping task if exists
            if label in ping_tasks:
                ping_tasks[label].cancel()
                del ping_tasks[label]
            pinged_players.discard(sender.id)
            
            # Remove from round tracking for auto-ping
            if sender.id in round_bingos:
                round_bingos.remove(sender.id)
            
            # Cancel auto-ping task if this player/team was the last one
            if auto_ping_task and not auto_ping_task.done():
                auto_ping_task.cancel()
                auto_ping_task = None
            
            # Teleport the player to the top level (same as gg)
            try:
                await bot.highrise.teleport(user_id=sender.id,
                                           dest=Position(float(13), float(12),
                                                         float(29)))
            except Exception as e:
                print(f"Error teleporting player: {e}")
                # Add fallback message if teleportation fails
                await bot.highrise.send_whisper(sender.id, "Please hit the spikes in front of you to exit the playing area. Thank you!")
            
            await bot.highrise.chat(f"{sender.username} is out (no revs left).")
            
            # Check if this was the last player/team
            await check_for_last_players(bot)
            
            # Check if there's only one player/team left after this removal
            winner_declared = await check_for_winner(bot)
            if not winner_declared:
                # Only send this message if we didn't declare a winner
                await bot.highrise.chat(f"{sender.username} is out (no revs left).")

# Call this from on_user_leave
async def handle_user_leave(bot, user):
    global players, player_labels, player_revs, ping_tasks, pinged_players
    global teams, emoji_users, player_emojis, team_emojis, auto_ping_task
    
    # Check if the user was a player in the game
    user_was_player = False
    
    # Check if user is in individual players
    if user in players:
        players.remove(user)
        user_was_player = True
    
    # Check if user is in a team
    user_team = None
    for team_num, user_ids in list(teams.items()):
        if user.id in user_ids:
            user_team = team_num
            user_was_player = True
            
            # Find the teammate who will become an individual player
            teammate_id = next((uid for uid in user_ids if uid != user.id), None)
            
            if teammate_id:
                # Find the teammate user object
                teammate = None
                user_emoji = player_emojis.get(user.id)
                if user_emoji and user_emoji in emoji_users:
                    for u in emoji_users[user_emoji]:
                        if u.id == teammate_id:
                            teammate = u
                            break
                
                if teammate:
                    # Add teammate to individual players
                    if teammate not in players:
                        players.append(teammate)
                    
                    # Notify the room about team change
                    await bot.highrise.chat(f"Team {team_num} has been disbanded because {user.username} left. {teammate.username} is now playing individually.")
            
            # Remove team
            del teams[team_num]
            break
    
    # Clean up player_labels entries
    for label, u in list(player_labels.items()):
        if u.id == user.id:
            del player_labels[label]
            if label in ping_tasks:
                ping_tasks[label].cancel()
                del ping_tasks[label]
    
    # Clean up emoji_users entries
    user_emoji = player_emojis.get(user.id)
    if user_emoji and user_emoji in emoji_users:
        emoji_users[user_emoji] = [u for u in emoji_users[user_emoji] if u.id != user.id]
        if not emoji_users[user_emoji]:
            del emoji_users[user_emoji]
        elif user_emoji in team_emojis:
            del team_emojis[user_emoji]
    
    # Clean up other player data
    if user.id in player_emojis:
        del player_emojis[user.id]
    if user.id in player_revs:
        del player_revs[user.id]
    
    # Clean up ping tasks for team members
    if user_team:
        for i in range(2):  # Check both potential team member task IDs
            task_label = user_team * 100 + i
            if task_label in ping_tasks:
                ping_tasks[task_label].cancel()
                del ping_tasks[task_label]
    
    pinged_players.discard(user.id)
    
    # After cleaning up the player data, check if we have a winner
    if len(player_labels) + len(teams) == 1:
        print(f"[BINGO] Only one player/team left after {user.username} left")
        await declare_winner(bot)
    
    # Return whether the user was a player so the main bot can use this info
    return user_was_player

# Call this from on_chat to check for bingo+emoji
async def handle_bingo_celebration(bot, user, message):
    global player_labels, celebrating, continue_celebration, teams, player_emojis, emoji_users
    global team_celebrations, player_celebrations, team_emojis, round_bingos, team_round_bingos
    global auto_ping_task, pinged_players, bingo_timestamps, team_bingo_timestamps, game_ended
    
    # If not a player or in a team, ignore
    if user.id not in player_emojis:
        return
    
    message_lower = message.lower().strip()
    
    # Handle "gg" or "rev" commands in chat (not just whisper)
    if message_lower == "gg" or message_lower == "rev":
        # This player wants to use a rev or give up
        if user.id in pinged_players:
            print(f"[BINGO] Player {user.username} responded with '{message_lower}' in chat")
            # Find label for individual players
            label = None
            for l, u in player_labels.items():
                if u.id == user.id:
                    label = l
                    break
            
            # Find team for team players
            user_team = None
            for team_num, user_ids in teams.items():
                if user.id in user_ids:
                    user_team = team_num
                    break
            
            if message_lower == "gg":
                await handle_player_gg(bot, user, label, user_team)
            elif message_lower == "rev":
                await handle_player_rev(bot, user, label, user_team)
            return
    
    # Check if message contains "bingo" and an emoji
    if "bingo" in message_lower:
        # ...existing code for bingo celebration...
        user_emoji = player_emojis.get(user.id)
        message_emoji = extract_emoji(message)
        
        print(f"[BINGO] {user.username} said 'bingo' with emoji: {message_emoji}, their registered emoji is: {user_emoji}")
        
        # Check if the emoji matches their registration emoji
        if message_emoji and message_emoji == user_emoji:
            print(f"[BINGO] {user.username}'s emoji matches their registration - recording bingo")
            
            # Add to round tracking for auto-ping feature
            round_bingos.add(user.id)
            
            # Record timestamp for this bingo call
            current_time = asyncio.get_event_loop().time()
            bingo_timestamps[user.id] = current_time
            
            # Check if user is in a team
            team_num = None
            for t_num, user_ids in teams.items():
                if user.id in user_ids:
                    team_num = t_num
                    break
                    
            if team_num:
                # Team celebration logic
                if team_num not in team_celebrations:
                    team_celebrations[team_num] = []
                
                # Add to team round tracking
                if team_num not in team_round_bingos:
                    team_round_bingos[team_num] = set()
                team_round_bingos[team_num].add(user.id)
                
                print(f"[BINGO] Added {user.username} to team {team_num} bingos: {team_round_bingos[team_num]}")
                
                if user.id not in team_celebrations[team_num]:
                    team_celebrations[team_num].append(user.id)
                    
                if len(team_celebrations[team_num]) == 1:
                    # First team member said bingo
                    await bot.highrise.chat(f"{user.username} says BINGO {user_emoji}! Waiting for their teammate!")
                elif len(team_celebrations[team_num]) == 2:
                    # Both team members said bingo - record team completion timestamp
                    team_bingo_timestamps[team_num] = asyncio.get_event_loop().time()
                    
                    team_members = []
                    for uid in teams[team_num]:
                        for u in emoji_users.get(player_emojis.get(uid, ""), []):
                            if u.id == uid:
                                team_members.append(f"{u.username}")
                                break
                                
                    await bot.highrise.chat(f"🎉 Team {team_num} ({' & '.join(team_members)}) {user_emoji} got BINGO! 🎉")
                    
                    # Start celebration loop
                    celebrating = True
                    continue_celebration = True
                    asyncio.create_task(celebration_loop(bot, user, team_num=team_num))
            else:
                # Individual player celebration
                if user.id not in player_celebrations:
                    player_celebrations.add(user.id)
                    await bot.highrise.chat(f"🎉 {user.username} {user_emoji} got BINGO! 🎉")
                    
                    # Start celebration loop
                    celebrating = True 
                    continue_celebration = True
                    asyncio.create_task(celebration_loop(bot, user))
            
            # IMPORTANT: Always check for last players immediately after recording a bingo
            print(f"[BINGO] Checking for last players immediately after {user.username} said bingo")
            await check_for_last_players(bot)
        else:
            print(f"[BINGO] {user.username}'s emoji {message_emoji} doesn't match their registration emoji {user_emoji}")

# Split the player response functions to avoid complexity
async def handle_player_gg(bot, user, label, user_team):
    global player_revs, players, player_labels, ping_tasks, pinged_players
    global teams, emoji_users, player_emojis, team_emojis, auto_ping_task
    global game_ended
    
    await bot.highrise.chat(f"{user.username} says GG and is out of the game!")
    
    # Show sad emote to indicate loss
    try:
        await bot.highrise.send_emote("emote-sad", user.id)
    except Exception as e:
        print(f"[BINGO] Error sending sad emote: {e}")
    
    # Handle team case - if in a team, make teammate individual player
    if user_team is not None:
        # Find the teammate who will become an individual player
        teammate_id = next((uid for uid in teams[user_team] if uid != user.id), None)
        
        if teammate_id:
            # Find the teammate user object
            teammate = None
            user_emoji = player_emojis.get(user.id)
            if user_emoji and user_emoji in emoji_users:
                for u in emoji_users[user_emoji]:
                    if u.id == teammate_id:
                        teammate = u
                        break
            
            if teammate:
                # Add teammate to individual players if not already there
                if teammate not in players:
                    players.append(teammate)
                
                # Notify about team change
                await bot.highrise.chat(f"Team {user_team} has been split. {user.username} is out, {teammate.username} continues as an individual player.")
        
        # Remove team
        del teams[user_team]
        
        # Clean up team-specific pingings
        for i in range(2):  # Check both potential team member task IDs
            task_label = user_team * 100 + i
            if task_label in ping_tasks:
                ping_tasks[task_label].cancel()
                del ping_tasks[task_label]
    
    # Remove individual player if applicable
    if user in players:
        players.remove(user)
    
    # Clean up player data
    if user.id in player_revs:
        del player_revs[user.id]
    if label in player_labels:
        del player_labels[label]
    
    # Clean up emoji_users entries
    user_emoji = player_emojis.get(user.id)
    if user_emoji and user_emoji in emoji_users:
        emoji_users[user_emoji] = [u for u in emoji_users[user_emoji] if u.id != user.id]
        if not emoji_users[user_emoji]:
            del emoji_users[user_emoji]
        elif user_emoji in team_emojis and user_team is None:  # Only cleanup team_emojis if not already handled
            del team_emojis[user_emoji]
    
    if user.id in player_emojis:
        del player_emojis[user.id]
    
    # Cancel ping task if exists
    if label in ping_tasks:
        ping_tasks[label].cancel()
        del ping_tasks[label]
    pinged_players.discard(user.id)
    
    # Remove from round tracking for auto-ping
    if user.id in round_bingos:
        round_bingos.remove(user.id)
    
    # Cancel auto-ping task if this player/team was the last one
    if auto_ping_task and not auto_ping_task.done():
        auto_ping_task.cancel()
        auto_ping_task = None
    
    # Teleport the player to the top level
    try:
        await bot.highrise.teleport(user_id=user.id,
                                   dest=Position(float(13), float(12),
                                               float(29)))
    except Exception as e:
        print(f"Error teleporting player: {e}")
        # Add fallback message if teleportation fails
        await bot.highrise.send_whisper(user.id, "Please hit the spikes in front of you to exit the playing area. Thank you!")
    
    # IMPORTANT: Check if we have a winner BEFORE checking for last players
    # This ensures we immediately declare a winner when only one player/team remains
    print(f"[BINGO] Checking for winner after {user.username} left...")
    remaining_count = len(player_labels) + len(teams)
    print(f"[BINGO] Remaining players/teams: {remaining_count}")
    
    if remaining_count == 1:
        # We have a winner! Declare them immediately
        await declare_winner(bot)
        return True
    elif remaining_count == 0:
        # No players left - game over with no winner
        await bot.highrise.chat("Game over! No players remaining.")
        await reset_game()
        return True
    
    # If we didn't find a winner, continue with normal flow
    await check_for_last_players(bot)
    return False

# Similar changes to handle_player_rev function
async def handle_player_rev(bot, user, label, user_team):
    global player_revs, players, player_labels, ping_tasks, pinged_players
    global teams, emoji_users, player_emojis, team_emojis, auto_ping_task
    global game_ended
    
    if user.id in player_revs and player_revs[user.id] > 0:
        player_revs[user.id] -= 1
        await bot.highrise.chat(f"{user.username} used a rev! {player_revs[user.id]} revs left.")
        
        # Check if out of revs
        if player_revs[user.id] == 0:
            await bot.highrise.chat(f"{user.username} is out of revs!")
            
            # Handle team case - if in a team, make teammate individual player
            if user_team is not None:
                # Find the teammate who will become an individual player
                teammate_id = next((uid for uid in teams[user_team] if uid != user.id), None)
                
                if teammate_id:
                    # Find the teammate user object
                    teammate = None
                    user_emoji = player_emojis.get(user.id)
                    if user_emoji and user_emoji in emoji_users:
                        for u in emoji_users[user_emoji]:
                            if u.id == teammate_id:
                                teammate = u
                                break
                    
                    if teammate:
                        # Add teammate to individual players if not already there
                        if teammate not in players:
                            players.append(teammate)
                        
                        # Notify about team change
                        await bot.highrise.chat(f"Team {user_team} has been split. {user.username} is out of revs, {teammate.username} continues as an individual player.")
                
                # Remove team
                del teams[user_team]
                
                # Clean up team-specific pingings
                for i in range(2):  # Check both potential team member task IDs
                    task_label = user_team * 100 + i
                    if task_label in ping_tasks:
                        ping_tasks[task_label].cancel()
                        del ping_tasks[task_label]
            
            # Remove individual player if applicable
            if user in players:
                players.remove(user)
            
            # Clean up player data
            if user.id in player_revs:
                del player_revs[user.id]
            if label in player_labels:
                del player_labels[label]
            
            # Clean up emoji_users entries
            user_emoji = player_emojis.get(user.id)
            if user_emoji and user_emoji in emoji_users:
                emoji_users[user_emoji] = [u for u in emoji_users[user_emoji] if u.id != user.id]
                if not emoji_users[user_emoji]:
                    del emoji_users[user_emoji]
                elif user_emoji in team_emojis and user_team is None:  # Only cleanup team_emojis if not already handled
                    del team_emojis[user_emoji]
            
            if user.id in player_emojis:
                del player_emojis[user.id]
            
            # Cancel ping task if exists
            if label in ping_tasks:
                ping_tasks[label].cancel()
                del ping_tasks[label]
            pinged_players.discard(user.id)
            
            # Remove from round tracking for auto-ping
            if user.id in round_bingos:
                round_bingos.remove(user.id)
            
            # Cancel auto-ping task if this player/team was the last one
            if auto_ping_task and not auto_ping_task.done():
                auto_ping_task.cancel()
                auto_ping_task = None
            
            # Teleport the player to the top level (same as gg)
            try:
                await bot.highrise.teleport(user_id=user.id,
                                          dest=Position(float(13), float(12),
                                                      float(29)))
            except Exception as e:
                print(f"Error teleporting player: {e}")
                # Add fallback message if teleportation fails
                await bot.highrise.send_whisper(user.id, "Please hit the spikes in front of you to exit the playing area. Thank you!")
            
            # IMPORTANT: Check if we have a winner BEFORE checking for last players
            print(f"[BINGO] Checking for winner after {user.username} ran out of revs...")
            remaining_count = len(player_labels) + len(teams)
            print(f"[BINGO] Remaining players/teams: {remaining_count}")
            
            if remaining_count == 1:
                # We have a winner! Declare them immediately
                await declare_winner(bot)
                return True
            elif remaining_count == 0:
                # No players left - game over with no winner
                await bot.highrise.chat("Game over! No players remaining.")
                await reset_game()
                return True
            
            # If we didn't find a winner, continue with normal flow
            await check_for_last_players(bot)
            return False
    
    else:
        await bot.highrise.chat(f"{user.username} has no revs left! Say 'gg' to leave the game.")

# Create a dedicated function for winner declaration
async def declare_winner(bot):
    global player_labels, teams, player_emojis, emoji_users, game_ended
    
    game_ended = True
    print("[BINGO] Declaring winner and ending game")
    
    # Find the winner
    if player_labels:
        winner = next(iter(player_labels.values()))
        winner_emoji = player_emojis.get(winner.id, "")
        await bot.highrise.chat(f"🏆 GAME OVER! We have a winner! {winner.username} {winner_emoji} is the last player standing! 🎉")
        
        # Send celebration emotes to winner
        try:
            for _ in range(3):
                await bot.highrise.send_emote("emoji-celebrate", winner.id)
                await asyncio.sleep(1)
        except Exception as e:
            print(f"[BINGO] Error sending celebration to winner: {e}")
            
    elif teams:
        team_num = next(iter(teams.keys()))
        team_members = []
        team_emoji = ""
        for uid in teams[team_num]:
            for user in emoji_users.get(player_emojis.get(uid, ""), []):
                if user.id == uid:
                    team_members.append(f"{user.username}")
                    team_emoji = player_emojis.get(uid, "")
                    
                    # Send celebration emotes to team members
                    try:
                        for _ in range(3):
                            await bot.highrise.send_emote("emoji-celebrate", uid)
                            await asyncio.sleep(1)
                    except Exception as e:
                        print(f"[BINGO] Error sending celebration to team member: {e}")
                        
        await bot.highrise.chat(f"🏆 GAME OVER! We have winners! Team {team_num} ({' & '.join(team_members)}) {team_emoji} is the last team standing! 🎉")
    
    # Since we've already determined the winner, we can reset the game state
    await bot.highrise.chat("The game has ended. Use !record to start a new game!")
    await reset_game()
    return True

# Update check_for_winner to use the declare_winner function
async def check_for_winner(bot):
    global players, teams, player_labels, game_ended
    
    # If game already ended, don't proceed
    if game_ended:
        return False
    
    total_players_teams = len(player_labels) + len(teams)
    print(f"[BINGO] Checking for winner: {total_players_teams} players/teams left")
    
    if total_players_teams == 1:
        return await declare_winner(bot)
    
    return False

# Modify on_user_leave to check for winner
async def handle_user_leave(bot, user):
    global players, player_labels, player_revs, ping_tasks, pinged_players
    global teams, emoji_users, player_emojis, team_emojis, auto_ping_task
    
    # Check if the user was a player in the game
    user_was_player = False
    
    # Check if user is in individual players
    if user in players:
        players.remove(user)
        user_was_player = True
    
    # Check if user is in a team
    user_team = None
    for team_num, user_ids in list(teams.items()):
        if user.id in user_ids:
            user_team = team_num
            user_was_player = True
            
            # Find the teammate who will become an individual player
            teammate_id = next((uid for uid in user_ids if uid != user.id), None)
            
            if teammate_id:
                # Find the teammate user object
                teammate = None
                user_emoji = player_emojis.get(user.id)
                if user_emoji and user_emoji in emoji_users:
                    for u in emoji_users[user_emoji]:
                        if u.id == teammate_id:
                            teammate = u
                            break
                
                if teammate:
                    # Add teammate to individual players
                    if teammate not in players:
                        players.append(teammate)
                    
                    # Notify the room about team change
                    await bot.highrise.chat(f"Team {team_num} has been disbanded because {user.username} left. {teammate.username} is now playing individually.")
            
            # Remove team
            del teams[team_num]
            break
    
    # Clean up player_labels entries
    for label, u in list(player_labels.items()):
        if u.id == user.id:
            del player_labels[label]
            if label in ping_tasks:
                ping_tasks[label].cancel()
                del ping_tasks[label]
    
    # Clean up emoji_users entries
    user_emoji = player_emojis.get(user.id)
    if user_emoji and user_emoji in emoji_users:
        emoji_users[user_emoji] = [u for u in emoji_users[user_emoji] if u.id != user.id]
        if not emoji_users[user_emoji]:
            del emoji_users[user_emoji]
        elif user_emoji in team_emojis:
            del team_emojis[user_emoji]
    
    # Clean up other player data
    if user.id in player_emojis:
        del player_emojis[user.id]
    if user.id in player_revs:
        del player_revs[user.id]
    
    # Clean up ping tasks for team members
    if user_team:
        for i in range(2):  # Check both potential team member task IDs
            task_label = user_team * 100 + i
            if task_label in ping_tasks:
                ping_tasks[task_label].cancel()
                del ping_tasks[task_label]
    
    pinged_players.discard(user.id)
    
    # After cleaning up the player data, check if we have a winner
    if len(player_labels) + len(teams) == 1:
        print(f"[BINGO] Only one player/team left after {user.username} left")
        await declare_winner(bot)
    
    # Return whether the user was a player so the main bot can use this info
    return user_was_player

# Modify check_for_last_players to not ping if only one player/team
async def check_for_last_players(bot):
    global players, teams, round_bingos, team_round_bingos, auto_ping_task, pinged_players
    global bingo_timestamps, team_bingo_timestamps, game_ended
    
    # If game already ended, don't proceed
    if game_ended:
        return
    
    # If there's already an auto-ping task running, cancel it
    if auto_ping_task and not auto_ping_task.done():
        auto_ping_task.cancel()
        auto_ping_task = None
    
    # Log the current state for debugging
    print(f"[BINGO AUTO-PING] Checking for last players...")
    print(f"[BINGO AUTO-PING] Total players: {len(players)}")
    print(f"[BINGO AUTO-PING] Total teams: {len(teams)}")
    print(f"[BINGO AUTO-PING] Players who said bingo: {len(round_bingos)}")
    print(f"[BINGO AUTO-PING] Team bingos: {team_round_bingos}")
    
    # Remove any users who are already being manually pinged 
    # from consideration for auto-pinging
    active_players = [p for p in players if p.id not in pinged_players]
    active_teams = {t_num: members for t_num, members in teams.items() 
                    if not any(uid in pinged_players for uid in members)}
    
    # Check individual players who haven't said bingo
    missing_players = []
    for player in active_players:
        if player.id not in round_bingos:
            missing_players.append(player)
            print(f"[BINGO AUTO-PING] Player {player.username} hasn't said bingo")
    
    # Check teams where not all members have said bingo
    missing_teams = []
    for team_num, user_ids in active_teams.items():
        # Get users who said bingo in this team for this round
        team_bingos = team_round_bingos.get(team_num, set())
        
        # If not all team members said bingo, team is missing
        if len(team_bingos) < len(user_ids):
            missing_teams.append(team_num)
            print(f"[BINGO AUTO-PING] Team {team_num} hasn't fully said bingo. Members said: {team_bingos}")
    
    print(f"[BINGO AUTO-PING] Missing players: {len(missing_players)}")
    print(f"[BINGO AUTO-PING] Missing teams: {len(missing_teams)}")
    
    # First check if we only have one player/team total - if so, declare winner
    total_players_teams = len(player_labels) + len(teams)
    if total_players_teams == 1:
        print("[BINGO AUTO-PING] Only one player/team left in game - declaring winner!")
        await declare_winner(bot)
        return
    
    # If only one player or team left, auto-ping them
    if len(missing_players) == 1 and len(missing_teams) == 0:
        # Auto-ping last individual player
        last_player = missing_players[0]
        print(f"[BINGO AUTO-PING] Auto-pinging last player: {last_player.username}")
        await bot.highrise.chat(f"Only {last_player.username} hasn't said bingo! Auto-pinging...")
        auto_ping_task = asyncio.create_task(auto_ping_player(bot, last_player))
        
    elif len(missing_players) == 0 and len(missing_teams) == 1:
        # Auto-ping last team
        last_team_num = missing_teams[0]
        team_members = []
        team_member_objects = []
        
        # Get team members
        for uid in teams[last_team_num]:
            for emoji, users in emoji_users.items():
                for user in users:
                    if user.id == uid:
                        team_members.append(user.username)
                        team_member_objects.append(user)
                        break
        
        print(f"[BINGO AUTO-PING] Auto-pinging last team: {team_members}")
        await bot.highrise.chat(f"Only Team {last_team_num} ({', '.join(team_members)}) hasn't said bingo! Auto-pinging...")
        
        # Start auto-pinging each team member
        auto_ping_task = asyncio.create_task(auto_ping_team(bot, last_team_num, team_member_objects))
    
    # If everyone said bingo, announce it
    if len(missing_players) == 0 and len(missing_teams) == 0 and (active_players or active_teams):
        print("[BINGO AUTO-PING] Everyone has said bingo! Round complete! 🎉")
        await bot.highrise.chat("Everyone said bingo! Round complete! 🎉")
        
        # Check if we recorded timestamps and find the last one to say bingo
        if bingo_timestamps or team_bingo_timestamps:
            # Combine individual and team timestamps
            all_timestamps = {}
            
            # Add individual player timestamps
            for user_id, timestamp in bingo_timestamps.items():
                all_timestamps[user_id] = {"timestamp": timestamp, "is_team": False}
            
            # Add team timestamps (use the second team member's timestamp as completion time)
            for team_num, timestamp in team_bingo_timestamps.items():
                # Use team number as key with special prefix to avoid collision with user IDs
                team_key = f"team_{team_num}"
                all_timestamps[team_key] = {"timestamp": timestamp, "is_team": True, "team_num": team_num}
            
            # Find the last timestamp
            if all_timestamps:
                last_bingo = max(all_timestamps.items(), key=lambda x: x[1]["timestamp"])
                last_key = last_bingo[0]
                
                # Check if it's a team or individual player
                if last_bingo[1]["is_team"]:
                    team_num = last_bingo[1]["team_num"]
                    
                    # Get team members
                    team_members = []
                    team_member_objects = []
                    for uid in teams[team_num]:
                        for emoji, users in emoji_users.items():
                            for user in users:
                                if user.id == uid:
                                    team_members.append(user.username)
                                    team_member_objects.append(user)
                                    break
                    
                    await bot.highrise.chat(f"Team {team_num} ({', '.join(team_members)}) was the last to say bingo! You lose this round!")
                    
                    # Start pinging team as losers
                    for i, member in enumerate(team_member_objects):
                        # Use team_num*100+i as unique task label
                        task_label = team_num * 100 + i
                        if task_label not in ping_tasks:
                            ping_tasks[task_label] = asyncio.create_task(
                                ping_player(bot, member, f"t{team_num}")
                            )
                        pinged_players.add(member.id)
                else:
                    # Find user from ID
                    for p in players:
                        if p.id == last_key:
                            await bot.highrise.chat(f"{p.username} was the last to say bingo! You lose this round!")
                            
                            # Find label for player
                            label = None
                            for l, u in player_labels.items():
                                if u.id == p.id:
                                    label = l
                                    break
                            
                            # Start pinging player as loser
                            if label not in ping_tasks:
                                ping_tasks[label] = asyncio.create_task(
                                    ping_player(bot, p, label)
                                )
                            pinged_players.add(p.id)
                            break
        
        # Clear timestamps for next round
        bingo_timestamps.clear()
        team_bingo_timestamps.clear()
    
    print(f"[BINGO AUTO-PING] Multiple players/teams still need to say bingo: {len(missing_players)} players, {len(missing_teams)} teams")

# Celebration emote loop
async def celebration_loop(bot, user, team_num=None):
    global continue_celebration
    
    try:
        while continue_celebration:
            if team_num:
                # Celebrate with all team members
                for uid in teams.get(team_num, []):
                    try:
                        await bot.highrise.send_emote("emoji-celebrate", uid)
                    except Exception as e:
                        print(f"Error sending celebration to team member: {e}")
            else:
                # Celebrate with individual user
                await bot.highrise.send_emote("emoji-celebrate", user.id)
                
            # Wait before next celebration
            await asyncio.sleep(5)
    except Exception as e:
        print(f"Error in celebration loop: {e}")
        continue_celebration = False

# To use:
# - In on_whisper: await play_bingo(bot, user.id, message); await handle_player_response(bot, user, message)
# - In on_chat: await handle_bingo_celebration(bot, user, message)
# - In on_user_leave: await handle_user_leave(bot, user)
# - In on_tip: await handle_player_tip(bot, sender, receiver, tip)
