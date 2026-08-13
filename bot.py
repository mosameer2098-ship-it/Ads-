import asyncio
import logging
import sqlite3
from datetime import datetime

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
    ContextTypes,
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
    set_active_slot,
    get_slot_session,
    get_user_sessions,
    save_user_session,
    remove_user_session,
    set_slot_stopped,
    add_premium_subscription,
    remove_premium_subscription,
    get_custom_share_message,
    check_referral_eligibility,
    claim_referral_reward,
    save_real_groups_and_channels,
)

try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import (
        SessionPasswordNeededError,
        PhoneCodeInvalidError,
        PhoneCodeExpiredError,
        PasswordHashInvalidError,
    )
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False

try:
    from config import API_ID, API_HASH
except ImportError:
    API_ID = 0
    API_HASH = ""

MAX_SLOTS = 20

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

user_languages = {}
admin_sub_target = {}
forwarded_counts = {}
failed_counts = {}
login_states = {}


def is_admin(user_id):
    return user_id == ADMIN_ID


def has_access(user_id):
    return is_admin(user_id) or is_premium(user_id)


def admin_url():
    username = (ADMIN_CONTACT_USERNAME or "").replace("@", "")
    return f"https://t.me/{username}"


def force_channel_url():
    username = (FORCE_CHANNEL_USERNAME or "").replace("@", "")
    return f"https://t.me/{username}"


def subscription_label(user_id):
    if is_admin(user_id):
        return "Lifetime (Admin) ♾️"

    try:
        conn = sqlite3.connect("bot_database.db")

        row = conn.execute(
            """
            SELECT plan_type
            FROM subscriptions
            WHERE user_id = ?
              AND expiry_date > ?
            """,
            (
                user_id,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        ).fetchone()

        conn.close()

        if row:
            if row[0] in ("referral", "trial"):
                return "Free Referral Trial 🎁"

            return "Paid Premium 💎"

    except Exception as e:
        logger.warning("Subscription label error: %s", e)

    return "Inactive ❌"


async def check_membership(user_id, context):
    if is_admin(user_id) or not FORCE_CHANNEL_USERNAME:
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


async def show_join_required(update, context):
    text = (
        "🚨 **Channel Join Required!** 🚨\n\n"
        "AdsNova Pro use karne ke liye pehle hamara channel join karein.\n\n"
        "Join karne ke baad **Check Membership** button dabayein."
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 Join Channel",
                url=force_channel_url(),
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

    elif update.message:
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


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

    elif update.message:
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


# ============================================================
# ACCOUNT MANAGEMENT
# ============================================================

def account_keyboard(user_id):
    sessions = get_user_sessions(user_id)
    session_map = {int(row[0]): row for row in sessions}

    active_slot = get_active_slot(user_id)

    rows = []

    for start in range(1, MAX_SLOTS + 1, 5):
        row = []

        for slot in range(start, start + 5):
            session = session_map.get(slot)

            if session:
                if slot == active_slot:
                    label = f"👉 {slot}"
                else:
                    label = f"🔴 {slot}"

                row.append(
                    InlineKeyboardButton(
                        label,
                        callback_data=f"switch_{slot}",
                    )
                )

            else:
                row.append(
                    InlineKeyboardButton(
                        f"🟢 {slot}",
                        callback_data=f"empty_slot_{slot}",
                    )
                )

        rows.append(row)

    rows.append([
        InlineKeyboardButton(
            "🔐 Login New Account",
            callback_data="login_account",
        )
    ])

    rows.append([
        InlineKeyboardButton(
            "🗑️ Remove Account",
            callback_data="remove_account",
        )
    ])

    rows.append([
        InlineKeyboardButton(
            "🔙 Back to Menu",
            callback_data="main_menu",
        )
    ])

    return InlineKeyboardMarkup(rows)


async def accounts_page(update, context):
    user_id = update.effective_user.id

    sessions = get_user_sessions(user_id)
    active_slot = get_active_slot(user_id)

    connected = len(sessions)

    text = (
        "🔄 **Switch Account**\n\n"
        f"👉 You are currently using **Slot {active_slot}**.\n"
        f"📊 **{connected}/{MAX_SLOTS} slots filled**\n\n"
        "🔴 = Account connected\n"
        "🟢 = Empty slot\n"
        "👉 = Currently active\n\n"
        "Select a slot to switch:"
    )

    await update.callback_query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=account_keyboard(user_id),
    )


async def login_page(update, context):
    user_id = update.effective_user.id

    if not TELETHON_AVAILABLE:
        await update.callback_query.edit_message_text(
            "❌ Telethon installed nahi hai.\n\n"
            "Requirements me `telethon` add karo.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="accounts",
                    )
                ]
            ]),
        )
        return

    if not API_ID or not API_HASH:
        await update.callback_query.edit_message_text(
            "❌ API_ID / API_HASH configured nahi hai.\n\n"
            "Config.py me Telegram API credentials add karo.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="accounts",
                    )
                ]
            ]),
        )
        return

    sessions = get_user_sessions(user_id)

    used_slots = {
        int(row[0])
        for row in sessions
    }

    free_slot = next(
        (
            slot
            for slot in range(1, MAX_SLOTS + 1)
            if slot not in used_slots
        ),
        None,
    )

    if free_slot is None:
        await update.callback_query.edit_message_text(
            "⚠️ **20/20 Account Slots Full**\n\n"
            "Pehle kisi purane account ko remove karo.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "👤 Switch Account",
                        callback_data="accounts",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="settings",
                    )
                ],
            ]),
        )
        return

    login_states[user_id] = {
        "step": "phone",
        "slot": free_slot,
        "client": None,
        "phone": None,
    }

    await update.callback_query.edit_message_text(
        f"🔐 **Login Telegram Account**\n\n"
        f"📂 New Slot: **{free_slot}/{MAX_SLOTS}**\n\n"
        "Apna Telegram phone number bhejo.\n\n"
        "Example:\n`+919876543210`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="cancel_login",
                )
            ]
        ]),
    )


