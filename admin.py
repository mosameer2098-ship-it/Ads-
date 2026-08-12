import asyncio
import sqlite3
import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import ContextTypes

from config import (
    ADMIN_ID,
    BOT_USERNAME,
    ADMIN_CONTACT_USERNAME
)

from database import (
    add_premium_subscription,
    remove_premium_subscription
)


logger = logging.getLogger(__name__)


# ============================================================
# ADMIN SUBSCRIPTION STATE
# ============================================================

admin_sub_target = {}


# ============================================================
# ADMIN PANEL
# ============================================================

async def admin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ADMIN_ID:
        return

    admin_text = (
        "👑 **Admin Control Panel** 👑\n\n"
        "Aap niche diye gaye button se direct plans "
        "manage kar sakte hain ya stats dekh sakte hain:"
    )

    reply_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "💎 Manage Subscriptions (Plans)",
                callback_data="admin_manage_sub"
            )
        ],
        [
            InlineKeyboardButton(
                "📊 View User Stats",
                callback_data="admin_user_stats"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Back to Menu",
                callback_data="main_menu"
            )
        ]
    ])

    await update.message.reply_text(
        admin_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


# ============================================================
# ADD SUBSCRIPTION
# ============================================================

async def addsub_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:

        await update.message.reply_text(
            "❌ Usage: `/addsub <user_id> [days]`",
            parse_mode="Markdown"
        )

        return

    try:

        target_id = int(
            context.args[0]
        )

        days = (
            int(context.args[1])
            if len(context.args) > 1
            else 30
        )

        add_premium_subscription(
            target_id,
            days=days
        )

        await update.message.reply_text(
            f"✅ User `{target_id}` ko **{days} din** "
            "ka paid subscription successfully mil gaya!",
            parse_mode="Markdown"
        )

    except Exception as e:

        await update.message.reply_text(
            f"❌ Error: {e}"
        )


# ============================================================
# DELETE SUBSCRIPTION
# ============================================================

async def delsub_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:

        await update.message.reply_text(
            "❌ Usage: `/delsub <user_id>`",
            parse_mode="Markdown"
        )

        return

    try:

        target_id = int(
            context.args[0]
        )

        remove_premium_subscription(
            target_id
        )

        await update.message.reply_text(
            f"❌ User `{target_id}` ka subscription "
            "hata diya gaya.",
            parse_mode="Markdown"
        )

    except Exception as e:

        await update.message.reply_text(
            f"❌ Error: {e}"
        )


# ============================================================
# USER STATS
# ============================================================

async def userstats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    forwarded_counts=None,
    failed_counts=None
):

    if update.effective_user.id != ADMIN_ID:
        return

    forwarded_counts = (
        forwarded_counts
        if forwarded_counts is not None
        else {}
    )

    failed_counts = (
        failed_counts
        if failed_counts is not None
        else {}
    )

    if not forwarded_counts and not failed_counts:

        await update.message.reply_text(
            "📊 Abhi tak kisi user ne session start "
            "karke messages forward nahi kiye hain."
        )

        return

    stats_msg = (
        "📊 **Users Forwarding Performance Stats:**\n\n"
    )

    all_users = set(
        list(forwarded_counts.keys())
        + list(failed_counts.keys())
    )

    for user_id in all_users:

        succ = forwarded_counts.get(
            user_id,
            0
        )

        fail = failed_counts.get(
            user_id,
            0
        )

        stats_msg += (
            f"• User ID: `{user_id}`\n"
            f"  ⚡ Sent: {succ} | "
            f"⚠️ Failed: {fail}\n\n"
        )

    await update.message.reply_text(
        stats_msg,
        parse_mode="Markdown"
    )


# ============================================================
# BROADCAST
# ============================================================

