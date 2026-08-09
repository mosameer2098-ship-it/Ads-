import asyncio
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import BOT_TOKEN, CHANNEL_USERNAME, ADMIN_ID, PREMIUM_PRICE
from database import init_db, save_user, is_premium


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Ads Premium Bot is running!")

    def log_message(self, format, *args):
        return


def start_health_server():
    server = HTTPServer(("0.0.0.0", 10000), HealthHandler)
    server.serve_forever()


# =========================================================
# CHANNEL MEMBERSHIP
# =========================================================

async def check_channel_member(bot, user_id):

    if not CHANNEL_USERNAME:
        logger.warning("CHANNEL_USERNAME is empty.")
        return False

    try:
        member = await bot.get_chat_member(
            chat_id=CHANNEL_USERNAME,
            user_id=user_id,
        )

        return member.status in (
            "member",
            "administrator",
            "creator",
        )

    except Exception as error:
        logger.error(
            "Channel membership check failed: %s",
            error,
        )
        return False


# =========================================================
# JOIN CHANNEL SCREEN
# =========================================================

def join_channel_keyboard():

    username = CHANNEL_USERNAME.lstrip("@")

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 Join Channel",
                url=f"https://t.me/{username}",
            )
        ],
        [
            InlineKeyboardButton(
                "✅ Verify Membership",
                callback_data="verify_channel",
            )
        ],
    ])


async def show_join_screen(update):

    text = (
        "📢 <b>Channel Join Required</b>\n\n"
        "Bot use karne ke liye pehle hamara channel "
        "join karein.\n\n"
        "1️⃣ <b>Join Channel</b> par click karein.\n"
        "2️⃣ Channel join karne ke baad "
        "<b>Verify Membership</b> dabayein."
    )

    if update.callback_query:

        await update.callback_query.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=join_channel_keyboard(),
        )

    else:

        await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=join_channel_keyboard(),
        )


# =========================================================
# DASHBOARD
# =========================================================

def dashboard_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔐 Login",
                callback_data="login",
            )
        ],
        [
            InlineKeyboardButton(
                "📊 Status",
                callback_data="status",
            ),
            InlineKeyboardButton(
                "⚙️ Settings",
                callback_data="settings",
            ),
        ],
        [
            InlineKeyboardButton(
                "💎 Subscription",
                callback_data="subscription",
            ),
            InlineKeyboardButton(
                "❓ Help",
                callback_data="help",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔄 Switch Account",
                callback_data="switch_account",
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Refresh",
                callback_data="refresh",
            )
        ],
    ])


async def show_dashboard(update):

    text = (
        "🤖 <b>Ads Premium Bot</b>\n\n"
        "🏠 <b>Main Dashboard</b>\n\n"
        "Neeche se koi option select karein."
    )

    if update.callback_query:

        await update.callback_query.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=dashboard_keyboard(),
        )

    else:

        await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=dashboard_keyboard(),
        )


# =========================================================
# PREMIUM REQUIRED
# =========================================================

async def premium_required(query):

    text = (
        "🔒 <b>Premium Required</b>\n\n"
        "Ye feature use karne ke liye Premium "
        "subscription required hai.\n\n"
        f"💎 Premium Price: <b>₹{PREMIUM_PRICE}</b>"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                f"💎 Buy Premium ₹{PREMIUM_PRICE}",
                callback_data="buy_premium",
            )
        ],
        [
            InlineKeyboardButton(
                "↩️ Back to Dashboard",
                callback_data="dashboard",
            )
        ],
    ]

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# =========================================================
# SETTINGS
# =========================================================

def settings_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 Select Channel",
                callback_data="select_channel",
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Select Groups",
                callback_data="select_groups",
            )
        ],
        [
            InlineKeyboardButton(
                "⏱️ Set Posting Interval",
                callback_data="posting_interval",
            )
        ],
        [
            InlineKeyboardButton(
                "🐢 Set Group Delay",
                callback_data="group_delay",
            )
        ],
        [
            InlineKeyboardButton(
                "💬 Auto-Reply Settings",
                callback_data="auto_reply",
            )
        ],
        [
            InlineKeyboardButton(
                "🔓 Logout",
                callback_data="logout",
            )
        ],
        [
            InlineKeyboardButton(
                "↩️ Back",
                callback_data="dashboard",
            )
        ],
    ])


