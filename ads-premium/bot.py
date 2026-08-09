import logging

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

from config import (
    BOT_TOKEN,
    CHANNEL_USERNAME,
    ADMIN_ID,
    PREMIUM_PRICE,
)

from database import (
    init_db,
    save_user,
    is_premium,
)


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# CHANNEL MEMBERSHIP
# =========================================================

async def check_channel_member(bot, user_id):
    """
    Check whether the user has joined the required channel.
    """

    if not CHANNEL_USERNAME:
        logger.warning("CHANNEL_USERNAME is empty.")
        return False

    try:
        member = await bot.get_chat_member(
            chat_id=CHANNEL_USERNAME,
            user_id=user_id,
        )

        return member.status in [
            "member",
            "administrator",
            "creator",
        ]

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

    channel_username = CHANNEL_USERNAME.lstrip("@")

    keyboard = [
        [
            InlineKeyboardButton(
                "📢 Join Channel",
                url=f"https://t.me/{channel_username}",
            )
        ],
        [
            InlineKeyboardButton(
                "✅ Verify Membership",
                callback_data="verify_channel",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


async def show_join_screen(update):

    text = (
        "📢 <b>Channel Join Required</b>\n\n"
        "Bot use karne ke liye pehle hamara channel "
        "join karein.\n\n"
        "1️⃣ <b>Join Channel</b> par click karein.\n"
        "2️⃣ Channel join karne ke baad "
        "<b>Verify Membership</b> dabayein.\n\n"
        "⚠️ Channel join kiye bina dashboard open nahi hoga."
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
# MAIN DASHBOARD
# =========================================================

def dashboard_keyboard():

    keyboard = [
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
            ),
        ],
        [
            InlineKeyboardButton(
                "🔄 Refresh",
                callback_data="refresh",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


async def show_dashboard(update):

    text = (
        "🤖 <b>Ads Premium Bot</b>\n\n"
        "🏠 <b>Main Dashboard</b>\n\n"
        "Welcome! Neeche se koi option select karein."
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
# PREMIUM REQUIRED SCREEN
# =========================================================

async def premium_required(query):

    text = (
        "🔒 <b>Premium Required</b>\n\n"
        "Ye feature use karne ke liye "
        "Premium subscription required hai.\n\n"
        f"💎 Premium Price: <b>₹{PREMIUM_PRICE}</b>\n\n"
        "Premium activate karne ke baad aap is feature "
        "ka use kar sakte hain."
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

    keyboard = [
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
        reply_markup=settings_keyboard(),
    )


# =========================================================
# SUBSCRIPTION
# =========================================================

async def show_subscription(query):

    user_id = query.from_user.id

    if is_premium(user_id):
        status = "✅ Premium Active"
    else:
        status = "❌ Premium Not Active"

    text = (
        "💎 <b>Premium Subscription</b>\n\n"
        f"💰 Price: <b>₹{PREMIUM_PRICE}</b>\n"
        f"📊 Status: <b>{status}</b>\n\n"
        "Premium payment system ko baad me "
        "automatic verification ke saath connect kiya jayega."
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
# ACCOUNT MANAGER
# =========================================================

async def show_accounts(query):

    if not is_premium(query.from_user.id):

        await premium_required(query)
        return

    text = (
        "🔄 <b>Account Manager</b>\n\n"
        "Multiple Telegram account slots yahan manage honge.\n\n"
        "➕ Add Account\n"
        "🔄 Switch Account\n"
        "🗑️ Remove Account"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Add Account",
                callback_data="add_account",
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Refresh",
                callback_data="switch_account",
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

    text = (
        "❓ <b>Help Centre</b>\n\n"
        "Bot ke kisi feature ko use karne me problem "
        "ho to admin se contact karein."
    )

    keyboard = [
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


# =========================================================
# ADMIN PANEL
# =========================================================

def admin_keyboard():

    keyboard = [
        [
            InlineKeyboardButton(
                "📈 Statistics",
                callback_data="admin_stats",
            )
        ],
        [
            InlineKeyboardButton(
                "🎯 Active Slots",
                callback_data="admin_slots",
            )
        ],
        [
            InlineKeyboardButton(
                "📢 Broadcast",
                callback_data="admin_broadcast",
            )
        ],
        [
            InlineKeyboardButton(
                "➕ Add Subscription",
                callback_data="admin_addsub",
            ),
            InlineKeyboardButton(
                "✏️ Edit Subscription",
                callback_data="admin_editsub",
            ),
        ],
        [
            InlineKeyboardButton(
                "❌ Delete Subscription",
                callback_data="admin_delsub",
            )
        ],
        [
            InlineKeyboardButton(
                "💰 Set Plan Price",
                callback_data="admin_price",
            )
        ],
        [
            InlineKeyboardButton(
                "👤 User Status",
                callback_data="admin_userstatus",
            )
        ],
        [
            InlineKeyboardButton(
                "ℹ️ User Info",
                callback_data="admin_userinfo",
            )
        ],
        [
            InlineKeyboardButton(
                "✅ Verify User",
                callback_data="admin_verify",
            )
        ],
        [
            InlineKeyboardButton(
                "🚫 Remove Verification",
                callback_data="admin_unverify",
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Active Subscribers",
                callback_data="admin_list",
            )
        ],
        [
            InlineKeyboardButton(
                "↩️ Back",
                callback_data="dashboard",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


async def show_admin(query):

    if query.from_user.id != ADMIN_ID:

        await query.answer(
            "❌ Admin access nahi hai.",
            show_alert=True,
        )

        return

    text = (
        "👑 <b>Admin Panel</b>\n\n"
        "Admin options select karein:"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# =========================================================
# START COMMAND
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user = update.effective_user

    save_user(user)

    # Admin ko direct dashboard access
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

    # Channel joined -> dashboard
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

        text = (
            f"💎 <b>Premium Subscription</b>\n\n"
            f"💰 Amount: <b>₹{PREMIUM_PRICE}</b>\n\n"
            "Payment system abhi setup phase me hai.\n\n"
            "Automatic payment verification baad me "
            "add ki jayegi."
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "↩️ Back",
                    callback_data="subscription",
                )
            ]
        ]

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        return

    # -----------------------------------------------------
    # PREMIUM FEATURES
    # -----------------------------------------------------

    premium_features = [
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
    ]

    if action in premium_features:

        if not is_premium(user_id):

            await premium_required(query)

            return

    # -----------------------------------------------------
    # SETTINGS
    # -----------------------------------------------------

    if action == "settings":

        await show_settings(query)

        return

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    if action == "status":

        text = (
            "📊 <b>Posting Status</b>\n\n"
            "🟢 Status: Ready\n"
            "📢 Channel: Not configured\n"
            "👥 Groups: Not configured\n"
            "⏱️ Interval: Not configured"
        )

        keyboard = [
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

    # -----------------------------------------------------
    # LOGIN
    # -----------------------------------------------------

    if action == "login":

        text = (
            "🔐 <b>Telegram Account Login</b>\n\n"
            "Multiple account login module next stage "
            "me add kiya jayega.\n\n"
            "Sirf apne/authorized accounts ka use karein."
        )

        keyboard = [
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

    # -----------------------------------------------------
    # ACCOUNT MANAGER
    # -----------------------------------------------------

    if action == "switch_account":

        await show_accounts(query)

        return

    # -----------------------------------------------------
    # SETTINGS ITEMS
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

        title = setting_titles[action]

        text = (
            f"{title}\n\n"
            "⚙️ Is setting ka detailed configuration "
            "next module me add kiya jayega."
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "↩️ Settings",
                    callback_data="settings",
                )
            ]
        ]

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        return

    # -----------------------------------------------------
    # ADD ACCOUNT
    # -----------------------------------------------------

    if action == "add_account":

        text = (
            "➕ <b>Add Telegram Account</b>\n\n"
            "Account login module next stage me add kiya jayega."
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "↩️ Account Manager",
                    callback_data="switch_account",
                )
            ]
        ]

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
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

    # -----------------------------------------------------
    # ADMIN PANEL
    # -----------------------------------------------------

    if action == "admin":

        await show_admin(query)
