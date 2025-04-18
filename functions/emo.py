from highrise import *
from highrise.models import *
from highrise.webapi import *
from highrise.models_webapi import *
import re, random

emoteshelp = [
    "kiss", "no", "sad", "yes", "laughing", "hello", "wave", "shy", "tired", 
    "angry", "sitfloor", "thumbsup", "lust", "cursing", "greedy", "flex", 
    "gagging", "celebrate", "macarena", "tiktok8", "blackpink", "model", 
    "tiktok2", "pennywise", "bow", "russian", "curtsy", "snowball", "hot", 
    "snowangel", "charging", "shoppingcart", "confused", "enthusiastic", 
    "telekinesis", "float", "teleporting", "swordfight", "maniac", 
    "energyball", "snake", "idle_singing", "frog", "superpose", "cute", 
    "tiktok9", "weird", "tiktok10", "pose7", "pose8", "casual", "pose1", 
    "pose3", "pose5", "cutey", "punkguitar", "zombierun", "fashionista", 
    "gravity", "icecream", "wrong", "uwu", "tiktok4"
]


async def emo(self: BaseBot, user: User, message: str) -> None:
    await self.highrise.chat(f"It's okay, try to say '{random.choice(emoteshelp)}'")