async def start_telegram_login(user_id, phone):
    client = TelegramClient(
        StringSession(),
        int(API_ID),
        API_HASH,
    )

    await client.connect()

    sent = await client.send_code_request(phone)

    login_states[user_id]["client"] = client
    login_states[user_id]["phone"] = phone
    login_states[user_id]["phone_code_hash"] = sent.phone_code_hash
    login_states[user_id]["step"] = "otp"

    return client


async def handle_login_message(update, context):
    user = update.effective_user

    if (
        not user
        or not update.message
        or not update.message.text
    ):
        return False

    user_id = user.id

    state = login_states.get(user_id)

    if not state:
        return False

    text = update.message.text.strip()
    step = state.get("step")

    if step == "phone":
        phone = text.replace(" ", "")

        if not phone.startswith("+"):
            await update.message.reply_text(
                "❌ Country code ke saath phone number bhejo.\n\n"
                "Example: `+919876543210`",
                parse_mode="Markdown",
            )
            return True

        try:
            await update.message.reply_text(
                "⏳ Login request bhej raha hoon..."
            )

            await start_telegram_login(
                user_id,
                phone,
            )

            await update.message.reply_text(
                "📩 **OTP Sent!**\n\n"
                "Telegram app me aaya login code yahan bhejo.\n\n"
                "Example: `12345`",
                parse_mode="Markdown",
            )

        except Exception as e:
            logger.exception("Login phone error")

            state = login_states.pop(
                user_id,
                None,
            )

            if state and state.get("client"):
                try:
                    await state["client"].disconnect()
                except Exception:
                    pass

            await update.message.reply_text(
                f"❌ Login start failed:\n`{e}`",
                parse_mode="Markdown",
            )

        return True

    if step == "otp":
        client = state.get("client")

        if not client:
            login_states.pop(
                user_id,
                None,
            )

            await update.message.reply_text(
                "❌ Login session expire ho gayi. "
                "Dobara Login Account dabao."
            )

            return True

        try:
            await client.sign_in(
                phone=state["phone"],
                code=text,
                phone_code_hash=state["phone_code_hash"],
            )

        except SessionPasswordNeededError:
            state["step"] = "password"

            await update.message.reply_text(
                "🔐 **2-Step Verification Enabled**\n\n"
                "Apna Telegram 2FA password bhejo.",
                parse_mode="Markdown",
            )

            return True

        except PhoneCodeInvalidError:
            await update.message.reply_text(
                "❌ OTP galat hai. Dobara OTP bhejo."
            )
            return True

        except PhoneCodeExpiredError:
            state = login_states.pop(
                user_id,
                None,
            )

            if state and state.get("client"):
                try:
                    await state["client"].disconnect()
                except Exception:
                    pass

            await update.message.reply_text(
                "❌ OTP expire ho gaya. "
                "Dobara Login Account se login karo."
            )

            return True

        except Exception as e:
            logger.exception("OTP login error")

            state = login_states.pop(
                user_id,
                None,
            )

            if state and state.get("client"):
                try:
                    await state["client"].disconnect()
                except Exception:
                    pass

            await update.message.reply_text(
                f"❌ Login failed:\n`{e}`",
                parse_mode="Markdown",
            )

            return True

        await finish_login(
            update,
            user_id,
        )

        return True

    if step == "password":
        client = state.get("client")

        if not client:
            login_states.pop(
                user_id,
                None,
            )

            await update.message.reply_text(
                "❌ Login session expire ho gayi."
            )

            return True

        try:
            await client.sign_in(
                password=text
            )

        except PasswordHashInvalidError:
            await update.message.reply_text(
                "❌ 2FA password galat hai. Dobara bhejo."
            )
            return True

        except Exception as e:
            logger.exception("2FA login error")

            state = login_states.pop(
                user_id,
                None,
            )

            if state and state.get("client"):
                try:
                    await state["client"].disconnect()
                except Exception:
                    pass

            await update.message.reply_text(
                f"❌ 2FA login failed:\n`{e}`",
                parse_mode="Markdown",
            )

            return True

        await finish_login(
            update,
            user_id,
        )

        return True

    return False


