import os

from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# BOT SETTINGS
# ============================================================

BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    ""
).strip()

BOT_USERNAME = os.getenv(
    "BOT_USERNAME",
    ""
).strip()


# ============================================================
# TELETHON API
# ============================================================

API_ID_RAW = os.getenv(
    "35596674",
    ""
).strip()

API_HASH = os.getenv(
    "65e7dd5ec043ae33cf2d51d3b1a37adc",
    ""
).strip()


try:
    API_ID = int(API_ID_RAW)

except (TypeError, ValueError):

    API_ID = 0


# ============================================================
# ADMIN
# ============================================================

ADMIN_ID_RAW = os.getenv(
    "ADMIN_ID",
    ""
).strip()


try:
    ADMIN_ID = int(ADMIN_ID_RAW)

except (TypeError, ValueError):

    ADMIN_ID = 0


ADMIN_CONTACT_USERNAME = os.getenv(
    "ADMIN_CONTACT_USERNAME",
    ""
).strip()


# ============================================================
# FORCE JOIN CHANNEL
# ============================================================

FORCE_CHANNEL_USERNAME = os.getenv(
    "FORCE_CHANNEL_USERNAME",
    ""
).strip()


# ============================================================
# VALIDATION
# ============================================================

if not BOT_TOKEN:

    print(
        "⚠️ WARNING: BOT_TOKEN is not configured."
    )


if not API_ID:

    print(
        "⚠️ WARNING: API_ID is not configured."
    )


if not API_HASH:

    print(
        "⚠️ WARNING: API_HASH is not configured."
    )


if not ADMIN_ID:

    print(
        "⚠️ WARNING: ADMIN_ID is not configured."
    )
