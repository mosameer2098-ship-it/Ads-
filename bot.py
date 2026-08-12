import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from config import (
    ADMIN_ID,
    BOT_TOKEN,
    BOT_USERNAME,
    FORCE_CHANNEL_USERNAME,
    ADMIN_CONTACT_USERNAME,
)

from database import (
    init_db,
    save_user,
    is_premium,
    get_user_expiry,
    get_bot_config,
    set_source_channel,
    set_time_interval,
    get_user_groups,
    toggle_group_selection,
    set_all_groups_selection,
    get_user_channels,
    get_remaining_days,
    get_active_slot,
    get_slot_session,
    set_active_slot,
    set_slot_stopped,
    add_premium_subscription,
    remove_premium_subscription,
    get_custom_share_message,
    check_referral_eligibility,
    claim_referral_reward,
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# GLOBAL STATES
# ============================================================

user_languages = {}
admin_sub_target = {}
forwarded_counts = {}
failed_counts = {}


# ============================================================
# HELPERS
# ============================================================

def is_admin(user_id):
    return user_id == ADMIN_ID


def has_access(user_id):
    return is_admin(user_id) or is_premium(user_id)


def bot_url():
    return f"https://t.me/{BOT_USERNAME}"


def admin_url():
    username = ADMIN_CONTACT_USERNAME.replace("@", "")
    return f"https://t.me/{username}"


async def check_membership(user_id, context):

    if is_admin(user_id):
        return True

    try:
        member = await context.bot.get_chat_member(
            chat_id=FORCE_CHANNEL_USERNAME,
            user_id=user_id,
        )

        return member.status in (
            "member",
            "administrator",
            "creator",
        )

    except Exception as e:
        logger.warning(
            "Membership check failed for %s: %s",
            user_id,
            e,
        )
        return False


def subscription_label(user_id):

    if is_admin(user_id):
        return "Lifetime (Admin) ♾️"

    try:
        conn = sqlite3.connect("bot_database.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT plan_type
            FROM subscriptions
            WHERE user_id = ?
            AND expiry_date > ?
            """,
            (
                user_id,
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            ),
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            if row[0] in ("referral", "trial"):
                return "Free Referral Trial 🎁"

            return "Paid Premium 💎"

    except Exception:
        pass

    return "Inactive ❌"


# ============================================================
# JOIN REQUIRED SCREEN
# ============================================================

async def show_join_required(update, context):

    text = (
        "🚨 **Channel Join Required!** 🚨\n\n"
        "AdsNova Pro use karne ke liye pehle "
        "hamara channel join karein.\n\n"
        "Join karne ke baad **Check Membership** "
        "button dabayein."
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 Join Channel",
                url=(
                    f"https://t.me/"
                    f"{FORCE_CHANNEL_USERNAME.replace('@', '')}"
                ),
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Check Membership",
                callback_data="check_membership",
            )
        ],
    ])

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


# ============================================================
# ACCESS DENIED
# ============================================================

async def show_subscription_required(update, context):

    text = (
        "❌ **Premium Subscription Required**\n\n"
        "Aapka AdsNova Pro subscription active nahi hai.\n\n"
        "Plan purchase karne ke liye Admin se contact karein."
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🛒 Contact Admin",
                url=admin_url(),
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Back to Menu",
                callback_data="main_menu",
            )
        ],
    ])

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


# ============================================================
# MAIN KEYBOARD
# ============================================================

def main_keyboard(user_id):

    lang = user_languages.get(user_id, "hi")

    keyboard = [
        [
            InlineKeyboardButton(
                "📊 Live Analytics Status",
                callback_data="status",
            ),
            InlineKeyboardButton(
                "⚙️ Settings",
                callback_data="settings",
            ),
        ],
        [
            InlineKeyboardButton(
                "💎 Subscription Details",
                callback_data="subscription",
            )
        ],
        [
            InlineKeyboardButton(
                "🎁 Free Trial (Referral)",
                callback_data="referral_info",
            )
        ],
        [
            InlineKeyboardButton(
                (
                    "🌐 Language: English"
                    if lang == "en"
                    else "🌐 Language: Hinglish"
                ),
                callback_data="toggle_lang",
            )
        ],
        [
            InlineKeyboardButton(
                "✨ Refresh",
                callback_data="refresh",
            ),
            InlineKeyboardButton(
                "🛠️ Help Centre",
                callback_data="help_centre",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# START
# ============================================================

async def start(update, context):

    user = update.effective_user

    save_user(user)

    # Referral
    if context.args:

        arg = context.args[0]

        if arg.startswith("ref_"):

            try:
                referrer_id = int(
                    arg.split("_")[1]
                )

                if (
                    referrer_id != user.id
                    and check_referral_eligibility(
                        user.id
                    )
                ):
                    if claim_referral_reward(user.id):

                        await context.bot.send_message(
                            user.id,
                            (
                                "🎁 **Badhai ho!**\n\n"
                                "Aapko referral se "
                                "**2 din ka Free Trial** mil gaya!"
                            ),
                            parse_mode="Markdown",
                        )

            except Exception as e:
                logger.warning(
                    "Referral error: %s",
                    e,
                )

    if not await check_membership(
        user.id,
        context,
    ):
        await show_join_required(
            update,
            context,
        )
        return

    text = (
        "💎 **AdsNova Pro Bot** 💎\n\n"
        "✨ Premium Automation Service\n"
        "⚡ Fast & Reliable Configuration\n"
        "📊 Live Analytics\n"
        "🎁 Referral Trial System\n\n"
        "👇 **Main Menu:**"
    )

    keyboard = main_keyboard(user.id)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


# ============================================================
# STATUS
# ============================================================

async def status_command(update, context):

    user_id = update.effective_user.id

    if not await check_membership(
        user_id,
        context,
    ):
        await show_join_required(
            update,
            context,
        )
        return

    if not has_access(user_id):

        await show_subscription_required(
            update,
            context,
        )
        return

    config = get_bot_config(user_id)

    source = (
        config[0]
        if config and config[0]
        else "Not Set"
    )

    interval = (
        config[1]
        if config and config[1]
        else 30
    )

    active_slot = get_active_slot(user_id)

    slot = get_slot_session(
        user_id,
        active_slot,
    )

    if slot:
        account_status = "Configured ✅"
        account_name = slot[2] or "N/A"
        stopped = slot[3]
    else:
        account_status = "Not Configured"
        account_name = "N/A"
        stopped = 1

    forwarding_status = (
        "Stopped 🛑"
        if stopped
        else "Active 🟢"
    )

    groups = get_user_groups(user_id)

    selected = sum(
        1
        for group in groups
        if group[2] == 1
    )

    sent = forwarded_counts.get(
        user_id,
        0,
    )

    failed = failed_counts.get(
        user_id,
        0,
    )

    sub_label = subscription_label(user_id)

    if is_admin(user_id):
        expiry = "Unlimited"
    else:
        expiry = get_user_expiry(user_id)

    text = (
        "📊 **AdsNova Pro - Live Analytics**\n\n"
        f"🆔 User ID: `{user_id}`\n"
        f"📂 Active Slot: {active_slot}\n"
        f"🔐 Account Status: {account_status}\n"
        f"🏷️ Account Name: {account_name}\n\n"
        f"💎 Subscription: {sub_label}\n"
        f"⏳ Expiry: `{expiry}`\n\n"
        f"🚀 Forwarding Status: {forwarding_status}\n"
        f"📢 Source Channel: {source}\n"
        f"👥 Selected Groups: {selected}\n"
        f"⏱️ Interval: {interval} seconds\n\n"
        "📈 **Performance**\n"
        f"⚡ Successfully Sent: `{sent}`\n"
        f"⚠️ Failed: `{failed}`"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔙 Back to Menu",
                callback_data="main_menu",
            )
        ]
    ])

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


# ============================================================
# STOP
# ============================================================

async def stop_command(update, context):

    user_id = update.effective_user.id

    if not await check_membership(
        user_id,
        context,
    ):
        return

    if not has_access(user_id):
        return

    slot = get_active_slot(user_id)

    if not get_slot_session(
        user_id,
        slot,
    ):
        await update.message.reply_text(
            "ℹ️ Abhi koi configured account slot nahi hai."
        )
        return

    set_slot_stopped(
        user_id,
        slot,
        1,
    )

    await update.message.reply_text(
        f"🛑 Slot {slot} stopped successfully."
    )


# ============================================================
# LOGOUT
# ============================================================

async def logout_command(update, context):

    user_id = update.effective_user.id

    if not await check_membership(
        user_id,
        context,
    ):
        return

    if not has_access(user_id):
        return

    await update.message.reply_text(
        "ℹ️ Account login/logout ko is safe version "
        "me bot ke through handle nahi kiya jata.\n\n"
        "Aap Settings me apna forwarding configuration "
        "manage kar sakte hain."
    )


# ============================================================
# SUBSCRIPTION
# ============================================================

async def subscription_page(update, context):

    user_id = update.effective_user.id

    if is_admin(user_id):

        text = (
            "💎 **Subscription Details**\n\n"
            "🌟 Status: Active ✅\n"
            "🏷️ Type: Lifetime (Admin) ♾️\n"
            "⏳ Expiry: Unlimited"
        )

    elif is_premium(user_id):

        expiry = get_user_expiry(user_id)
        remaining = get_remaining_days(user_id)
        label = subscription_label(user_id)

        text = (
            "💎 **Subscription Details**\n\n"
            "🌟 Status: Active ✅\n"
            f"🏷️ Type: {label}\n"
            f"⏳ Expiry: `{expiry}`\n"
            f"⏱️ Remaining: `{remaining}`"
        )

    else:

        text = (
            "💎 **AdsNova Pro Pricing**\n\n"
            "❌ Status: Inactive\n\n"
            "📦 **Available Plans:**\n\n"
            "💎 ₹399 — 1 Month\n"
            "💎 ₹799 — 3 Months\n"
            "💎 ₹1999 — 6 Months\n\n"
            "Purchase ke liye Admin se contact karein."
        )

    keyboard = []

    if not is_admin(user_id) and not is_premium(user_id):
        keyboard.append([
            InlineKeyboardButton(
                "🛒 Contact Admin",
                url=admin_url(),
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Back to Menu",
            callback_data="main_menu",
        )
    ])

    markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=markup,
        )


# ============================================================
# REFERRAL
# ============================================================

async def referral_page(update, context):

    user_id = update.effective_user.id

    link = (
        f"https://t.me/{BOT_USERNAME}"
        f"?start=ref_{user_id}"
    )

    share_text = (
        "🎁 AdsNova Pro ko 2 din free test karo!\n"
        f"{link}"
    )

    share_url = (
        "https://t.me/share/url?"
        f"url={link}&text={share_text}"
    )

    text = (
        "🎁 **Referral & Free Trial**\n\n"
        "Apna unique referral link share karein:\n\n"
        f"`{link}`\n\n"
        "🎁 Referral se join karne wale user ko "
        "**2 din ka Free Trial** mil sakta hai."
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🚀 Share Link",
                url=share_url,
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Back to Menu",
                callback_data="main_menu",
            )
        ],
    ])

    await update.callback_query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# ============================================================
# SETTINGS
# ============================================================

async def settings_page(update, context):

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 Source Channel",
                callback_data="opt_1",
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Target Groups",
                callback_data="opt_2",
            )
        ],
        [
            InlineKeyboardButton(
                "⏱️ Time Interval",
                callback_data="opt_3",
            )
        ],
        [
            InlineKeyboardButton(
                "💬 Share Message",
                callback_data="opt_4",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Back to Menu",
                callback_data="main_menu",
            )
        ],
    ])

    await update.callback_query.edit_message_text(
        "⚙️ **AdsNova Pro Settings**",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# ============================================================
# SOURCE CHANNEL
# ============================================================

async def source_channel_page(update, context):

    user_id = update.effective_user.id

    channels = get_user_channels(user_id)

    if not channels:

        await update.callback_query.edit_message_text(
            "❌ Database me koi channel available nahi hai.\n\n"
            "Pehle apne authorized Telegram integration "
            "se channels configure karein.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="settings",
                    )
                ]
            ]),
        )
        return

    keyboard = []

    for index, (_, name) in enumerate(channels):

        keyboard.append([
            InlineKeyboardButton(
                f"📌 {name}",
                callback_data=f"channel_{index}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Back",
            callback_data="settings",
        )
    ])

    await update.callback_query.edit_message_text(
        "📢 **Select Source Channel**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ============================================================
# GROUPS
# ============================================================

async def groups_page(update, context):

    user_id = update.effective_user.id

    groups = get_user_groups(user_id)

    if not groups:

        await update.callback_query.edit_message_text(
            "❌ Database me koi target group available nahi hai.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="settings",
                    )
                ]
            ]),
        )
        return

    keyboard = []

    for group_id, name, selected in groups[:40]:

        icon = "✅" if selected else "☑️"

        keyboard.append([
            InlineKeyboardButton(
                f"{icon} {name}",
                callback_data=f"group_{group_id}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "☑️ Select All",
            callback_data="groups_all",
        ),
        InlineKeyboardButton(
            "🔲 Deselect All",
            callback_data="groups_none",
        ),
    ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Back",
            callback_data="settings",
        )
    ])

    await update.callback_query.edit_message_text(
        "👥 **Target Groups**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ============================================================
# TIME SETTINGS
# ============================================================

async def time_page(update, context):

    config = get_bot_config(
        update.effective_user.id
    )

    current = config[1] if config else 30

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⚡ 20s",
                callback_data="time_20",
            ),
            InlineKeyboardButton(
                "⚡ 30s",
                callback_data="time_30",
            ),
            InlineKeyboardButton(
                "⚡ 60s",
                callback_data="time_60",
            ),
        ],
        [
            InlineKeyboardButton(
                "⚡ 120s",
                callback_data="time_120",
            ),
            InlineKeyboardButton(
                "⚡ 300s",
                callback_data="time_300",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="settings",
            )
        ],
    ])

    await update.callback_query.edit_message_text(
        f"⏱️ **Time Interval Settings**\n\n"
        f"Current: `{current}` seconds",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# ============================================================
# HELP
# ============================================================

async def help_page(update, context):

    text = (
        "💡 **AdsNova Pro Help Centre**\n\n"
        "1️⃣ Subscription active karein.\n"
        "2️⃣ Source channel configure karein.\n"
        "3️⃣ Target groups select karein.\n"
        "4️⃣ Posting interval choose karein.\n"
        "5️⃣ Status page se configuration check karein.\n\n"
        "🔐 Security: Bot OTP, 2FA password ya "
        "Telegram session credentials collect nahi karta.\n\n"
        f"📞 Admin: @{ADMIN_CONTACT_USERNAME}"
    )

    await update.callback_query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="main_menu",
                )
            ]
        ]),
    )


# ============================================================
# ADMIN PANEL
# ============================================================

async def admin_command(update, context):

    if not is_admin(update.effective_user.id):
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "💎 Manage Subscription",
                callback_data="admin_sub",
            )
        ],
        [
            InlineKeyboardButton(
                "📊 User Stats",
                callback_data="admin_stats",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Main Menu",
                callback_data="main_menu",
            )
        ],
    ])

    await update.message.reply_text(
        "👑 **AdsNova Pro Admin Panel**",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# ============================================================
# ADD SUB
# ============================================================

async def addsub_command(update, context):

    if not is_admin(update.effective_user.id):
        return

    if not context.args:

        await update.message.reply_text(
            "Usage:\n"
            "`/addsub USER_ID DAYS`",
            parse_mode="Markdown",
        )
        return

    try:

        target = int(context.args[0])

        days = (
            int(context.args[1])
            if len(context.args) > 1
            else 30
        )

        add_premium_subscription(
            target,
            days=days,
            plan_type="paid",
        )

        await update.message.reply_text(
            f"✅ User `{target}` ko {days} days "
            "premium de diya gaya.",
            parse_mode="Markdown",
        )

    except Exception as e:

        await update.message.reply_text(
            f"❌ Error: {e}"
        )


# ============================================================
# DELETE SUB
# ============================================================

async def delsub_command(update, context):

    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        return

    try:

        target = int(context.args[0])

        remove_premium_subscription(target)

        await update.message.reply_text(
            f"✅ User `{target}` ka subscription remove kar diya.",
            parse_mode="Markdown",
        )

    except Exception as e:

        await update.message.reply_text(
            f"❌ Error: {e}"
        )


# ============================================================
# ADMIN STATS
# ============================================================

async def admin_stats(update, context):

    if not is_admin(update.effective_user.id):
        return

    try:

        conn = sqlite3.connect(
            "bot_database.db"
        )

        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM users"
        )

        users = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM subscriptions
            WHERE expiry_date > ?
            """,
            (
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            ),
        )

        premium = cursor.fetchone()[0]

        conn.close()

    except Exception:

        users = 0
        premium = 0

    text = (
        "📊 **Admin Statistics**\n\n"
        f"👥 Total Users: `{users}`\n"
        f"💎 Active Premium: `{premium}`\n"
        f"⚡ Runtime Sent: `{sum(forwarded_counts.values())}`\n"
        f"⚠️ Runtime Failed: `{sum(failed_counts.values())}`"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="main_menu",
            )
        ]
    ])

    if update.callback_query:

        await update.callback_query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