async def show_settings(query):

    await query.edit_message_text(
        "⚙️ <b>Settings Menu</b>\n\n"
        "Neeche se setting select karein.",
        parse_mode="HTML",
        reply_markup=settings_keyboard(),
    )


# =========================================================
# SUBSCRIPTION
# =========================================================

async def show_subscription(query):

    if is_premium(query.from_user.id):
        status = "✅ Premium Active"
    else:
        status = "❌ Premium Not Active"

    text = (
        "💎 <b>Premium Subscription</b>\n\n"
        f"💰 Price: <b>₹{PREMIUM_PRICE}</b>\n"
        f"📊 Status: <b>{status}</b>\n\n"
        "Payment verification module baad me "
        "add kiya jayega."
    )

    keyboard = [
        [
            InlineKeyboardButton(
                f"💎 Buy Premium ₹{PREMIUM_PRICE}",
                callback_data="buy_premium",
            )
        ],
        [
            InlineKeyboardButton(
                "↩️ Back",
                callback_data="dashboard",
            )
        ],
    ]

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# =========================================================
# HELP
# =========================================================

async def show_help(query):

    await query.edit_message_text(
        "❓ <b>Help Centre</b>\n\n"
        "Bot use karne me problem aaye to admin se "
        "contact karein.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "↩️ Back",
                    callback_data="dashboard",
                )
            ]
        ]),
    )


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user = update.effective_user

    save_user(user)

    # Admin ko direct dashboard
    if user.id == ADMIN_ID:
        await show_dashboard(update)
        return

    # Normal user ke liye channel verification
    is_member = await check_channel_member(
        context.bot,
        user.id,
    )

    if not is_member:
        await show_join_screen(update)
        return

    await show_dashboard(update)


# =========================================================
# CALLBACK HANDLER
# =========================================================

