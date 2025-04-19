from highrise import BaseBot, __main__, CurrencyItem, Item, Position, AnchorPosition, SessionMetadata, User
from highrise.__main__ import BotDefinition
from asyncio import run as arun
from json import load, dump
import asyncio
import os
from highrise.models import *
from highrise.webapi import *
import importlib.util
from loop_emote import send_specific_emote_periodically, stop_emote_task
from getItems import getclothes, getCommands
# from webserver import keep_alive
# Add import for play_bingo
from functions import play_bingo

emotesava = [
    "emote-kiss", "emote-no", "emote-sad", "emote-yes", "emote-laughing",
    "emote-hello", "emote-wave", "emote-shy", "emote-tired", "emoji-angry",
    "idle-loop-sitfloor", "emoji-thumbsup", "emote-lust", "emoji-cursing",
    "emote-greedy", "emoji-flex", "emoji-gagging", "emoji-celebrate",
    "dance-macarena", "dance-tiktok8", "dance-blackpink", "emote-model",
    "dance-tiktok2", "dance-pennywise", "emote-bow", "dance-russian",
    "emote-curtsy", "emote-snowball", "emote-hot", "emote-snowangel",
    "emote-charging", "dance-shoppingcart", "emote-confused",
    "idle-enthusiastic", "emote-telekinesis", "emote-float",
    "emote-teleporting", "emote-swordfight", "emote-maniac",
    "emote-energyball", "emote-snake", "idle_singing", "emote-frog",
    "emote-superpose", "emote-cute", "dance-tiktok9", "dance-weird",
    "dance-tiktok10", "emote-pose7", "emote-pose8", "idle-dance-casual",
    "emote-pose1", "emote-pose3", "emote-pose5", "emote-cutey",
    "emote-punkguitar", "emote-zombierun", "emote-fashionista",
    "emote-gravity", "dance-icecream", "dance-wrong", "idle-uwu",
    "idle-dance-tiktok4"
]

vip_users = []

commds = [
    'allemo',
    'emo',
    'emote',
    'equip',
    'funfact',
    'remove',
    'userinfo',
    'loop',
    'teleport',
    'stop',
    'kick',
    'move',
    'commands',
    'bot commands',
    '!allemo',
    'everyemo',
    'categories',
]


