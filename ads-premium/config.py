cat << 'EOF' > config.py
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Nayi API ID aur API Hash
API_ID = 27862122
API_HASH = "8e770d6182496162316bb773cc5b69e5"

CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PREMIUM_PRICE = 400
EOF