async def finish_login(update, user_id):
    state = login_states.get(user_id)

    if not state:
        return

    client = state.get("client")
    slot = state.get("slot")
    phone = state.get("phone")

    try:
        me = await client.get_me()

        session_string = client.session.save()

        account_name = (
            " ".join(
                filter(
                    None,
                    [
                        me.first_name,
                        me.last_name,
                    ],
                )
            )
            or me.username
            or str(me.id)
        )

        dialogs = await client.get_dialogs(
            limit=None
        )

        groups = []
        channels = []

        for dialog in dialogs:
            entity = dialog.entity

            if getattr(
                entity,
                "broadcast",
                False,
            ):
                channels.append(
                    (
                        dialog.id,
                        dialog.title,
                    )
                )

            elif (
                getattr(
                    entity,
                    "megagroup",
                    False,
                )
                or dialog.is_group
            ):
                groups.append(
                    (
                        dialog.id,
                        dialog.title,
                    )
                )

            elif dialog.is_channel:
                channels.append(
                    (
                        dialog.id,
                        dialog.title,
                    )
                )

        save_user_session(
            user_id=user_id,
            slot_number=slot,
            phone=phone,
            session_string=session_string,
            account_name=account_name,
        )

        save_real_groups_and_channels(
            user_id=user_id,
            groups_list=groups,
            channels_list=channels,
        )

        set_active_slot(
            user_id,
            slot,
        )

        set_slot_stopped(
            user_id,
            slot,
            0,
        )

        await client.disconnect()

        login_states.pop(
            user_id,
            None,
        )

        await update.message.reply_text(
            "✅ **Telegram Account Login Successful!**\n\n"
            f"📂 Slot: **{slot}/{MAX_SLOTS}**\n"
            f"👤 Account: **{account_name}**\n"
            f"🆔 Telegram ID: `{me.id}`\n"
            f"📱 Phone: `{phone}`\n\n"
            f"📢 Channels Found: `{len(channels)}`\n"
            f"👥 Groups Found: `{len(groups)}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔄 Switch Account",
                        callback_data="accounts",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⚙️ Settings",
                        callback_data="settings",
                    )
                ],
            ]),
        )

    except Exception as e:
        logger.exception(
            "Finish login error"
        )

        try:
            if client:
                await client.disconnect()
        except Exception:
            pass

        login_states.pop(
            user_id,
            None,
        )

        await update.message.reply_text(
            f"❌ Account save failed:\n`{e}`",
            parse_mode="Markdown",
        )


async def cancel_login(update, context):
    user_id = update.effective_user.id

    state = login_states.pop(
        user_id,
        None,
    )

    if state and state.get("client"):
        try:
            await state["client"].disconnect()
        except Exception:
            pass

    await accounts_page(
        update,
        context,
    )


async def switch_account(update, context, slot):
    user_id = update.effective_user.id

    sessions = get_user_sessions(
        user_id
    )

    found = next(
        (
            row
            for row in sessions
            if int(row[0]) == int(slot)
        ),
        None,
    )

    if not found:
        await update.callback_query.answer(
            "🟢 Ye slot empty hai. "
            "Login New Account use karo.",
            show_alert=True,
        )
        return

    set_active_slot(
        user_id,
        slot,
    )

    await update.callback_query.answer(
        f"👉 Slot {slot} active ho gaya.",
        show_alert=True,
    )

    await accounts_page(
        update,
        context,
    )


async def toggle_slot(update, context):
    user_id = update.effective_user.id

    slot = get_active_slot(
        user_id
    )

    slot_info = get_slot_session(
        user_id,
        slot,
    )

    if not slot_info:
        await update.callback_query.answer(
            "❌ Pehle Telegram account login karo.",
            show_alert=True,
        )
        return

    stopped = int(
        slot_info[3] or 0
    )

    if stopped:
        set_slot_stopped(
            user_id,
            slot,
            0,
        )

        message = (
            f"🟢 Slot {slot} started successfully."
        )

    else:
        set_slot_stopped(
            user_id,
            slot,
            1,
        )

        try:
            from forwarder import close_client

            await close_client(
                user_id,
                slot,
            )
        except Exception:
            pass

        message = (
            f"🔴 Slot {slot} stopped successfully."
        )

    await update.callback_query.answer(
        message,
        show_alert=True,
    )

    await start(
        update,
        context,
    )


