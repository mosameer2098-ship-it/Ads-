import logging
import sqlite3
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import BOT_TOKEN, CHANNEL_USERNAME, ADMIN_ID, PREMIUM_PRICE


# =========================
# LOGGING
# =========================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

DB_NAME = "bot.db"


# =========================
# DATABASE
# =========================

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            premium INTEGER DEFAULT 0,
            premium_expiry TEXT,
            verified INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS account_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            slot_number INTEGER,
            status TEXT DEFAULT 'Not Connected',
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_user(user):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO users
        (user_id, username, first_name, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        user.id,
        user.username or "",
        user.first_name or "",
        datetime.utcnow().isoformat(),
    ))

    cur.execute("""
        UPDATE users
        SET username = ?, first_name = ?
        WHERE user_id = ?
    """, (
        user.username or "",
        user.first_name or "",
        user.id,
    ))

    conn.commit()
    conn.close()


def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,)
    )

    row = cur.fetchone()
    conn.close()

    return row


def is_premium(user_id):
    row = get_user(user_id)

    if not row:
        return False

    premium = row[3]
    expiry = row[4]

    if premium != 1:
        return False

    if expiry:
        try:
            expiry_date = datetime.fromisoformat(expiry)

            if datetime.utcnow() > expiry_date:
                conn = sqlite3.connect(DB_NAME)
                cur = conn.cursor()

                cur.execute("""
                    UPDATE users
                    SET premium = 0
                    WHERE user_id = ?
                """, (user_id,))

                conn.commit()
                conn.close()

                return False

        except Exception:
            pass

    return True


# =========================
# CHANNEL MEMBERSHIP
# =========================

async def check_channel_member(bot, user_id):

    if not CHANNEL_USERNAME:
        return False

    try:
        member = await bot.get_chat_member(
            chat_id=CHANNEL_USERNAME,
            user_id=user_id
        )

        return member.status in [
            "member",
            "administrator",
            "creator",
        ]

    except Exception as e:
        logger.error("Channel check error: %s", e)
        return False


# =========================
# JOIN SCREEN
# =========================