async def callbacks(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id
    action = query.data

    # -----------------------------------------------------
    # VERIFY CHANNEL
    # -----------------------------------------------------

    if action == "verify_channel":

        is_member = await check_channel_member(
            context.bot,
            user_id,
        )

        if not is_member:

            await query.answer(
                "❌ Pehle channel join karein.",
                show_alert=True,
            )

            return

        await show_dashboard(update)
        return

    # -----------------------------------------------------
    # DASHBOARD
    # -----------------------------------------------------

    if action == "dashboard":

        await show_dashboard(update)
        return

    # -----------------------------------------------------
    # SUBSCRIPTION
    # -----------------------------------------------------

    if action == "subscription":

        await show_subscription(query)
        return

    # -----------------------------------------------------
    # BUY PREMIUM
    # -----------------------------------------------------

    if action == "buy_premium":

        await query.edit_message_text(
            f"💎 <b>Premium Subscription</b>\n\n"
            f"💰 Amount: <b>₹{PREMIUM_PRICE}</b>\n\n"
            "Payment system abhi setup phase me hai.\n\n"
            "UPI QR aur automatic verification "
            "baad me add karenge.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "↩️ Back",
                        callback_data="subscription",
                    )
                ]
            ]),
        )

        return

    # -----------------------------------------------------
    # PREMIUM FEATURES
    # -----------------------------------------------------

    premium_features = {
        "login",
        "status",
        "settings",
        "switch_account",
        "select_channel",
        "select_groups",
        "posting_interval",
        "group_delay",
        "auto_reply",
        "logout",
    }

    if action in premium_features:

        if not is_premium(user_id):

            await premium_required(query)
            return

    # -----------------------------------------------------
    # LOGIN
    # -----------------------------------------------------

    if action == "login":

        await query.edit_message_text(
            "🔐 <b>Telegram Account Login</b>\n\n"
            "Multiple account login module next stage "
            "me add kiya jayega.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "↩️ Back",
                        callback_data="dashboard",
                    )
                ]
            ]),
        )

        return

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    if action == "status":

        await query.edit_message_text(
            "📊 <b>Status</b>\n\n"
            "🟢 Bot: Online\n"
            "📢 Channel: Not configured\n"
            "👥 Groups: Not configured\n"
            "⏱️ Posting: Not configured",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "↩️ Back",
                        callback_data="dashboard",
                    )
                ]
            ]),
        )

        return

    # -----------------------------------------------------
    # SETTINGS
    # -----------------------------------------------------

    if action == "settings":

        await show_settings(query)
        return

    # -----------------------------------------------------
    # ACCOUNT MANAGER
    # -----------------------------------------------------

    if action == "switch_account":

        await query.edit_message_text(
            "🔄 <b>Account Manager</b>\n\n"
            "Multiple Telegram account module "
            "next stage me add hoga.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "➕ Add Account",
                        callback_data="add_account",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "↩️ Back",
                        callback_data="dashboard",
                    )
                ]
            ]),
        )

        return

    # -----------------------------------------------------
    # ADD ACCOUNT
    # -----------------------------------------------------

    if action == "add_account":

        await query.edit_message_text(
            "➕ <b>Add Telegram Account</b>\n\n"
            "Account login module next stage me "
            "add kiya jayega.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "↩️ Account Manager",
                        callback_data="switch_account",
                    )
                ]
            ]),
        )

        return

    # -----------------------------------------------------
    # SETTINGS OPTIONS
    # -----------------------------------------------------

    setting_titles = {
        "select_channel": "📢 Select Channel",
        "select_groups": "👥 Select Groups",
        "posting_interval": "⏱️ Set Posting Interval",
        "group_delay": "🐢 Set Group Delay",
        "auto_reply": "💬 Auto-Reply Settings",
        "logout": "🔓 Logout",
    }

    if action in setting_titles:

        await query.edit_message_text(
            f"<b>{setting_titles[action]}</b>\n\n"
            "Is setting ka detailed configuration "
            "next module me add kiya jayega.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "↩️ Settings",
                        callback_data="settings",
                    )
                ]
            ]),
        )

        return

    # -----------------------------------------------------
    # HELP
    # -----------------------------------------------------

    if action == "help":

        await show_help(query)
        return

    # -----------------------------------------------------
    # REFRESH
    # -----------------------------------------------------

    if action == "refresh":

        await show_dashboard(update)
        return


# =========================================================
# ADMIN COMMAND
# =========================================================

async def admin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if update.effective_user.id != ADMIN_ID:

        await update.message.reply_text(
            "❌ Admin access denied."
        )

        return

    await update.message.reply_text(
        "👑 <b>Admin Access</b>\n\n"
        "Admin system next module me add hoga.",
        parse_mode="HTML",
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    logger.error(
        "Exception while handling update:",
        exc_info=context.error,
    )


# =========================================================
# BOT RUNNER
# =========================================================

async def run_bot():

    if not BOT_TOKEN:

        raise ValueError(
            "BOT_TOKEN environment variable missing."
        )

    # Database initialize
    init_db()

    # Render health server
    threading.Thread(
        target=start_health_server,
        daemon=True,
    ).start()

    # Create Telegram application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Handlers
    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "admin",
            admin_command,
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            callbacks,
        )
    )

    application.add_error_handler(
        error_handler
    )

    logger.info(
        "🤖 Ads Premium Bot Started..."
    )

    # Start application
    await application.initialize()

    await application.start()

    # Start Telegram polling
    await application.updater.start_polling(
        allowed_updates=Update.ALL_TYPES
    )

    logger.info(
        "✅ Telegram polling started successfully."
    )

    # Keep bot alive
    await asyncio.Event().wait()


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    asyncio.run(run_bot())