async def remove_account_page(update, context):
    user_id = update.effective_user.id

    sessions = get_user_sessions(
        user_id
    )

    if not sessions:
        await update.callback_query.answer(
            "❌ Koi account login nahi hai.",
            show_alert=True,
        )
        return

    keyboard = []

    for (
        slot,
        phone,
        session_string,
        account_name,
        stopped,
    ) in sessions:

        name = (
            account_name
            or phone
            or f"Slot {slot}"
        )

        keyboard.append([
            InlineKeyboardButton(
                f"🗑️ Slot {slot} • {name}",
                callback_data=f"delete_{slot}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Back",
            callback_data="accounts",
        )
    ])

    await update.callback_query.edit_message_text(
        "🗑️ **Remove Account**\n\n"
        "Jis account ko remove karna hai select karo:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


async def delete_account(update, context, slot):
    user_id = update.effective_user.id

    session = get_slot_session(
        user_id,
        slot,
    )

    if not session:
        await update.callback_query.answer(
            "❌ Account nahi mila.",
            show_alert=True,
        )
        return

    remove_user_session(
        user_id,
        slot,
    )

    active = get_active_slot(
        user_id
    )

    if active == slot:
        sessions = get_user_sessions(
            user_id
        )

        if sessions:
            set_active_slot(
                user_id,
                int(sessions[0][0]),
            )
        else:
            set_active_slot(
                user_id,
                1,
            )

    try:
        from forwarder import close_client

        await close_client(
            user_id,
            slot,
        )
    except Exception:
        pass

    await update.callback_query.answer(
        f"✅ Slot {slot} remove ho gaya.",
        show_alert=True,
    )

    await accounts_page(
        update,
        context,
    )


# ============================================================
# MAIN MENU
# ============================================================

def main_keyboard(user_id):
    lang = user_languages.get(
        user_id,
        "hi",
    )

    active_slot = get_active_slot(
        user_id
    )

    slot_info = get_slot_session(
        user_id,
        active_slot,
    )

    if slot_info:
        stopped = int(
            slot_info[3] or 0
        )

        slot_button_text = (
            f"🟢 Start Slot {active_slot}"
            if stopped
            else f"🔴 Stop Slot {active_slot}"
        )

    else:
        slot_button_text = "🔐 Login Account"

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
                slot_button_text,
                callback_data=(
                    "toggle_slot"
                    if slot_info
                    else "login_account"
                ),
            ),
            InlineKeyboardButton(
                "🔄 Switch Account",
                callback_data="accounts",
            ),
        ],
        [
            InlineKeyboardButton(
                "💎 Subscription Details",
                callback_data="subscription",
            ),
            InlineKeyboardButton(
                "🔒 Logout",
                callback_data="logout_info",
            ),
        ],
        [
            InlineKeyboardButton(
                "🎁 Free Trial (Referral)",
                callback_data="referral_info",
            ),
            InlineKeyboardButton(
                "❓ Help",
                callback_data="help_centre",
            ),
        ],
        [
            InlineKeyboardButton(
                (
                    "🌐 Language: English"
                    if lang == "en"
                    else "🌐 Language: Hinglish"
                ),
                callback_data="toggle_lang",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔄 Refresh",
                callback_data="refresh",
            ),
            InlineKeyboardButton(
                "💬 Help Centre",
                callback_data="help_centre",
            ),
        ],
    ]

    return InlineKeyboardMarkup(
        keyboard
    )


async def start(update, context):
    user = update.effective_user

    if not user:
        return

    save_user(user)

    if context.args:
        arg = context.args[0]

        if arg.startswith("ref_"):
            try:
                referrer_id = int(
                    arg.split(
                        "_",
                        1,
                    )[1]
                )

                if (
                    referrer_id != user.id
                    and check_referral_eligibility(
                        user.id
                    )
                ):
                    if claim_referral_reward(
                        user.id
                    ):
                        await context.bot.send_message(
                            chat_id=user.id,
                            text=(
                                "🎁 **Badhai ho!**\n\n"
                                "Aapko referral se "
                                "**2 din ka Free Trial** "
                                "mil gaya!"
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
        "💎 **Premium Service - Fast & Reliable**\n"
        "🎲 Random intervals for natural posting\n"
        "🔒 Your profile stays unchanged\n\n"
        "📱 **Choose an option below:**"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=main_keyboard(
                user.id
            ),
        )

    elif update.message:
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=main_keyboard(
                user.id
            ),
        )


# ============================================================
# USER STATUS
# ============================================================