def join_screen():

    username = CHANNEL_USERNAME.lstrip("@")

    keyboard = [
        [
            InlineKeyboardButton(
                "📢 Join Channel",
                url=f"https://t.me/{username}"
            )
        ],
        [
            InlineKeyboardButton(
                "✅ Verify Membership",
                callback_data="verify_channel"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


async def send_join_screen(update: Update):

    text = (
        "📢 <b>Channel Join Required</b>\n\n"
        "Bot use karne se pehle hamara official "
        "channel join karein.\n\n"
        "👇 Pehle channel join karein, phir "
        "<b>Verify Membership</b> dabayein."
    )

    if update.callback_query:
        await update.callback_query.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=join_screen()
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=join_screen()
        )


# =========================
# MAIN MENU
# =========================

def main_menu():

    keyboard = [
        [
            InlineKeyboardButton(
                "🔐 Login",
                callback_data="login"
            )
        ],
        [
            InlineKeyboardButton(
                "📊 Status",
                callback_data="status"
            ),
            InlineKeyboardButton(
                "⚙️ Settings",
                callback_data="settings"
            )
        ],
        [
            InlineKeyboardButton(
                "💎 Subscription",
                callback_data="subscription"
            ),
            InlineKeyboardButton(
                "❓ Help",
                callback_data="help"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Switch Account",
                callback_data="switch_account"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Refresh",
                callback_data="refresh"
            ),
            InlineKeyboardButton(
                "💬 Help Centre",
                callback_data="help"
            )
        ],
        [
            InlineKeyboardButton(
                "🆔 TG ID BOT",
                url="https://t.me/userinfobot"
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


async def show_dashboard(update: Update):

    text = (
        "🤖 <b>Ads Premium Bot - Main Menu</b>\n\n"
        "💎 <b>Premium Service</b>\n"
        "🔒 Your account stays protected.\n\n"
        "Choose an option below:"
    )

    if update.callback_query:
        await update.callback_query.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=main_menu()
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=main_menu()
        )


# =========================
# SETTINGS
# =========================

def settings_menu():

    keyboard = [
        [
            InlineKeyboardButton(
                "📢 Select Channel",
                callback_data="select_channel"
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Select Groups",
                callback_data="select_groups"
            )
        ],
        [
            InlineKeyboardButton(
                "⏱️ Set Posting Interval",
                callback_data="posting_interval"
            )
        ],
        [
            InlineKeyboardButton(
                "🐢 Set Group Delay",
                callback_data="group_delay"
            )
        ],
        [
            InlineKeyboardButton(
                "💬 Auto-Reply Settings",
                callback_data="auto_reply"
            )
        ],
        [
            InlineKeyboardButton(
                "🔓 Logout",
                callback_data="logout"
            )
        ],
        [
            InlineKeyboardButton(
                "↩️ Back",
                callback_data="dashboard"
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


async def show_settings(query):

    text = (
        "⚙️ <b>Settings Menu</b>\n\n"
        "Configure your bot settings:"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=settings_menu()
    )


# =========================
# SUBSCRIPTION
# =========================

async def show_subscription(query):

    if is_premium(query.from_user.id):
        status = "✅ Premium Active"
    else:
        status = "❌ Premium Not Active"

    text = (
        "💎 <b>Premium Subscription</b>\n\n"
        f"💰 Price: <b>₹{PREMIUM_PRICE}</b>\n"
        f"📊 Status: <b>{status}</b>\n\n"
        "Premium payment verification baad me "
        "automatic system ke saath connect ki jayegi."
    )

    keyboard = [
        [
            InlineKeyboardButton(
                f"💎 Buy Premium ₹{PREMIUM_PRICE}",
                callback_data="buy_premium"
            )
        ],
        [
            InlineKeyboardButton(
                "↩️ Back",
                callback_data="dashboard"
            )
        ]
    ]

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# ACCOUNT MANAGER
# =========================

async def show_accounts(query):

    user_id = query.from_user.id

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT slot_number, status
        FROM account_slots
        WHERE user_id = ?
        ORDER BY slot_number
    """, (user_id,))

    slots = cur.fetchall()
    conn.close()

    text = "🔄 <b>Account Manager</b>\n\n"

    if not slots:
        text += "No account slots created yet.\n\n"

    for slot, status in slots:
        text += f"• Slot {slot}: {status}\n"

    text += "\n➕ Add Account se naya slot create kar sakte hain."

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Add Account",
                callback_data="add_account"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Refresh",
                callback_data="switch_account"
            )
        ],
        [
            InlineKeyboardButton(
                "↩️ Back",
                callback_data="dashboard"
            )
        ]
    ]

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# ADMIN PANEL
# =========================

def admin_menu():

    keyboard = [
        [
            InlineKeyboardButton(
                "📈 Statistics",
                callback_data="admin_stats"
            )
        ],
        [
            InlineKeyboardButton(
                "🎯 Active Slots",
                callback_data="admin_slots"
            )
        ],
        [
            InlineKeyboardButton(
                "📢 Broadcast",
                callback_data="admin_broadcast"
            )
        ],
        [
            InlineKeyboardButton(
                "➕ Add Subscription",
                callback_data="admin_addsub"
            ),
            InlineKeyboardButton(
                "✏️ Edit Subscription",
                callback_data="admin_editsub"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Delete Subscription",
                callback_data="admin_delsub"
            )
        ],
        [
            InlineKeyboardButton(
                "💰 Set Plan Price",
                callback_data="admin_price"
            )
        ],
        [
            InlineKeyboardButton(
                "👤 User Status",
                callback_data="admin_userstatus"
            )
        ],
        [
            InlineKeyboardButton(
                "ℹ️ User Info",
                callback_data="admin_userinfo"
            )
        ],
        [
            InlineKeyboardButton(
                "✅ Verify User",
                callback_data="admin_verify"
            )
        ],
        [
            InlineKeyboardButton(
                "🚫 Remove Verification",
                callback_data="admin_unverify"
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Active Subscribers",
                callback_data="admin_list"
            )
        ],
        [
            InlineKeyboardButton(
                "↩️ Back",
                callback_data="dashboard"
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


async def show_admin(query):

    if query.from_user.id != ADMIN_ID:
        await query.answer(
            "❌ Admin access nahi hai.",
            show_alert=True
        )
        return

    text = (
        "👑 <b>Admin Panel</b>\n\n"
        "Select an admin option:"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_menu()
    )


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    save_user(user)

    is_member = await check_channel_member(
        context.bot,
        user.id
    )

    if not is_member:
        await send_join_screen(update)
        return

    await show_dashboard(update)


# =========================
# CALLBACKS
# =========================

async def callbacks(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    # Channel verification
    if query.data == "verify_channel":

        is_member = await check_channel_member(
            context.bot,
            user_id
        )

        if not is_member:
            await query.answer(
                "❌ Pehle channel join karein.",
                show_alert=True
            )
            return

        await show_dashboard(update)
        return

    # Dashboard
    if query.data == "dashboard":
        await show_dashboard(update)
        return

    # Settings
    if query.data == "settings":
        await show_settings(query)
        return

    # Subscription
    if query.data == "subscription":
        await show_subscription(query)
        return

    # Accounts
    if query.data == "switch_account":
        await show_accounts(query)
        return

    # Admin
    if query.data == "admin":
        await show_admin(query)
        return

    # Login
    if query.data == "login":

        if not is_premium(user_id):
            await query.answer(
                "💎 Pehle Premium activate karein.",
                show_alert=True
            )
            return

        await query.edit_message_text(
            "🔐 <b>Telegram Account Login</b>\n\n"
            "Multiple account login module next stage "
            "me add kiya jayega.\n\n"
            "⚠️ Sirf apne/authorized accounts ka use karein.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "↩️ Back",
                        callback_data="dashboard"
                    )
                ]
            ])
        )
        return

    # Buy Premium
    if query.data == "buy_premium":

        await query.edit_message_text(
            f"💎 <b>Premium – ₹{PREMIUM_PRICE}</b>\n\n"
            "Payment module abhi setup phase me hai.\n\n"
            "Automatic payment verification baad me "
            "connect ki jayegi.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "↩️ Back",
                        callback_data="subscription"
                    )
                ]
            ])
        )
        return

    # Add Account
    if query.data == "add_account":

        if not is_premium(user_id):
            await query.answer(
                "💎 Multiple accounts ke liye Premium required hai.",
                show_alert=True
            )
            return

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()

        cur.execute("""
            SELECT COALESCE(MAX(slot_number), 0)
            FROM account_slots
            WHERE user_id = ?
        """, (user_id,))

        next_slot = cur.fetchone()[0] + 1

        cur.execute("""
            INSERT INTO account_slots
            (user_id, slot_number, status, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            next_slot,
            "Not Connected",
            datetime.utcnow().isoformat(),
        ))

        conn.commit()
        conn.close()

        await query.edit_message_text(
            f"➕ <b>Slot {next_slot} Created</b>\n\n"
            "Account login module next stage me connect hoga.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔄 Account Manager",
                        callback_data="switch_account"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "↩️ Back",
                        callback_data="dashboard"
                    )
                ]
            ])
        )
        return

    # Help
    if query.data == "help":

        await query.edit_message_text(
            "❓ <b>Help Centre</b>\n\n"
            "Bot use karne me problem aaye to admin se "
            "contact karein.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "↩️ Back",
                        callback_data="dashboard"
                    )
                ]
            ])
        )
        return

    # Refresh
    if query.data == "refresh":
        await show_dashboard(update)
        return

    # Settings items
    settings_items = {
        "select_channel": "📢 Select Channel",
        "select_groups": "👥 Select Groups",
        "posting_interval": "⏱️ Set Posting Interval",
        "group_delay": "🐢 Set Group Delay",
        "auto_reply": "💬 Auto-Reply Settings",
        "logout": "🔓 Logout",
    }

    if query.data in settings_items:

        title = settings_items[query.data]

        await query.edit_message_text(
            f"{title}\n\n"
            "⚙️ Is setting ka detailed configuration "
            "next module me add kiya jayega.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "↩️ Settings",
                        callback_data="settings"
                    )
                ]
            ])
        )
        return


# =========================
# ADMIN COMMAND
# =========================

async def admin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ Admin access denied."
        )
        return

    keyboard = [
        [
            InlineKeyboardButton(
                "👑 Open Admin Panel",
                callback_data="admin"
            )
        ]
    ]

    await update.message.reply_text(
        "👑 <b>Admin Access</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# ERROR HANDLER
# =========================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.error(
        "Exception while handling update:",
        exc_info=context.error
    )


# =========================
# MAIN
# =========================

def main():

    if not BOT_TOKEN:
        raise ValueError(
            "BOT_TOKEN environment variable missing."
        )

    init_db()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("admin", admin_command)
    )

    application.add_handler(
        CallbackQueryHandler(callbacks)
   
