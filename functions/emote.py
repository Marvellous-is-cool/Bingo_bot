from highrise import *
from highrise.models import *
from highrise.webapi import *
from highrise.models_webapi import *

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

async def emote(self: BaseBot, user: User, message: str) -> None:
    try:
        command, target, emote_id = message.split(" ")
    except:
        await self.highrise.chat("Invalid command format. Please use '!emote <target> <emotename>.")
        return
    
    user = (await self.webapi.get_users(username=target))
    if user.total == 0:
        await self.highrise.chat("Invalid target.")
        return
    user_id = user.users[0].user_id
    for emotename in emotesava:
        try:
            if emote_id.startswith(f"{emotename.rsplit('-', 1)[-1]}"):
                await self.highrise.send_emote(emotename, user_id)
            else:
                await self.highrise.chat("invalid gesture. type !emo to give you a suggestion, or !allemo to see all the emotions")
        except Exception as e:
            await self.highrise.chat("invalid gesture.")
            return