async def user_status_command(update, context):
    """
    Normal user's personal status.
    Admin is handled separately in status_command().
    """

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

    config = get_bot_config(
        user_id
    )

    source = (
        config[0]
        if config and config[0]
        else "Not Set"
    )

    interval = (
        config[1]
        if config and len(config) > 1
        else 30
    )

    active_slot = get_active_slot(
        user_id
    )

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
        "Stopped 🔴"
        if stopped
        else "Active 🟢"
    )

    groups = get_user_groups(
        user_id
    )

    selected = sum(
        1
        for group in groups
        if group[2] == 1
    )

    sessions = get_user_sessions(
        user_id
    )

    sent = forwarded_counts.get(
        user_id,
        0,
    )

    failed = failed_counts.get(
        user_id,
        0,
    )

    expiry = (
        "Unlimited"
        if is_admin(user_id)
        else get_user_expiry(user_id)
    )

    text = (
        "📊 **AdsNova Pro - Live Analytics**\n\n"
        f"🆔 User ID: `{user_id}`\n"
        f"👤 Logged Accounts: `{len(sessions)}/{MAX_SLOTS}`\n"
        f"📂 Active Slot: `{active_slot}`\n"
        f"🔐 Account Status: {account_status}\n"
        f"🏷️ Account Name: {account_name}\n\n"
        f"💎 Subscription: {subscription_label(user_id)}\n"
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
                "🔄 Switch Account",
                callback_data="accounts",
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
# STATUS ROUTER
# ============================================================

async def status_command(update, context):
    """
    IMPORTANT:
    Admin -> Admin Live Status
    Normal User -> Personal User Status
    """

    user_id = update.effective_user.id

    if is_admin(user_id):
        await admin_stats(
            update,
            context,
        )
        return

    await user_status_command(
        update,
        context,
    )


# ============================================================
# STOP / LOGOUT
# ============================================================

async def stop_command(update, context):
    user = update.effective_user

    if not user:
        return

    user_id = user.id

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

    slot = get_active_slot(
        user_id
    )

    slot_info = get_slot_session(
        user_id,
        slot,
    )

    if not slot_info:
        await update.message.reply_text(
            "ℹ️ Abhi koi configured account slot nahi hai."
        )
        return

    set_slot_stopped(
        user_id,
        slot,
        1,
    )

    try:
        from forwarder import close_client

        await close_client(
            user_id,
            slot,
        )
    except Exception:
        pass

    await update.message.reply_text(
        f"🔴 Slot {slot} stopped successfully."
    )


async def logout_command(update, context):
    user_id = update.effective_user.id

    if not await check_membership(
        user_id,
        context,
    ):
        return

    if not has_access(user_id):
        return

    sessions = get_user_sessions(
        user_id
    )

    if not sessions:
        await update.message.reply_text(
            "❌ Koi logged-in account nahi hai."
        )
        return

    await update.message.reply_text(
        "👤 Account logout/remove ke liye "
        "**🔄 Switch Account** open karke "
        "**🗑️ Remove Account** use karo.",
        parse_mode="Markdown",
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
        text = (
            "💎 **Subscription Details**\n\n"
            "🌟 Status: Active ✅\n"
            f"🏷️ Type: {subscription_label(user_id)}\n"
            f"⏳ Expiry: `{get_user_expiry(user_id)}`\n"
            f"⏱️ Remaining: `{get_remaining_days(user_id)}`"
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

    if (
        not is_admin(user_id)
        and not is_premium(user_id)
    ):
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

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
        )


# ============================================================
# REFERRAL
# ============================================================

async def referral_page(update, context):
    user_id = update.effective_user.id

    username = (
        BOT_USERNAME or "your_bot"
    ).replace("@", "")

    link = (
        f"https://t.me/{username}"
        f"?start=ref_{user_id}"
    )

    share_text = (
        "🎁 AdsNova Pro ko 2 din free test karo!"
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

    await update.callback_query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
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
        ]),
    )


# ============================================================
# SETTINGS
# ============================================================

async def settings_page(update, context):
    await update.callback_query.edit_message_text(
        "⚙️ **AdsNova Pro Settings**\n\n"
        "👤 Maximum Accounts: **20**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔐 Login Account",
                    callback_data="login_account",
                ),
                InlineKeyboardButton(
                    "🔄 Switch Account",
                    callback_data="accounts",
                ),
            ],
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
        ]),
    )


async def source_channel_page(update, context):
    user_id = update.effective_user.id

    channels = get_user_channels(
        user_id
    )

    if not channels:
        await update.callback_query.edit_message_text(
            "❌ Database me koi channel available nahi hai.\n\n"
            "Pehle Telegram account login karke "
            "channels refresh karein.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔄 Switch Account",
                        callback_data="accounts",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="settings",
                    )
                ],
            ]),
        )
        return

    keyboard = [
        [
            InlineKeyboardButton(
                f"📌 {name}",
                callback_data=f"channel_{index}",
            )
        ]
        for index, (_, name)
        in enumerate(channels)
    ]

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Back",
            callback_data="settings",
        )
    ])

    await update.callback_query.edit_message_text(
        "📢 **Select Source Channel**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


async def groups_page(update, context):
    user_id = update.effective_user.id

    groups = get_user_groups(
        user_id
    )

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

    keyboard = [
        [
            InlineKeyboardButton(
                f"{'✅' if selected else '☑️'} {name}",
                callback_data=f"group_{group_id}",
            )
        ]
        for group_id, name, selected
        in groups[:40]
    ]

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
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


async def time_page(update, context):
    config = get_bot_config(
        update.effective_user.id
    )

    current = (
        config[1]
        if config and len(config) > 1
        else 30
    )

    await update.callback_query.edit_message_text(
        "⏱️ **Time Interval Settings**\n\n"
        f"Current: `{current}` seconds",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
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
        ]),
    )


