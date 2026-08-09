import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Tumhare Telegram channel ka username
# Example: @mychannel
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "")

# Tumhari Telegram numeric ID
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Premium price
PREMIUM_PRICE = 400