# ============================================================
# BROADCAST
# ============================================================

async def broadcast_command(update, context):

    if not is_admin(update.effective_user.id):
        return

    if not context.args:

        await update.message.reply_text(
            "Usage:\n`/broadcast Your message`",
            parse_mode="Markdown",
        )
        return

    message = " ".join(context.args)

    conn = sqlite3.connect(
        "bot_database.db"
    )

    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id FROM users"
    )

    users = cursor.fetchall()

    conn.close()

    sent = 0
    failed = 0

    for row in users:

        try:

            await context.bot.send_message(
                chat_id=row[0],
                text=message,
            )

            sent += 1

            forwarded_counts[ADMIN_ID] = (
                forwarded_counts.get(ADMIN_ID, 0) + 1
            )

            await asyncio.sleep(0.05)

        except Exception:

            failed += 1

            failed_counts[ADMIN_ID] = (
                failed_counts.get(ADMIN_ID, 0) + 1
            )

    await update.message.reply_text(
        f"✅ Broadcast completed.\n\n"
        f"📨 Sent: {sent}\n"
        f"⚠️ Failed: {failed}"
    )


# ============================================================
# BUTTON HANDLER
# ============================================================

async def button_handler(update, context):

    query = update.callback_query

    await query.answer()

    data = query.data
    user_id = query.from_user.id

    # Membership
    if data == "check_membership":

        if await check_membership(
            user_id,
            context,
        ):
            await start(
                update,
                context,
            )
        else:
            await query.answer(
                "❌ Channel abhi join nahi hua.",
                show_alert=True,
            )

        return

    # Language
    if data == "toggle_lang":

        old = user_languages.get(
            user_id,
            "hi",
        )

        user_languages[user_id] = (
            "en"
            if old == "hi"
            else "hi"
        )

        await start(
            update,
            context,
        )
        return

    # Membership required
    if not await check_membership(
        user_id,
        context,
    ):

        await show_join_required(
            update,
            context,
        )
        return

    # Main menu
    if data == "main_menu":

        await start(
            update,
            context,
        )
        return

    # Subscription
    if data == "subscription":

        await subscription_page(
            update,
            context,
        )
        return

    # Referral
    if data == "referral_info":

        await referral_page(
            update,
            context,
        )
        return

    # Help
    if data == "help_centre":

        await help_page(
            update,
            context,
        )
        return

    # Refresh
    if data == "refresh":

        await start(
            update,
            context,
        )
        return

    # Access
    if not has_access(user_id):

        await show_subscription_required(
            update,
            context,
        )
        return

    # Status
    if data == "status":

        await status_command(
            update,
            context,
        )
        return

    # Settings
    if data == "settings":

        await settings_page(
            update,
            context,
        )
        return

    # Source channel
    if data == "opt_1":

        await source_channel_page(
            update,
            context,
        )
        return

    if data.startswith("channel_"):

        try:

            index = int(
                data.split("_")[1]
            )

            channels = get_user_channels(
                user_id
            )

            if index < len(channels):

                channel_name = channels[index][1]

                set_source_channel(
                    user_id,
                    channel_name,
                )

                await query.answer(
                    "✅ Source channel set!",
                    show_alert=True,
                )

                await settings_page(
                    update,
                    context,
                )

        except Exception as e:

            await query.answer(
                f"Error: {e}",
                show_alert=True,
            )

        return

    # Groups
    if data == "opt_2":

        await groups_page(
            update,
            context,
        )
        return

    if data.startswith("group_"):

        try:

            group_id = data.split(
                "group_",
                1
            )[1]

            toggle_group_selection(
                user_id,
                group_id,
            )

            await groups_page(
                update,
                context,
            )

        except Exception as e:

            await query.answer(
                f"Error: {e}",
                show_alert=True,
            )

        return

    if data == "groups_all":

        set_all_groups_selection(
            user_id,
            1,
        )

        await groups_page(
            update,
            context,
        )
        return

    if data == "groups_none":

        set_all_groups_selection(
            user_id,
            0,
        )

        await groups_page(
            update,
            context,
        )
        return

    # Time
    if data == "opt_3":

        await time_page(
            update,
            context,
        )
        return

    if data.startswith("time_"):

        try:

            seconds = int(
                data.split("_")[1]
            )

            set_time_interval(
                user_id,
                seconds,
            )

            await query.answer(
                f"✅ Interval set: {seconds}s",
                show_alert=True,
            )

            await time_page(
                update,
                context,
            )

        except Exception as e:

            await query.answer(
                f"Error: {e}",
                show_alert=True,
            )

        return

    # Share message
    if data == "opt_4":

        current = get_custom_share_message(
            user_id
        )

        await query.edit_message_text(
            "💬 **Share Message**\n\n"
            f"Current message:\n`{current}`\n\n"
            "Custom message editing ko safe version "
            "me direct Telegram account access ke bina "
            "handle kiya ja sakta hai.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="settings",
                    )
                ]
            ]),
        )

        return

    # Admin subscription
    if data == "admin_sub":

        if not is_admin(user_id):
            return

        admin_sub_target[user_id] = {
            "step": "target"
        }

        await query.edit_message_text(
            "💎 **Manage Subscription**\n\n"
            "Ab jis user ko subscription dena hai "
            "uski Telegram User ID message me bhejein.\n\n"
            "Example: `123456789`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 Cancel",
                        callback_data="main_menu",
                    )
                ]
            ]),
        )

        return

    # Admin stats
    if data == "admin_stats":

        await admin_stats(
            update,
            context,
        )
        return