async def help_page(update, context):
    text = (
        "💡 **AdsNova Pro Help Centre**\n\n"
        "1️⃣ Subscription active karein.\n"
        "2️⃣ Telegram account login karein.\n"
        "3️⃣ Maximum 20 accounts login rakh sakte hain.\n"
        "4️⃣ Switch Account se active account change karein.\n"
        "5️⃣ Source channel select karein.\n"
        "6️⃣ Target groups select karein.\n"
        "7️⃣ Posting interval choose karein.\n"
        "8️⃣ Status page se configuration check karein.\n\n"
        f"📞 Admin: @{str(ADMIN_CONTACT_USERNAME).replace('@', '')}"
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
# ADMIN
# ============================================================

async def admin_command(update, context):
    if not update.effective_user:
        return

    if not is_admin(
        update.effective_user.id
    ):
        return

    message = update.effective_message

    if message is None:
        return

    await message.reply_text(
        "👑 **AdsNova Pro Admin Panel**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
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
        ]),
    )


async def addsub_command(update, context):
    if not update.effective_user:
        return

    if not is_admin(
        update.effective_user.id
    ):
        return

    message = update.effective_message

    if message is None:
        return

    if not context.args:
        await message.reply_text(
            "Usage:\n`/addsub USER_ID DAYS`",
            parse_mode="Markdown",
        )
        return

    try:
        target = int(
            context.args[0]
        )

        days = (
            int(context.args[1])
            if len(context.args) > 1
            else 30
        )

        if target <= 0 or days <= 0:
            raise ValueError

        add_premium_subscription(
            target,
            days=days,
            plan_type="paid",
        )

        await message.reply_text(
            f"✅ User `{target}` ko "
            f"{days} days premium de diya gaya.",
            parse_mode="Markdown",
        )

    except Exception as e:
        await message.reply_text(
            f"❌ Error: {e}"
        )


async def delsub_command(update, context):
    if not update.effective_user:
        return

    if not is_admin(
        update.effective_user.id
    ):
        return

    message = update.effective_message

    if message is None:
        return

    if not context.args:
        await message.reply_text(
            "Usage:\n`/delsub USER_ID`",
            parse_mode="Markdown",
        )
        return

    try:
        target = int(
            context.args[0]
        )

        remove_premium_subscription(
            target
        )

        await message.reply_text(
            f"✅ User `{target}` ka subscription "
            "remove kar diya.",
            parse_mode="Markdown",
        )

    except Exception as e:
        await message.reply_text(
            f"❌ Error: {e}"
        )


# ============================================================
# ADMIN LIVE STATUS
# ============================================================