class Bot(BaseBot):

  def __init__(self):
    super().__init__()
    self.bot_id = None
    self.owner_id = None
    self.bot_status = False
    self.tip_data = {}
    self.load_tip_data()
    self.bot_position = None
    self.dice_interval = 3  # default
    self.dice_task = None


  async def on_chat(self, user: User, message: str) -> None:
    response = await self.command_handler(user.id, message)
    if response:
        await self.highrise.chat("Room users fetched successfully.")
    lowerMsg = message.lower()
    response = await self.highrise.get_room_users()
    if hasattr(response, 'content'):
        if isinstance(response, GetRoomUsersRequest.GetRoomUsersResponse):
            roomUsers = response.content
        else:
            await self.highrise.chat("Failed to fetch room users.")
            return
    else:
        await self.highrise.chat("Failed to fetch room users.")
        return
      
    # Add bingo celebration handler - this now also handles 'gg' and 'rev' commands
    await play_bingo.handle_bingo_celebration(self, user, message)

  async def on_emote(self, user: User, emote_id: str,
                     receiver: User | None) -> None:
    pass

  async def on_whisper(self, user: User, message: str) -> None:
    # Play bingo join/command handler
    await play_bingo.play_bingo(self, user.id, message)
    # Play bingo player response handler
    await play_bingo.handle_player_response(self, user, message)
    response = await self.command_handler(user.id, message)
    if response:
      try:
        await self.highrise.send_whisper(user.id, response)
      except Exception as e:
        await self.highrise.chat(f"Whisper Error: {e}")

  async def on_message(self, user_id: str, conversation_id: str,
                       is_new_conversation: bool) -> None:
    response = await self.highrise.get_messages(conversation_id)
    message = ""  # Initialize message with a default value
    if isinstance(response, GetMessagesRequest.GetMessagesResponse):
      message = response.messages[0].content
    user = None
    try:
      # Fetch user object for permission checks
      room_users_resp = await self.highrise.get_room_users()
      if isinstance(room_users_resp, GetRoomUsersRequest.GetRoomUsersResponse):
        user_tuple = next((u for u in room_users_resp.content if u[0].id == user_id), None)
        if user_tuple:
          user = user_tuple[0]
      if message.lower() == "!equip help" or message.lower() == "equip":
        if user_id == self.owner_id:
          await self.highrise.send_message(
              conversation_id, f"Equip Help 🆘: {getclothes('help')}")
        else:
          await self.highrise.send_message(
              conversation_id,
              f"Sorry, you don't have access to this command")

      elif message.lower() == "eq h":
        response = await self.highrise.get_room_users()
        if isinstance(response, GetRoomUsersRequest.GetRoomUsersResponse):
            user_tuple = next((u for u in response.content if u[0].id == user_id), None)
            if user_tuple:
              user = user_tuple[0]
            else:
              user = None
        else:
            await self.highrise.chat("Failed to fetch room users.")
            user = None
        if not user:
          await self.highrise.send_message(
              conversation_id,
              "User information could not be retrieved.")
          return
        if user_id == self.owner_id:
          await self.highrise.send_message(
              conversation_id,
              f"Here are the list of Hairs 👱‍♂️: {getclothes('hair')}")
          await self.highrise.send_message(
              conversation_id,
              f"\n\nUsage ⌨: Type !equip <hairname> in the room to equip / !remove <hairname> in the room to remove \n Note that the names are case sensitive"
          )
        else:
          await self.highrise.send_message(
              conversation_id,
              f"Sorry {user.username}, you don't have access to this command")

      elif message.lower() == "eq t":
        if user_id == self.owner_id:
          await self.highrise.send_message(
              conversation_id,
              f"Here are the list of Shirts 🎽: {getclothes('top')}")
          await self.highrise.send_message(
              conversation_id,
              f"\n\nUsage ⌨: Type !equip <topname> in the room to equip / !remove <topname> in the room to remove \n Note that the names are case sensitive"
          )
        else:
          await self.highrise.send_message(
              conversation_id,
              f"Sorry {user.username}, you don't have access to this command")

      elif message.lower() == "eq p":
        if user_id == self.owner_id:
          await self.highrise.send_message(
              conversation_id,
              f"Here are the list of Pants 👖: {getclothes('pant')}")
          await self.highrise.send_message(
              conversation_id,
              f"\n\nUsage ⌨: Type !equip <pantname> in the room to equip / !remove <pantname> in the room to remove \n Note that the names are case sensitive"
          )
        else:
          await self.highrise.send_message(
              conversation_id,
              f"Sorry {user.username}, you don't have access to this command")

      elif message.lower() == "eq s":
        if user_id == self.owner_id:
          await self.highrise.send_message(
              conversation_id,
              f"Here are the list of Skirts 🩳: {getclothes('skirt')}")
          await self.highrise.send_message(
              conversation_id,
              f"\n\nUsage ⌨: Type !equip <skirtname> in the room to equip / !remove <skirtname> in the room to remove \n Note that the names are case sensitive"
          )
        else:
          await self.highrise.send_message(
              conversation_id,
              f"Sorry {user.username}, you don't have access to this command")

      elif message.lower() == "eq sh":
        if user_id == self.owner_id:
          await self.highrise.send_message(
              conversation_id,
              f"Here are the list of Shoes 👟: {getclothes('shoe')}")
          await self.highrise.send_message(
              conversation_id,
              f"\n\nUsage ⌨: Type !equip <shoename> in the room to equip / !remove <shoename> in the room to remove \n Note that the names are case sensitive"
          )
        else:
          await self.highrise.send_message(
              conversation_id,
              f"Sorry {user.username}, you don't have access to this command")

      elif message.lower() == "eq b":
        if user_id == self.owner_id:
          await self.highrise.send_message(
              conversation_id,
              f"Back hair 👱‍♂️:'Short Short Fro', 'Box Braids', 'Long Undercut Dreads', 'Undercut Dreads', 'Side Swept Fro', 'Long Buzzed Fro', 'Short Buzzed Fro', 'Curly Undercut', 'Tight Curls', 'Loose Curls', 'Shaggy Curls', 'Short Curls', 'Medium Wavy Cut', 'Short Wavy Cut', 'Wavy Undercut', 'Wavy Side Part', 'Shaggy Side Part', 'Combed Back Waves', 'Blown Back Waves', 'Short Straight', 'Side Combed Straight', 'Straight Slicked Back', 'Buzz Cut', 'Shaggy Crew Cut', 'Faux Hawk', 'Shaggy Straight', 'Straight Side Part', 'Combed Back Undercut', 'Upward Swoosh', 'Side Swept Undercut', 'Side Swept', 'Crew Cut', 'Over Shoulder Wavy Short', 'Over Shoulder Wavy Long', 'Over Shoulder Straight Short', 'Over Shoulder Straight Bangs', 'Over Shoulder Straight Long', 'Over Shoulder Pony', 'Over Shoulder Curly', 'Over Shoulder Coily', 'Over Shoulder Braid'"
          )
          await self.highrise.send_message(
              conversation_id,
              f"\n'Wavy Long Bob', 'Sweet Curl Waves', 'Poofy Bob', 'Short Beach Waves', 'Long Beach Waves', 'Long Glamour Waves', 'Chunky Waves', 'Wavy Short', 'Wavy Medium', 'Wavy Low Pony', 'Wavy High Pony', 'Wavy Pixie', 'Wavy Long', 'Top Knot Back', 'Straight Short Low Pigtails', 'Straight Short High Pigtails', 'Straight Short', 'Straight Medium', 'Straight Low Pony', 'Straight Long Low Pigtails', 'Straight Long', 'Straight High Pony', 'Straight Pixie', 'Sleek Straight Pony', 'Sleek Straight Medium', 'Sleek Straight Long', 'Sleek Straight Short', 'Bettie Waves', 'Marilyn Curls', 'Loose Coily Short', 'Loose Coily Medium', 'Loose Coily Long', 'Long Wavy Half Bun', 'Half Pony', 'Dreads Medium', 'Dreads Low Pony', 'Dreads Long', 'Dreads High Pony', 'Dreads Extra Short', 'Dreads Short', 'Double Top Knots Back', 'Low Double Buns', 'Curly Short Low Pigtails', 'Curly Short High Pigtails', 'Curly No Bangs Back', 'Curly Medium', 'Curly Low Pony', 'Curly Long High Pigtails', 'Curly Long', 'Curly High Pony', 'Curly Pixie', 'Coily Short', 'Coily Pinapple Hair', 'Coily Medium', 'Coily Low Pony', 'Coily Long', 'Coily High Pony', 'Bald', 'Low Bun', 'High Bun', 'Afro Short', 'Afro Pom Poms Back', 'Afro Medium', 'Afro Long', 'Afro High Pony'"
          )
        else:
          await self.highrise.send_message(
              conversation_id,
              f"Sorry {user.username}, you don't have access to this command")

      elif message.lower() == "eq so":
        if user_id == self.owner_id:
          await self.highrise.send_message(
              conversation_id,
              f"Here are the list of Sock 🧦: {getclothes('sock')}")
          await self.highrise.send_message(
              conversation_id,
              f"\n\nUsage ⌨: Type !equip <sockname> in the room to equip / !remove <sockname> in the room to remove \n Note that the names are case sensitive"
          )
        else:
          await self.highrise.send_message(
              conversation_id,
              f"Sorry {user.username}, you don't have access to this command")

      elif message.lower() == "eq a":
        if user_id == self.owner_id:
          await self.highrise.send_message(
              conversation_id,
              f"Here are the list of Accesories 🧣: {getclothes('assec')}")
          await self.highrise.send_message(
              conversation_id,
              f"\n\nUsage ⌨: Type !equip <assessoriesname> in the room to equip / !remove <assessoriesname> in the room to remove \n Note that the names are case sensitive"
          )
        else:
          await self.highrise.send_message(
              conversation_id,
              f"Sorry {user.username}, you don't have access to this command")
        # new ones
      elif message.lower() == "eq fh":
        if user_id == self.owner_id:
          await self.highrise.send_message(
              conversation_id,
              f"Here are the list of Face hairs 👱‍♀️: {getclothes('face')}")
          await self.highrise.send_message(
              conversation_id,
              f"\n\nUsage ⌨: Type !equip <facehairname> in the room to equip / !remove <facehairname> in the room to remove \n Note that the names are case sensitive"
          )
        else:
          await self.highrise.send_message(
              conversation_id,
              f"Sorry {user.username}, you don't have access to this command")

      elif message.lower() == "eq eb":
        if user_id == self.owner_id:
          await self.highrise.send_message(
              conversation_id,
              f"Here are the list of Eyebrows 👁‍🗨: {getclothes('eyebrow')}")
          await self.highrise.send_message(
              conversation_id,
              f"\n\nUsage ⌨: Type !equip <eyebrowname> in the room to equip / !remove <eyebrowname> in the room to remove \n Note that the names are case sensitive"
          )
        else:
          await self.highrise.send_message(
              conversation_id,
              f"Sorry {user.username}, you don't have access to this command")

      elif message.lower() == "eq e":
        if user_id == self.owner_id:
          await self.highrise.send_message(
              conversation_id,
              f"Here are the list of Eyes 👁: {getclothes('eye')}")
          await self.highrise.send_message(
              conversation_id,
              f"\n\nUsage ⌨: Type !equip <eyename> in the room to equip / !remove <eyename> in the room to remove \n Note that the names are case sensitive"
          )
        else:
          await self.highrise.send_message(
              conversation_id,
              f"Sorry {user.username}, you don't have access to this command")

      elif message.lower() == "eq n":
        if user_id == self.owner_id:
          await self.highrise.send_message(
              conversation_id,
              f"Here are the list of Noses 👃: {getclothes('nose')}")
          await self.highrise.send_message(
              conversation_id,
              f"\n\nUsage ⌨: Type !equip <nosename> in the room to equip / !remove <nosename> in the room to remove \n Note that the names are case sensitive"
          )
        else:
          await self.highrise.send_message(
              conversation_id,
              f"Sorry {user.username}, you don't have access to this command")

      elif message.lower() == "eq m":
        if user_id == self.owner_id:
          await self.highrise.send_message(
              conversation_id,
              f"Here are the list of Mouth 👄: {getclothes('mouth')}")
          await self.highrise.send_message(
              conversation_id,
              f"\n\nUsage ⌨: Type !equip <mouthname> in the room to equip / !remove <mouthname> in the room to remove \n Note that the names are case sensitive"
          )
        else:
          await self.highrise.send_message(
              conversation_id,
              f"Sorry {user.username}, you don't have access to this command")

      elif message.lower() == "eq fr":
        if user_id == self.owner_id:
          await self.highrise.send_message(
              conversation_id,
              f"Here are the list of Freckles ☺: {getclothes('freckle')}")
          await self.highrise.send_message(
              conversation_id,
              f"\n\nUsage ⌨: Type !equip <frecklename> in the room to equip / !remove <frecklename> in the room to remove \n Note that the names are case sensitive"
          )
        else:
          await self.highrise.send_message(
              conversation_id,
              f"Sorry {user.username}, you don't have access to this command")

      elif message.lower() == "evemo":
        if user_id == self.owner_id:
          await self.highrise.send_message(
              conversation_id,
              f"All emotes 👯‍♂️ : 'sit-idle-cute'  'idle_zombie'  'idle_layingdown2'  'idle_layingdown'  'idle-sleep'  'idle-sad'  'idle-posh'  'idle-loop-tired'  'idle-loop-tapdance'  'idle-loop-sitfloor'  'idle-loop-shy'  'idle-loop-sad'  'idle-loop-happy'  'idle-loop-annoyed'  'idle-loop-aerobics'  'idle-lookup'  'idle-hero'  'idle-floorsleeping2'  'idle-floorsleeping'  'idle-enthusiastic'  'idle-dance-swinging'  'idle-dance-headbobbing'  'idle-angry'  'emote-yes'  'emote-wings'  'emote-wave'  'emote-tired'  'emote-think'  'emote-theatrical'  'emote-tapdance'  'emote-superrun'  'emote-superpunch 'emote-sumo'  'emote-suckthumb'  'emote-splitsdrop'  'emote-snowball'  'emote-snowangel'  'emote-shy'  'emote-secrethandshake'  'emote-sad'  'emote-ropepull'  'emote-roll'  'emote-rofl'  'emote-robot'  'emote-rainbow'  'emote-proposing'  'emote-peekaboo'  'emote-peace'  'emote-panic'  'emote-no'  'emote-ninjarun'  'emote-nightfever'  'emote-monster_fail'  'emote-model'  'emote-lust'  'emote-levelup'  'emote-laughing2'  'emote-laughing'  'emote-kiss'  'emote-kicking'  'emote-jumpb'  'emote-judochop'  'emote-jetpack'  'emote-hugyourself"
          )
          await self.highrise.send_message(
              conversation_id,
              f"'emote-hot'  'emote-hero'  'emote-hello'  'emote-headball'  'emote-harlemshake'  'emote-happy'  'emote-handstand'  'emote-greedy'  'emote-graceful'  'emote-gordonshuffle' 'emote-ghost-idle'  'emote-gangnam'  'emote-frollicking'  'emote-fainting'  'emote-fail2'  'emote-fail1'  'emote-exasperatedb'  'emote-exasperated'  'emote-elbowbump'  'emote-disco'  'emote-disappear'  'emote-deathdrop'  'emote-death2'  'emote-death'  'emote-dab'  'emote-curtsy'  'emote-confused'  'emote-cold'  'emote-charging'  'emote-bunnyhop'  'emote-bow'  'emote-boo'  'emote-baseball'  'emote-apart'  'emoji-thumbsup'  'emoji-there'  'emoji-sneeze'  'emoji-smirking'  'emoji-sick'  'emoji-scared'  'emoji-punch'  'emoji-pray'  'emoji-poop'  'emoji-naughty'  'emoji-mind-blown'  'emoji-lying'  'emoji-halo'  'emoji-hadoken'  'emoji-give-up'  'emoji-gagging'  'emoji-flex'  'emoji-dizzy'  'emoji-cursing'  'emoji-crying'  'emoji-clapping'  'emoji-celebrate'  'emoji-arrogance'  'emoji-angry'  'dance-voguehands'  'dance-tiktok8'  'dance-tiktok2'  'dance-spiritual'  'dance-smoothwalk'  'dance-singleladies'  'dance-shoppingcart'  'dance-russian'  'dance-robotic'  'dance-pennywise'  'dance-orangejustice'  'dance-metal'  'dance-martial-artist'  'dance-macarena'  'dance-handsup'  'dance-floss'  'dance-duckwalk'  'dance-breakdance'  'dance-blackpink'  'dance-aerobics'"
          )
          await self.highrise.send_message(
              conversation_id,
              f"\n\nHere are the lists of all emotes in the normal emote name, useful for when you want to buy emotes for your bot that users can use [use !buy <itemname> in room to buy any of the unavailable ones].. To see emotes available for use instead, enter !allemo "
          )
          await self.highrise.send_message(
              conversation_id,
              f"\n\nEnter the last word of any of these emote in the room to check if they are free/available e.g to use the 'emoji-flex', type flex in the room \n\n To buy unavailale ones !equip <emotename> in the room to equip / !remove <emotename> in the room to remove \n Note that the names are case sensitive"
          )
        else:
          await self.highrise.send_message(
              conversation_id, f"Sorry, you don't have access to this command")

      elif message.lower().startswith("help"):
        await self.highrise.send_message(
            conversation_id,
            f"Good day ☺, what can i help you with? : {getCommands('help')}")

      elif message.lower() in commds:
        await self.highrise.send_message(
            conversation_id, f"{getCommands(f'{message.lower()}')}")

      elif message.lower().startswith("hi"):
        await self.highrise.send_message(
            conversation_id,
            "Hey, How's your day? ☺ \nTo show you list of available options, type help"
        )

      else:
        await self.highrise.send_message(
            conversation_id,
            f"I can't understand your message, type help for further assistance.."
        )

    except Exception as e:
      await self.highrise.send_message(
          conversation_id,
          f"Sorry, i can't fetch the response for you.. \n Kindly contact @coolbuoy with error code: msg281 if error persists \n\n 📛Error Message {e}"
      )

  # Handle commands from any source (chat/whisper/message)
  async def command_handler(self, user_id, message: str):
    command = message.lower().strip()

    if command.startswith("!set"):
      if user_id != self.owner_id:  # Only listen to host's commands
        return  # Set the bot at your location
      try:
        set_position = await self.set_bot_position(user_id)
        return set_position
      except Exception as e:
        await self.highrise.chat(f"Set Error: {e}")
    elif command.startswith("!top"):
      if user_id != self.owner_id:  # Only listen to host's commands
        return  # Build a 10 top tippers leaderboard
      top_tippers = self.get_top_tippers()
      formatted_tippers = []
      for i, (user_id, user_data) in enumerate(top_tippers):
        username = user_data['username']
        total_tips = user_data['total_tips']
        formatted_tippers.append(f"{i + 1}. {username} ({total_tips}g)")

      tipper_message = '\n'.join(formatted_tippers)
      return f"Top Tippers:\n{tipper_message}"
    elif command.startswith("!get "):
      if user_id != self.owner_id:  # Only listen to host's commands
        return  # Query a specific user's tips
      username = command.split(" ", 1)[1].replace("@", "")
      tip_amount = self.get_user_tip_amount(username)
      if tip_amount is not None:
        return f"{username} se ha inclinado {tip_amount}g"
      else:
        return f"{username} no se ha volcado."
    elif command.startswith("!wallet"):
      if user_id != self.owner_id:  # Only listen to host's commands
        return  # Get Bot wallet gold
      wallet = await self.highrise.get_wallet()
      for currency in wallet.content:
        if currency.type == 'gold':
          gold = currency.amount
          return f"Tengo {gold}g en mi billetera."
      return "No hay oro en la billetera."

    parts = message.split(" ")
    command = parts[0][1:]
    functions_folder = "functions"
    # Check if the function exists in the module
    for file_name in os.listdir(functions_folder):
      if file_name.endswith(".py"):
        module_path = None
        module_name = file_name[:-3]  # Remove the '.py' extension

        if os.path.isfile(os.path.join(functions_folder, file_name)):
          module_path = os.path.join(functions_folder, file_name)
        

        if module_path:
          try:
            # Load the module
            spec = importlib.util.spec_from_file_location(
                module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Check if the function exists in the module
            if hasattr(module, command) and callable(getattr(module, command)):
              function = getattr(module, command)
              await function(self, user_id, message)
              return  # Exit the loop if a matching function is found
          except Exception as e:
            await self.highrise.chat(
                f"Error loading module {module_name}: {str(e)}")

    # If no matching function is found
    return

  async def on_tip(self, sender: User, receiver: User,
                   tip: CurrencyItem | Item) -> None:
    # Handle bingo 5g tip as rev
    if isinstance(tip, CurrencyItem):
      await play_bingo.handle_player_tip(self, sender, receiver, tip.amount)
    if isinstance(tip, CurrencyItem):
      await self.highrise.chat(
          f"{sender.username} tipped {tip.amount}g -> {receiver.username}")
      if receiver.id == self.bot_id:
        if sender.id not in self.tip_data:
          self.tip_data[sender.id] = {
              "username": sender.username,
              "total_tips": 0
          }

        self.tip_data[sender.id]['total_tips'] += tip.amount
        self.write_tip_data(sender, tip.amount)

        if tip.amount >= 100:
          await self.highrise.chat(
              f"{sender.username} Tipped  {tip.amount} for VIP. Teleporting now..."
          )
          #teleports the user to the specified coordinate
          await self.highrise.teleport(user_id=sender.id,
                                       dest=Position(float(15), float(9.1),
                                                     float(12)))

  async def on_user_join(self, user: User,
                         position: Position | AnchorPosition) -> None:
    if user.username == "coolbuoy":
      await self.highrise.react("wave", user.id)
      await self.highrise.chat(
        f"Welcome boss! The BINGO BUOY reporting here..... I am your special bot made by you. We have gathered here today to play what? BINGO!!!!!!!!!!!!!")
    
    
    elif user.username == "User_taken2":
      await self.highrise.react("wave", user.id)
      await self.highrise.chat(
        f"Apologies, i have to acknoledge the Mamacita! It's the beauty's arrival!.  Welcome, Beauty!")
      
      # Else 
    else:
      await self.highrise.react("wave", user.id)
      await self.highrise.chat(
          f"Hiiii It's bingo TIMEEEEE!!!"
      )

  async def on_user_leave(self, user: User) -> None:
    try:
        # Call the handle_user_leave function and get whether the user was a player
        user_was_player = await play_bingo.handle_user_leave(self, user)
        
        if user_was_player:
            await self.highrise.chat(
                f"{user.username} left the game! Hope you had fun playing bingo with us!"
            )
        else:
            await self.highrise.chat(
                f"{user.username} left the room. See you next time!"
            )
            
    except Exception as e:
        print(f"[ERROR] Error in on_user_leave: {e}")
        # Fallback message
        await self.highrise.chat(
            f"{user.username} left the room. See you next time!"
        )

  async def on_start(self, session_metadata: SessionMetadata) -> None:
    self.bot_id = session_metadata.user_id
    self.owner_id = session_metadata.room_info.owner_id
    if self.bot_status:
      await self.place_bot()
    self.bot_status = True

    # Avoid crashing if muted: catch and log mute error, do not raise
    try:
      await self.highrise.chat("Who is ready for a round of bingo! 🎲🤣")
    except Exception as e:
      if "muted" in str(e).lower():
        print(f"[WARN] Bot is muted and cannot chat: {e}")
      else:
        raise
    print("started...")

  # Return the top 10 tippers
  def get_top_tippers(self):
    if not self.tip_data:
        return []
    sorted_tippers = sorted(self.tip_data.items(),
                            key=lambda x: x[1]['total_tips'],
                            reverse=True)
    return sorted_tippers[:10]

  # Return the amount a particular username has tipped
  def get_user_tip_amount(self, username):
    for _, user_data in self.tip_data.items():
      if user_data['username'].lower() == username.lower():
        return user_data['total_tips']
    return None

  # Place bot on start
  async def place_bot(self):
    while self.bot_status is False:
      await asyncio.sleep(0.5)
    try:
      self.bot_position = self.get_bot_position()
      if self.bot_position != Position(0, 0, 0, 'FrontRight'):
        await self.highrise.teleport(self.bot_id, self.bot_position)
        return
    except Exception as e:
      await self.highrise.chat(f"Error with starting position {e}")

  # Write tip event to file
  def write_tip_data(self, user: User, tip: int) -> None:
    with open("./data.json", "r+") as file:
      data = load(file)
      user_data = data["users"].get(user.id, {
          "total_tips": 0,
          "username": user.username
      })
      user_data["total_tips"] += tip
      user_data["username"] = user.username
      data["users"][user.id] = user_data
      file.seek(0)
      dump(data, file)
      file.truncate()

  # Set the bot position at player's location permanently
  async def set_bot_position(self, user_id) -> None:
    position = None
    try:
      room_users = await self.highrise.get_room_users()
      for room_user, pos in room_users.content:
        if user_id == room_user.id:
          if isinstance(pos, Position):
            position = pos

      if position is not None:
        with open("./data.json", "r+") as file:
          data = load(file)
          file.seek(0)
          data["bot_position"] = {
              "x": position.x,
              "y": position.y,
              "z": position.z,
              "facing": position.facing
          }
          dump(data, file)
          file.truncate()
        set_position = Position(position.x, (position.y + 0.0000001),
                                position.z,
                                facing=position.facing)
        await self.highrise.teleport(self.bot_id, set_position)
        await self.highrise.teleport(self.bot_id, position)
        await self.highrise.walk_to(position)
        return "Updated bot position."
      else:
        return "Failed to update bot position."
    except Exception as e:
      await self.highrise.chat(f"Error setting bot position: {e}")

  # Load tip data on start
  def load_tip_data(self) -> None:
    with open("./data.json", "r") as file:
      data = load(file)
      self.tip_data = data["users"]

  # Load bot position from file
  def get_bot_position(self) -> Position:
    with open("./data.json", "r") as file:
      data = load(file)
      pos_data = data["bot_position"]
      return Position(pos_data["x"], pos_data["y"], pos_data["z"],
                      pos_data["facing"])

  async def run_bot(self, room_id, api_key) -> None:
    asyncio.create_task(self.place_bot())
    definitions = [BotDefinition(self, room_id, api_key)]
    await __main__.main(definitions)


# Automatically create json file if not exists
def data_file(filename: str, default_data: str = "{}") -> None:
  if not os.path.exists(filename):
    with open(filename, 'w') as file:
      file.write(default_data)


DEFAULT_DATA = '{"users": {}, "bot_position": {"x": 0, "y": 0, "z": 0, "facing": "FrontRight"}}'
data_file("./data.json", DEFAULT_DATA)

# To run the bot directly (without Flask keep-alive), use:
#   python main.py
# This is recommended for local development and debugging.

# Uncomment below to enable direct execution:
# if __name__ == "__main__":
#   import os
#   from dotenv import load_dotenv
#   load_dotenv()
#   ROOM_ID = os.getenv("ROOM_ID")
#   API_KEY = os.getenv("BOT_TOKEN")
#   arun(Bot().run_bot(ROOM_ID, API_KEY))
