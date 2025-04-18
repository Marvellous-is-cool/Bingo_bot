from highrise import *
from highrise.models import *

categories = ["aura","bag","blush","body","dress","earrings","emote","eye","eyebrow","fishing_rod","freckle","fullsuit","glasses",
"gloves","hair_back","hair_front","handbag","hat","jacket","lashes","mole","mouth","necklace","nose","rod","shirt","shoes",
"shorts","skirt","sock","tattoo","watch", "pants"]

async def remove(self: BaseBot, user: User, message: str):
        parts = message.split(" ")
        if len(parts) != 2:
            await self.highrise.chat("Invalid command format. You must specify the category. (message me with remove to help you further)")
            return
        if parts[1] not in categories:
            await self.highrise.chat("Invalid category. (message me with remove to help you further)")
            return
        category = parts[1].lower()
        outfit = (await self.highrise.get_my_outfit()).outfit
        for outfit_item in outfit:
            #the category of the item in an outfit can be found by the first string in the id before the "-" character
            item_category = outfit_item.id.split("-")[0][0:3]
            if item_category == category[0:3]:
                try:
                    outfit.remove(outfit_item)
                except:
                    await self.highrise.chat(f"The bot is not using any elements from the category. '{category}'.")
                    return
        response = await self.highrise.set_outfit(outfit)