async def admin_stats(update, context):
    if not is_admin(
        update.effective_user.id
    ):
        return

    try:
        conn = sqlite3.connect(
            "bot_database.db"
        )

        now = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        total_users = conn.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        paid_users = conn.execute(
            """
            SELECT COUNT(*)
            FROM subscriptions
            WHERE expiry_date > ?
              AND plan_type NOT IN ('referral', 'trial')
            """,
            (now,),
        ).fetchone()[0]

        referral_users = conn.execute(
            """
            SELECT COUNT(*)
            FROM subscriptions
            WHERE expiry_date > ?
              AND plan_type IN ('referral', 'trial')
            """,
            (now,),
        ).fetchone()[0]

        active_premium = conn.execute(
            """
            SELECT COUNT(*)
            FROM subscriptions
            WHERE expiry_date > ?
            """,
            (now,),
        ).fetchone()[0]

        logged_accounts = conn.execute(
            """
            SELECT COUNT(*)
            FROM user_sessions
            """
        ).fetchone()[0]

        total_groups = conn.execute(
            """
            SELECT COUNT(*)
            FROM groups
            """
        ).fetchone()[0]

        selected_groups = conn.execute(
            """
            SELECT COUNT(*)
            FROM groups
            WHERE selected = 1
            """
        ).fetchone()[0]

        source_channels = conn.execute(
            """
            SELECT COUNT(*)
            FROM bot_config
            WHERE source_channel IS NOT NULL
              AND TRIM(source_channel) != ''
            """
        ).fetchone()[0]

        active_accounts = conn.execute(
            """
            SELECT COUNT(*)
            FROM user_sessions
            WHERE is_stopped = 0
            """
        ).fetchone()[0]

        active_forwarding_users = conn.execute(
            """
            SELECT COUNT(DISTINCT user_id)
            FROM user_sessions
            WHERE is_stopped = 0
            """
        ).fetchone()[0]

        conn.close()

    except Exception as e:
        logger.exception(
            "Admin live stats error: %s",
            e,
        )

        total_users = 0
        paid_users = 0
        referral_users = 0
        active_premium = 0
        logged_accounts = 0
        total_groups = 0
        selected_groups = 0
        source_channels = 0
        active_accounts = 0
        active_forwarding_users = 0

    runtime_sent = sum(
        forwarded_counts.values()
    )

    runtime_failed = sum(
        failed_counts.values()
    )

    text = (
        "👑 **AdsNova Pro — Live Admin Status**\n\n"
        "👥 **Users**\n"
        f"🚀 Bot Started Users: `{total_users}`\n"
        f"💎 Paid Premium Users: `{paid_users}`\n"
        f"🎁 Referral Premium Users: `{referral_users}`\n"
        f"⭐ Total Active Premium: `{active_premium}`\n\n"
        "🔐 **Telegram Accounts**\n"
        f"🆔 Logged-in Telegram IDs: `{logged_accounts}`\n"
        f"🟢 Active Accounts: `{active_accounts}`\n\n"
        "📢 **Forwarding**\n"
        f"📢 Source Channels Configured: `{source_channels}`\n"
        f"👥 Total Target Groups: `{total_groups}`\n"
        f"📨 Selected/Receiving Groups: `{selected_groups}`\n"
        f"🚀 Active Forwarding Users: `{active_forwarding_users}`\n\n"
        "📈 **Live Runtime Performance**\n"
        f"⚡ Successfully Sent: `{runtime_sent}`\n"
        f"⚠️ Failed: `{runtime_failed}`"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔄 Refresh Live Status",
                callback_data="admin_stats",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="admin_panel",
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


async def broadcast_command(update, context):
    if not is_admin(
        update.effective_user.id
    ):
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n`/broadcast Your message`",
            parse_mode="Markdown",
        )
        return

    message = " ".join(
        context.args
    )

    conn = sqlite3.connect(
        "bot_database.db"
    )

    users = conn.execute(
        "SELECT user_id FROM users"
    ).fetchall()

    conn.close()

    sent = 0
    failed = 0

    for (user_id,) in users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message,
            )

            sent += 1

            await asyncio.sleep(
                0.05
            )

        except Exception:
            failed += 1

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

    if not await check_membership(
        user_id,
        context,
    ):
        await show_join_required(
            update,
            context,
        )
        return

    if data == "login_account":
        if not has_access(user_id):
            await show_subscription_required(
                update,
                context,
            )
            return

        await login_page(
            update,
            context,
        )
        return

    if data == "accounts":
        if not has_access(user_id):
            await show_subscription_required(
                update,
                context,
            )
            return

        await accounts_page(
            update,
            context,
        )
        return

    if data == "cancel_login":
        await cancel_login(
            update,
            context,
        )
        return

    if data == "remove_account":
        if not has_access(user_id):
            await show_subscription_required(
                update,
                context,
            )
            return

        await remove_account_page(
            update,
            context,
        )
        return

    if data.startswith("empty_slot_"):
        await query.answer(
            "🟢 Ye empty slot hai. "
            "'Login New Account' dabakar account add karo.",
            show_alert=True,
        )
        return

    if data.startswith("switch_"):
        try:
            slot = int(
                data.split(
                    "_",
                    1,
                )[1]
            )

            if not 1 <= slot <= MAX_SLOTS:
                raise ValueError

            await switch_account(
                update,
                context,
                slot,
            )

        except Exception as e:
            await query.answer(
                f"❌ Error: {e}",
                show_alert=True,
            )

        return

    if data == "toggle_slot":
        if not has_access(user_id):
            await show_subscription_required(
                update,
                context,
            )
            return

        await toggle_slot(
            update,
            context,
        )
        return

    if data == "logout_info":
        await query.answer(
            "Account remove karne ke liye "
            "Switch Account → Remove Account use karo.",
            show_alert=True,
        )
        return

    if data.startswith("delete_"):
        try:
            slot = int(
                data.split(
                    "_",
                    1,
                )[1]
            )

            await delete_account(
                update,
                context,
                slot,
            )

        except Exception as e:
            await query.answer(
                f"❌ Error: {e}",
                show_alert=True,
            )

        return

    if data == "main_menu":
        await start(
            update,
            context,
        )
        return

    if data == "subscription":
        await subscription_page(
            update,
            context,
        )
        return

    if data == "referral_info":
        await referral_page(
            update,
            context,
        )
        return

    if data == "help_centre":
        await help_page(
            update,
            context,
        )
        return

    if data == "refresh":
        await start(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # ADMIN STATUS BUTTON
    # --------------------------------------------------------

    if data == "admin_stats":
        if not is_admin(user_id):
            return

        await admin_stats(
            update,
            context,
        )
        return

    if data == "admin_panel":
        if not is_admin(user_id):
            return

        await admin_command(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # ADMIN SUBSCRIPTION
    # --------------------------------------------------------

    if data == "admin_sub":
        if not is_admin(user_id):
            return

        admin_sub_target[user_id] = {
            "step": "target"
        }

        await query.edit_message_text(
            "💎 **Manage Subscription**\n\n"
            "Jis user ko subscription dena hai "
            "uski Telegram User ID bhejein.\n\n"
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

    if not has_access(user_id):
        await show_subscription_required(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # NORMAL USER STATUS
    # --------------------------------------------------------

    if data == "status":
        await user_status_command(
            update,
            context,
        )
        return

    if data == "settings":
        await settings_page(
            update,
            context,
        )
        return

    if data == "opt_1":
        await source_channel_page(
            update,
            context,
        )
        return

    if data.startswith("channel_"):
        try:
            index = int(
                data.split(
                    "_",
                    1,
                )[1]
            )

            channels = get_user_channels(
                user_id
            )

            if not 0 <= index < len(channels):
                await query.answer(
                    "❌ Channel not found.",
                    show_alert=True,
                )
                return

            channel_id, channel_name = channels[index]

            set_source_channel(
                user_id,
                str(channel_id),
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
                1,
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

    if data == "opt_3":
        await time_page(
            update,
            context,
        )
        return

    if data.startswith("time_"):
        try:
            seconds = int(
                data.split(
                    "_",
                    1,
                )[1]
            )

            if seconds <= 0:
                raise ValueError(
                    "Invalid interval"
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

    if data == "opt_4":
        current = get_custom_share_message(
            user_id
        )

        await query.edit_message_text(
            "💬 **Share Message**\n\n"
            f"Current message:\n`{current}`\n\n"
            "Custom message setting database me available hai.",
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


# ============================================================
# MESSAGE HANDLER
# ============================================================

async def handle_message(update, context):
    if (
        not update.message
        or not update.message.text
    ):
        return

    user = update.effective_user

    if not user:
        return

    user_id = user.id
    text = update.message.text.strip()

    if user_id in login_states:
        if await handle_login_message(
            update,
            context,
        ):
            return

    if (
        is_admin(user_id)
        and user_id in admin_sub_target
        and admin_sub_target[user_id].get(
            "step"
        ) == "target"
    ):
        try:
            target_id = int(text)

            if target_id <= 0:
                raise ValueError

            admin_sub_target[user_id] = {
                "step": "plan",
                "target_id": target_id,
            }

            await update.message.reply_text(
                f"✅ Target ID: `{target_id}`\n\n"
                "Plan select karein:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
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
                ]),
            )

        except ValueError:
            await update.message.reply_text(
                "❌ Valid numeric Telegram User ID bhejein."
            )

        return


# ============================================================
# ADMIN PLAN HANDLER
# ============================================================

async def admin_plan_handler(update, context):
    query = update.callback_query

    if query.from_user.id != ADMIN_ID:
        await query.answer(
            "❌ Not authorized.",
            show_alert=True,
        )
        return

    await query.answer()

    try:
        days = int(
            query.data.split(
                "_",
                1,
            )[1]
        )

        target_data = admin_sub_target.get(
            ADMIN_ID,
            {},
        )

        target_id = target_data.get(
            "target_id"
        )

        if not target_id or days <= 0:
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
# POST INIT
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
            "Stop forwarding",
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
# BUILD APPLICATION
# ============================================================

def build_application():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing from environment."
        )

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
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

    application.add_handler(
        CallbackQueryHandler(
            admin_plan_handler,
            pattern=r"^plan_\d+$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    return application


# ============================================================
# BACKGROUND WORKERS
# ============================================================

async def start_background_workers(application):
    tasks = []

    try:
        from forwarder import background_forwarder

        tasks.append(
            asyncio.create_task(
                background_forwarder(
                    application
                )
            )
        )

        logger.info(
            "Forwarder worker started."
        )

    except ImportError as e:
        logger.error(
            "Could not load forwarder.py: %s",
            e,
        )

    try:
        from worker import expiry_reminder_worker

        tasks.append(
            asyncio.create_task(
                expiry_reminder_worker(
                    application
                )
            )
        )

        logger.info(
            "Expiry reminder worker started."
        )

    except ImportError as e:
        logger.error(
            "Could not load worker.py: %s",
            e,
        )

    return tasks


# ============================================================
# RUN BOT
# ============================================================

async def run_bot():
    init_db()

    application = build_application()

    worker_tasks = []

    logger.info(
        "========================================"
    )

    logger.info(
        "AdsNova Pro Bot Starting..."
    )

    logger.info(
        "Async runner enabled."
    )

    logger.info(
        "========================================"
    )

    try:
        await application.initialize()

        await post_init(
            application
        )

        await application.start()

        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )

        worker_tasks = await start_background_workers(
            application
        )

        logger.info(
            "AdsNova Pro Bot is ONLINE ✅"
        )

        logger.info(
            "Telegram polling started successfully."
        )

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

        for task in worker_tasks:
            if not task.done():
                task.cancel()

        if worker_tasks:
            await asyncio.gather(
                *worker_tasks,
                return_exceptions=True,
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
# MAIN
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
