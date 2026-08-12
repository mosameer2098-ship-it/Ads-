import logging

from telegram import Update
from telegram.ext import ContextTypes

from telethon import TelegramClient
from telethon.sessions import StringSession

from config import API_ID, API_HASH

from database import (
    save_user_session,
    set_active_slot,
    save_real_groups_and_channels,
)


logger = logging.getLogger(__name__)


async def update_account_dialogs(client, user_id):
    """Login ke baad groups aur channels database mein save kare."""

    try:
        dialogs = await client.get_dialogs(limit=None)

        groups = []
        channels = []

        for dialog in dialogs:

            if not (dialog.is_channel or dialog.is_group):
                continue

            entity = dialog.entity

            if getattr(entity, "broadcast", False):

                channels.append(
                    (dialog.id, dialog.title)
                )

            elif (
                getattr(entity, "megagroup", False)
                or dialog.is_group
            ):

                groups.append(
                    (dialog.id, dialog.title)
                )

            else:

                channels.append(
                    (dialog.id, dialog.title)
                )

        save_real_groups_and_channels(
            user_id,
            groups,
            channels
        )

        logger.info(
            f"Saved {len(groups)} groups and "
            f"{len(channels)} channels for user {user_id}"
        )

    except Exception as e:

        logger.error(
            f"Dialog refresh error for user {user_id}: {e}"
        )


async def process_login_phone(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_login_state: dict,
    user_id: int,
):
    """Phone number receive karke OTP send karta hai."""

    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    state = user_login_state.get(user_id)

    if not state:
        return

    slot_num = state.get("slot_number")

    client = TelegramClient(
        StringSession(),
        API_ID,
        API_HASH
    )

    state["client"] = client
    state["phone"] = text

    try:

        await client.connect()

        sent = await client.send_code_request(
            text
        )

        state["phone_code_hash"] = (
            sent.phone_code_hash
        )

        state["step"] = "waiting_otp"

        await update.message.reply_text(
            "📩 OTP code aapke Telegram account "
            "par bhej diya gaya hai:\n\n"
            "⚠️ OTP yahin bhejein."
        )

    except Exception as e:

        try:
            await client.disconnect()
        except Exception:
            pass

        user_login_state.pop(
            user_id,
            None
        )

        await update.message.reply_text(
            f"❌ Error sending OTP:\n{e}"
        )


async def finish_login(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_login_state: dict,
    user_id: int,
    client,
    slot_num: int,
    phone: str,
):
    """Successful login ke baad session save karta hai."""

    try:

        me = await client.get_me()

        session_str = client.session.save()

        acc_name = (
            f"{me.first_name or ''} "
            f"{me.last_name or ''}"
        ).strip()

        if not acc_name:
            acc_name = (
                me.username
                or phone
            )

        save_user_session(
            user_id,
            slot_num,
            phone,
            session_str,
            acc_name
        )

        set_active_slot(
            user_id,
            slot_num
        )

        await update_account_dialogs(
            client,
            user_id
        )

        await client.disconnect()

        user_login_state.pop(
            user_id,
            None
        )

        await update.message.reply_text(
            f"✅ **Slot {slot_num} Connected Successfully!**\n\n"
            f"👤 Account: {acc_name}\n\n"
            "📂 Groups & Channels automatically "
            "refresh ho gaye hain.",
            parse_mode="Markdown"
        )

        return True

    except Exception as e:

        logger.error(
            f"Login save error for user {user_id}: {e}"
        )

        try:
            await client.disconnect()
        except Exception:
            pass

        user_login_state.pop(
            user_id,
            None
        )

        await update.message.reply_text(
            f"❌ Login save error:\n{e}"
        )

        return False


async def process_login_otp(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_login_state: dict,
    user_id: int,
):
    """OTP verify karta hai."""

    if not update.message or not update.message.text:
        return

    state = user_login_state.get(user_id)

    if not state:
        return

    otp = update.message.text.strip().replace(
        " ",
        ""
    )

    client = state.get("client")

    phone = state.get("phone")
    phone_code_hash = state.get(
        "phone_code_hash"
    )
    slot_num = state.get("slot_number")

    if not client:
        user_login_state.pop(
            user_id,
            None
        )

        await update.message.reply_text(
            "❌ Login session expire ho gaya. "
            "Dobara login karein."
        )

        return

    try:

        await client.sign_in(
            phone=phone,
            code=otp,
            phone_code_hash=phone_code_hash
        )

        await finish_login(
            update,
            context,
            user_login_state,
            user_id,
            client,
            slot_num,
            phone
        )

    except Exception as e:

        err_str = str(e)

        if (
            "SessionPasswordNeeded" in err_str
            or "password" in err_str.lower()
            or "Two-steps verification"
            in err_str
        ):

            state["step"] = "waiting_password"

            await update.message.reply_text(
                "🔒 **2-Step Verification detected!**\n\n"
                "Aapke Telegram account par "
                "2FA password laga hua hai.\n\n"
                "🔐 Apna Telegram 2FA password bhejein:",
                parse_mode="Markdown"
            )

            return

        await client.disconnect()

        user_login_state.pop(
            user_id,
            None
        )

        await update.message.reply_text(
            f"❌ Login Failed:\n{e}"
        )


async def process_login_password(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_login_state: dict,
    user_id: int,
):
    """2FA password verify karta hai."""

    if not update.message or not update.message.text:
        return

    state = user_login_state.get(user_id)

    if not state:
        return

    password = update.message.text

    client = state.get("client")

    phone = state.get("phone")
    slot_num = state.get("slot_number")

    if not client:

        user_login_state.pop(
            user_id,
            None
        )

        await update.message.reply_text(
            "❌ Login session expire ho gaya. "
            "Dobara login karein."
        )

        return

    try:

        await client.sign_in(
            password=password
        )

        await finish_login(
            update,
            context,
            user_login_state,
            user_id,
            client,
            slot_num,
            phone
        )

    except Exception as e:

        logger.error(
            f"2FA login error for user {user_id}: {e}"
        )

        try:
            await client.disconnect()
        except Exception:
            pass

        user_login_state.pop(
            user_id,
            None
        )

        await update.message.reply_text(
            f"❌ Password Error:\n{e}"
        )


async def handle_login_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_login_state: dict,
):
    """
    Login ke current step ke according
    Phone / OTP / Password handle karta hai.
    """

    if not update.message:
        return

    user = update.effective_user

    if not user:
        return

    user_id = user.id

    state = user_login_state.get(user_id)

    if not state:
        return

    step = state.get("step")

    if step == "waiting_phone":

        await process_login_phone(
            update,
            context,
            user_login_state,
            user_id
        )

    elif step == "waiting_otp":

        await process_login_otp(
            update,
            context,
            user_login_state,
            user_id
        )

    elif step == "waiting_password":

        await process_login_password(
            update,
            context,
            user_login_state,
            user_id
        )