async def broadcast_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:

        await update.message.reply_text(
            "❌ Usage:\n"
            "`/broadcast Your message here`",
            parse_mode="Markdown"
        )

        return

    broadcast_msg = " ".join(
        context.args
    )

    bot_link = (
        f"https://t.me/{BOT_USERNAME}"
    )

    reply_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🚀 Start AdsNova Pro",
                url=bot_link
            )
        ]
    ])

    conn = sqlite3.connect(
        "bot_database.db"
    )

    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id FROM users"
    )

    users = cursor.fetchall()

    conn.close()

    sent_count = 0
    failed_count = 0

    for user in users:

        try:

            await context.bot.send_message(
                chat_id=user[0],
                text=broadcast_msg,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )

            sent_count += 1

            await asyncio.sleep(0.05)

        except Exception as e:

            failed_count += 1

            logger.warning(
                f"Broadcast failed for {user[0]}: {e}"
            )

            continue

    await update.message.reply_text(
        "✅ **Broadcast Complete!**\n\n"
        f"📨 Sent: {sent_count}\n"
        f"❌ Failed: {failed_count}",
        parse_mode="Markdown"
    )


# ============================================================
# ADMIN SUBSCRIPTION PANEL
# ============================================================

async def admin_manage_subscription(
    query,
    user_id
):

    if user_id != ADMIN_ID:
        return

    admin_sub_target[user_id] = {
        "step": "waiting_target_id"
    }

    await query.edit_message_text(
        "💎 **Manage Subscriptions Panel**\n\n"
        "Kripya us user ki **Telegram ID** "
        "message mein bhejein jise subscription dena hai:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔙 Cancel",
                    callback_data="admin_cancel"
                )
            ]
        ])
    )


# ============================================================
# ADMIN TARGET USER MESSAGE
# ============================================================

async def handle_admin_subscription_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int
):

    if user_id != ADMIN_ID:
        return False

    if user_id not in admin_sub_target:
        return False

    state = admin_sub_target[user_id]

    if state.get("step") != "waiting_target_id":
        return False

    text = update.message.text.strip()

    try:

        target_id = int(text)

    except ValueError:

        await update.message.reply_text(
            "❌ Kripya valid numeric User ID bhejein:"
        )

        return True

    state["target_id"] = target_id
    state["step"] = "select_plan"

    keyboard = [
        [
            InlineKeyboardButton(
                "💎 ₹399 - 1 Month (30 Days)",
                callback_data="sub_plan_30"
            )
        ],
        [
            InlineKeyboardButton(
                "💎 ₹799 - 3 Month (90 Days)",
                callback_data="sub_plan_90"
            )
        ],
        [
            InlineKeyboardButton(
                "💎 ₹1999 - 6 Month (180 Days)",
                callback_data="sub_plan_180"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Cancel",
                callback_data="admin_cancel"
            )
        ]
    ]

    await update.message.reply_text(
        f"✅ Target User ID: `{target_id}`\n\n"
        "Ab niche diye gaye plans mein se "
        "koi ek select karein:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )

    return True


# ============================================================
# ADMIN PLAN SELECTION
# ============================================================

async def handle_admin_plan(
    query,
    user_id: int,
    data: str
):

    if user_id != ADMIN_ID:
        return False

    days_map = {
        "30": 30,
        "90": 90,
        "180": 180
    }

    days_val = days_map.get(
        data.split("_")[2],
        30
    )

    target_data = admin_sub_target.get(
        user_id,
        {}
    )

    target_id = target_data.get(
        "target_id"
    )

    if not target_id:

        await query.edit_message_text(
            "❌ Error: Target user ID not found.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="main_menu"
                    )
                ]
            ])
        )

        return True

    try:

        add_premium_subscription(
            target_id,
            days=days_val
        )

        admin_sub_target.pop(
            user_id,
            None
        )

        await query.edit_message_text(
            f"✅ Success!\n\n"
            f"👤 User: `{target_id}`\n"
            f"💎 Plan: **{days_val} days**\n"
            "🎉 Subscription successfully assign kar diya gaya hai!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 Back to Menu",
                        callback_data="main_menu"
                    )
                ]
            ])
        )

    except Exception as e:

        await query.edit_message_text(
            f"❌ Subscription Error:\n{e}",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="main_menu"
                    )
                ]
            ])
        )

    return True


# ============================================================
# ADMIN CANCEL
# ============================================================

async def admin_cancel(
    query,
    user_id: int
):

    if user_id != ADMIN_ID:
        return False

    admin_sub_target.pop(
        user_id,
        None
    )

    return True
