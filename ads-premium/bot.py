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
    MessageHandler,
    filters,
    ConversationHandler,
)

from config import BOT_TOKEN, ADMIN_ID, PREMIUM_PRICE
from database import init_db, save_user, is_premium, save_user_session, get_user_sessions


# =========================================================
# CHANNEL
# =========================================================

CHANNEL_USERNAME = "@iqra_music_support"
CHANNEL_LINK = "https://t.me/iqra_music_support"


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# CONVERSATION STATES FOR LOGIN
# =========================================================
PHONE, OTP, PASSWORD = range(3)


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(
            b"Ads Premium Bot is running!"
        )

    def log_message(self, format, *args):
        return


def start_health_server():

    server = HTTPServer(
        ("0.0.0.0", 10000),
        HealthHandler,
    )

    server.serve_forever()


# =========================================================
# CHANNEL MEMBERSHIP CHECK
# =========================================================

async def check_channel_member(bot, user_id):

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
            "Channel membership error: %s",
            error,
        )

        return False


# =========================================================
# JOIN CHANNEL BUTTON
# =========================================================

def join_channel_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 Join Channel",
                url=CHANNEL_LINK,
            )
        ],
        [
            InlineKeyboardButton(
                "✅ Verify Membership",
                callback_data="verify_channel",
            )
        ],
    ])


# =========================================================
# JOIN SCREEN
# =========================================================

async def show_join_screen(update):

    text = (
        "📢 <b>Channel Join Required</b>\n\n"
        "Bot use karne ke liye pehle hamara channel "
        "join karein.\n\n"
        "1️⃣ <b>Join Channel</b> dabayein.\n"
        "2️⃣ Channel join karein.\n"
        "3️⃣ <b>Verify Membership</b> dabayein.\n\n"
        "⚠️ Channel join kiye bina Dashboard open nahi hoga."
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
                "🔐 Login / Add Accounts",
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
# PREMIUM CHECK
# =========================================================

def user_has_premium(user_id):

    if user_id == ADMIN_ID:
        return True

    try:
        return is_premium(user_id)

    except Exception as error:

        logger.error(
            "Premium check error: %s",
            error,
        )

        return False


# =========================================================
# PREMIUM REQUIRED
# =========================================================

async def premium_required(query):

    if query.from_user.id == ADMIN_ID:
        return False

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

    return True


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

    if user_has_premium(query.from_user.id):
        status = "✅ Premium Active"
    else:
        status = "❌ Premium Not Active"

    text = (
        "💎 <b>Premium Subscription</b>\n\n"
        f"💰 Price: <b>₹{PREMIUM_PRICE}</b>\n"
        f"📊 Status: <b>{status}</b>\n\n"
        "Payment verification module baad me add kiya jayega."
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

    is_member = await check_channel_member(
        context.bot,
        user.id,
    )

    if not is_member:

        await show_join_screen(update)
        return

    await show_dashboard(update)


# =========================================================
# CALLBACKS
# =========================================================

async def callbacks(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id
    action = query.data


    if action == "verify_channel":

        is_member = await check_channel_member(
            context.bot,
            user_id,
        )

        if not is_member:

            await query.answer(
                "❌ Aapne abhi channel join nahi kiya.",
                show_alert=True,
            )

            await query.edit_message_text(
                "📢 <b>Channel Join Required</b>\n\n"
                "Pehle channel join karein aur phir "
                "Verify Membership dabayein.",
                parse_mode="HTML",
                reply_markup=join_channel_keyboard(),
            )

            return

        await query.answer(
            "✅ Membership verified!",
            show_alert=False,
        )

        await show_dashboard(update)

        return


    if action == "dashboard":

        is_member = await check_channel_member(
            context.bot,
            user_id,
        )

        if not is_member:

            await show_join_screen(update)
            return

        await show_dashboard(update)
        return


    if action == "subscription":

        await show_subscription(query)
        return


    if action == "buy_premium":

        if user_id == ADMIN_ID:

            await query.answer(
                "👑 Admin Premium already active hai.",
                show_alert=True,
            )

            return

        await query.edit_message_text(
            f"💎 <b>Premium Subscription</b>\n\n"
            f"💰 Amount: <b>₹{PREMIUM_PRICE}</b>\n\n"
            "Payment system abhi setup phase me hai.",
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

        if not user_has_premium(user_id):

            blocked = await premium_required(query)

            if blocked:
                return


    if action == "login":

        sessions = get_user_sessions(user_id)
        count = len(sessions)

        text = (
            f"🔐 <b>Telegram Accounts Manager</b>\n\n"
            f"📊 Total Logged-in Accounts: <b>{count} / 20</b>\n\n"
            "Naya account add karne ke liye neeche click karein."
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "➕ Add New Account",
                    callback_data="start_add_account",
                )
            ],
            [
                InlineKeyboardButton(
                    "↩️ Back",
                    callback_data="dashboard",
                )
            ]
        ]

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        return


    if action == "start_add_account":

        await query.message.reply_text(
            "📱 Kripya apna Telegram account ka **Phone Number** country code ke sath bhejein (Jaise: `+919876543210`):",
            parse_mode="HTML"
        )
        return


    if action == "status":

        sessions = get_user_sessions(user_id)

        await query.edit_message_text(
            f"📊 <b>Status & Accounts</b>\n\n"
            f"🟢 Bot: Online\n"
            f"📱 Connected Accounts: <b>{len(sessions)}</b>",
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


    if action == "settings":

        await show_settings(query)
        return


    if action == "switch_account":

        sessions = get_user_sessions(user_id)

        if not sessions:
            text = "🔄 <b>Switch Account</b>\n\nAbhi koi account login nahi hai. Pehle Login section se account add karein."
        else:
            text = "🔄 <b>Your Logged-in Accounts:</b>\n\n"
            for row in sessions:
                text += f"🆔 ID: {row[0]} | 📱 {row[1]}\n"

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "➕ Add Account",
                        callback_data="login",
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
            "Is setting ka detailed configuration next module me add kiya jayega.",
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


    if action == "help":

        await show_help(query)
        return


    if action == "refresh":

        is_member = await check_channel_member(
            context.bot,
            user_id,
        )

        if not is_member:

            await show_join_screen(update)
            return

        await show_dashboard(update)
        return


# =========================================================
# ADMIN
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
        "💎 Premium: Active\n"
        "🟢 Bot: Online",
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
# RUN BOT
# =========================================================

async def run_bot():

    if not BOT_TOKEN:

        raise ValueError(
            "BOT_TOKEN environment variable missing."
        )

    init_db()

    threading.Thread(
        target=start_health_server,
        daemon=True,
    ).start()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

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

    application.add_error_handler(error_handler)

    print("Bot is starting...")
    await application.run_polling()
