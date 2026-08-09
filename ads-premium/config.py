import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Pyrogram Credentials
API_ID = 31497463
API_HASH = "4184eadf303c31ea114ab8cbc3f02478"

CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PREMIUM_PRICE = 400