# ============================================================
# TEXT HANDLER
# ============================================================

async def handle_message(update, context):

    user_id = update.effective_user.id

    if not update.message:
        return

    text = update.message.text.strip()

    # Admin subscription target
    if (
        is_admin(user_id)
        and user_id in admin_sub_target
        and admin_sub_target[user_id].get("step")
        == "target"
    ):

        try:

            target_id = int(text)

            admin_sub_target[user_id] = {
                "step": "plan",
                "target_id": target_id,
            }

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "💎 ₹399 — 30 Days",
                        callback_data="plan_30",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "💎 ₹799 — 90 Days",
                        callback_data="plan_90",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "💎 ₹1999 — 180 Days",
                        callback_data="plan_180",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔙 Cancel",
                        callback_data="main_menu",
                    )
                ],
            ])

            await update.message.reply_text(
                f"✅ Target ID: `{target_id}`\n\n"
                "Plan select karein:",
                parse_mode="Markdown",
                reply_markup=keyboard,
            )

        except ValueError:

            await update.message.reply_text(
                "❌ Valid numeric Telegram User ID bhejein."
            )

        return


# ============================================================
# ADMIN PLAN CALLBACK
# ============================================================

async def admin_plan_handler(update, context):

    query = update.callback_query

    if query.from_user.id != ADMIN_ID:
        await query.answer()
        return

    await query.answer()

    data = query.data

    if not data.startswith("plan_"):
        return

    try:

        days = int(
            data.split("_")[1]
        )

        target_data = admin_sub_target.get(
            ADMIN_ID,
            {}
        )

        target_id = target_data.get(
            "target_id"
        )

        if not target_id:

            await query.answer(
                "❌ Target user missing.",
                show_alert=True,
            )
            return

        add_premium_subscription(
            target_id,
            days=days,
            plan_type="paid",
        )

        admin_sub_target.pop(
            ADMIN_ID,
            None,
        )

        await query.edit_message_text(
            f"✅ **Subscription Added!**\n\n"
            f"👤 User ID: `{target_id}`\n"
            f"💎 Duration: `{days} days`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 Main Menu",
                        callback_data="main_menu",
                    )
                ]
            ]),
        )

    except Exception as e:

        await query.edit_message_text(
            f"❌ Error: {e}"
        )


