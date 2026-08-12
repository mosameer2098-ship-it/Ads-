import os


# ============================================================
# TELEGRAM BOT
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

BOT_USERNAME = os.getenv(
    "BOT_USERNAME",
    ""
).strip().lstrip("@")

# ============================================================
# TELETHON API
# ============================================================

try:
    API_ID = int(os.getenv("API_ID", "0"))
except (TypeError, ValueError):
    API_ID = 0

API_HASH = os.getenv(
    "API_HASH",
    ""
).strip()


# ============================================================
# ADMIN
# ============================================================

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except (TypeError, ValueError):
    ADMIN_ID = 0

ADMIN_CONTACT_USERNAME = os.getenv(
    "ADMIN_CONTACT_USERNAME",
    ""
).strip().lstrip("@")


# ============================================================
# FORCE JOIN CHANNEL
# ============================================================

FORCE_CHANNEL_USERNAME = os.getenv(
    "FORCE_CHANNEL_USERNAME",
    ""
).strip()

# @ hata kar username rakhenge
FORCE_CHANNEL_USERNAME = (
    FORCE_CHANNEL_USERNAME.lstrip("@")
)


# ============================================================
# VALIDATION
# ============================================================

def validate_config():

    missing = []

    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")

    if not BOT_USERNAME:
        missing.append("BOT_USERNAME")

    if API_ID <= 0:
        missing.append("API_ID")

    if not API_HASH:
        missing.append("API_HASH")

    if ADMIN_ID <= 0:
        missing.append("ADMIN_ID")

    if not ADMIN_CONTACT_USERNAME:
        missing.append("ADMIN_CONTACT_USERNAME")

    if not FORCE_CHANNEL_USERNAME:
        missing.append("FORCE_CHANNEL_USERNAME")

    if missing:
        raise RuntimeError(
            "Missing/invalid environment variables: "
            + ", ".join(missing)
        )


# ============================================================
# SAFE STARTUP CHECK
# ============================================================

if __name__ == "__main__":
    validate_config()
    print("✅ AdsNova Pro configuration is valid.")