# ============================================================
# COMMAND SETUP
# ============================================================

async def post_init(application):

    await application.bot.set_my_commands([
        BotCommand(
            "start",
            "Start AdsNova Pro",
        ),
        BotCommand(
            "menu",
            "Open Main Menu",
        ),
        BotCommand(
            "status",
            "Check Status",
        ),
        BotCommand(
            "stop",
            "Stop configuration",
        ),
        BotCommand(
            "logout",
            "Account information",
        ),
        BotCommand(
            "admin",
            "Admin Panel",
        ),
        BotCommand(
            "addsub",
            "Add Premium",
        ),
        BotCommand(
            "delsub",
            "Remove Premium",
        ),
        BotCommand(
            "broadcast",
            "Broadcast Message",
        ),
    ])

    logger.info(
        "AdsNova Pro bot initialized."
    )


# ============================================================
# APPLICATION
# ============================================================

def build_application():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing from config.py"
        )

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "menu",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "status",
            status_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "stop",
            stop_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "logout",
            logout_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "admin",
            admin_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "addsub",
            addsub_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "delsub",
            delsub_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "broadcast",
            broadcast_command,
        )
    )

    # Admin plan callbacks
    application.add_handler(
        CallbackQueryHandler(
            admin_plan_handler,
            pattern=r"^plan_\d+$",
        )
    )

    # General callbacks
    application.add_handler(
        CallbackQueryHandler(
            button_handler,
        )
    )

    # Text
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    return application


# ============================================================
# ASYNC HEROKU RUNNER
# ============================================================

async def run_bot():

    init_db()

    application = build_application()

    logger.info(
        "========================================"
    )
    logger.info(
        "AdsNova Pro Bot Starting..."
    )
    logger.info(
        "Python async runner enabled"
    )
    logger.info(
        "Heroku event-loop safe mode enabled"
    )
    logger.info(
        "========================================"
    )

    try:

        # Initialize application
        await application.initialize()

        # Run post_init manually because we are
        # not using application.run_polling()
        await post_init(application)

        # Start application
        await application.start()

        # Start Telegram polling
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )

        logger.info(
            "========================================"
        )
        logger.info(
            "AdsNova Pro Bot is ONLINE ✅"
        )
        logger.info(
            "Telegram polling started successfully."
        )
        logger.info(
            "========================================"
        )

        # Keep worker alive
        await asyncio.Event().wait()

    except asyncio.CancelledError:

        logger.info(
            "Bot shutdown requested."
        )

    except Exception as e:

        logger.exception(
            "BOT CRASHED: %s",
            e,
        )

        raise

    finally:

        logger.info(
            "Stopping AdsNova Pro Bot..."
        )

        try:

            if application.updater:
                await application.updater.stop()

        except Exception:
            pass

        try:

            await application.stop()

        except Exception:
            pass

        try:

            await application.shutdown()

        except Exception:
            pass

        logger.info(
            "AdsNova Pro Bot stopped."
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            run_bot()
        )

    except KeyboardInterrupt:

        logger.info(
            "Bot stopped by user."
        )

    except Exception as e:

        logger.exception(
            "Fatal error: %s",
            e,
        )
