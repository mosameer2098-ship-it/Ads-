import asyncio
import logging

from telethon import TelegramClient
from telethon.sessions import StringSession

from config import API_ID, API_HASH

from database import (
    get_active_slot,
    get_slot_session,
    get_bot_config,
    get_user_groups,
    get_all_users,
    get_forward_position,
    set_forward_position,
    reset_forward_position,
)

logger = logging.getLogger(__name__)

active_clients = {}


# ============================================================
# TELETHON CLIENT
# ============================================================

async def get_client(user_id, slot_number, session_string):

    key = (user_id, slot_number)

    client = active_clients.get(key)

    if client:
        try:
            if client.is_connected():
                return client
        except Exception:
            pass

    if not API_ID or not API_HASH or not session_string:
        logger.error("Telethon API_ID/API_HASH/session missing.")
        return None

    try:

        client = TelegramClient(
            StringSession(session_string),
            int(API_ID),
            API_HASH,
        )

        await client.connect()

        if not await client.is_user_authorized():

            logger.warning(
                "Unauthorized session: user=%s slot=%s",
                user_id,
                slot_number,
            )

            await client.disconnect()
            return None

        active_clients[key] = client

        logger.info(
            "Telethon client connected: user=%s slot=%s",
            user_id,
            slot_number,
        )

        return client

    except Exception as e:

        logger.exception(
            "Client connection error: user=%s slot=%s error=%s",
            user_id,
            slot_number,
            e,
        )

        return None


async def close_client(user_id, slot_number):

    key = (user_id, slot_number)

    client = active_clients.pop(key, None)

    if client:

        try:
            await client.disconnect()
        except Exception:
            pass


async def close_all_clients():

    for user_id, slot_number in list(active_clients.keys()):

        await close_client(
            user_id,
            slot_number,
        )


# ============================================================
# FIND SOURCE CHANNEL
# ============================================================

async def find_source_entity(client, source_channel):
    if not source_channel:
        return None

    source_channel = str(source_channel).strip()

    # --------------------------------------------------------
    # NUMERIC TELEGRAM ID
    # --------------------------------------------------------
    if source_channel.lstrip("-").isdigit():
        channel_id = int(source_channel)

        # First try the exact entity from the SAME user session.
        try:
            entity = await client.get_entity(channel_id)
            if entity:
                return entity
        except Exception:
            pass

        # ----------------------------------------------------
        # PRIVATE CHANNEL FALLBACK
        # Search the logged-in user's dialogs.
        # This works for private channels the user can access.
        # ----------------------------------------------------
        try:
            dialogs = await client.get_dialogs(limit=None)

            for dialog in dialogs:
                entity = dialog.entity

                try:
                    if int(dialog.id) == channel_id:
                        return entity
                except Exception:
                    pass

                try:
                    if int(getattr(entity, "id", 0)) == channel_id:
                        return entity
                except Exception:
                    pass

        except Exception as e:
            logger.warning(
                "Dialog source search failed: %s",
                e,
            )

        return None

    # --------------------------------------------------------
    # USERNAME
    # --------------------------------------------------------
    username = source_channel
    if not username.startswith("@"):
        username = "@" + username

    try:
        return await client.get_entity(username)
    except Exception:
        pass

    # --------------------------------------------------------
    # SEARCH DIALOGS BY TITLE
    # --------------------------------------------------------
    try:
        dialogs = await client.get_dialogs(limit=None)

        needle = (
            source_channel
            .replace("@", "")
            .lower()
        )

        for dialog in dialogs:
            title = getattr(
                dialog,
                "title",
                None,
            )

            if title and needle == title.lower():
                return dialog.entity

    except Exception as e:
        logger.warning(
            "Dialog title search failed: %s",
            e,
        )

    return None

# ============================================================
# SELECTED GROUPS
# ============================================================

def get_selected_groups(user_id):

    return [
        (group[0], group[1])
        for group in get_user_groups(user_id)
        if len(group) >= 3
        and group[2] == 1
    ]


# ============================================================
# SEND ONLY TEXT AS NEW MESSAGE
# ============================================================

async def send_text_message(
    client,
    group_id,
    message,
):

    # --------------------------------------------------------
    # MEDIA / NON-TEXT COMPLETELY IGNORE
    # --------------------------------------------------------

    if not message:
        return False

    if not message.text:
        return False

    text = str(
        message.text
    ).strip()

    if not text:
        return False

    try:

        # IMPORTANT:
        # send_message() creates a NEW message.
        # Native forward_messages() is NOT used.

        await client.send_message(
            entity=int(group_id),
            message=text,
            link_preview=True,
        )

        return True

    except Exception as e:

        logger.error(
            "Text send failed: group=%s error=%s",
            group_id,
            e,
        )

        return False


# ============================================================
# GET TEXT MESSAGES
# ============================================================

async def get_text_messages(
    client,
    source_entity,
):

    try:

        messages = await client.get_messages(
            source_entity,
            limit=100,
        )

        if not messages:
            return []

        # Oldest -> newest
        messages = list(
            reversed(messages)
        )

        # ONLY TEXT
        text_messages = []

        for message in messages:

            if not message:
                continue

            if not message.text:
                continue

            text = str(
                message.text
            ).strip()

            if not text:
                continue

            text_messages.append(
                message
            )

        return text_messages

    except Exception as e:

        logger.exception(
            "Unable to get source messages: %s",
            e,
        )

        return []


# ============================================================
# FORWARD FOR ONE USER
# ============================================================

async def forward_for_user(
    user_id,
    application=None,
):

    try:

        # ----------------------------------------------------
        # ACTIVE SLOT
        # ----------------------------------------------------

        slot_number = get_active_slot(
            user_id
        )

        # ----------------------------------------------------
        # SESSION
        # ----------------------------------------------------

        slot_tuple = get_slot_session(
            user_id,
            slot_number,
        )

        if not slot_tuple:
            return

        (
            phone,
            session_string,
            account_name,
            stopped,
        ) = slot_tuple

        # ----------------------------------------------------
        # STOPPED
        # ----------------------------------------------------

        if stopped:

            await close_client(
                user_id,
                slot_number,
            )

            return

        # ----------------------------------------------------
        # CONFIG
        # ----------------------------------------------------

        config = get_bot_config(
            user_id
        )

        source_channel = (
            config[0]
            if config
            else None
        )

        interval = (
            config[1]
            if config and len(config) > 1
            else 30
        )

        interval = max(
            3,
            int(interval or 30),
        )

        if not source_channel:
            return

        # ----------------------------------------------------
        # GROUPS
        # ----------------------------------------------------

        selected_groups = get_selected_groups(
            user_id
        )

        if not selected_groups:
            return

        # ----------------------------------------------------
        # CLIENT
        # ----------------------------------------------------

        client = await get_client(
            user_id,
            slot_number,
            session_string,
        )

        if not client:
            return

        # ----------------------------------------------------
        # SOURCE
        # ----------------------------------------------------

        source_entity = await find_source_entity(
            client,
            source_channel,
        )

        if not source_entity:

            logger.error(
                "Source not found: user=%s source=%s",
                user_id,
                source_channel,
            )

            return

        # ----------------------------------------------------
        # SOURCE KEY
        # ----------------------------------------------------

        try:

            source_key = str(
                getattr(
                    source_entity,
                    "id",
                    source_channel,
                )
            )

        except Exception:

            source_key = str(
                source_channel
            )

        # ----------------------------------------------------
        # GET ONLY TEXT MESSAGES
        # ----------------------------------------------------

        messages = await get_text_messages(
            client,
            source_entity,
        )

        if not messages:

            logger.info(
                "No text messages found: user=%s source=%s",
                user_id,
                source_channel,
            )

            return

        # ----------------------------------------------------
        # CURRENT POSITION
        # ----------------------------------------------------

        position = get_forward_position(
            user_id,
            slot_number,
            source_key,
        )

        # Safety
        if position < 0:
            position = 0

        # ----------------------------------------------------
        # CYCLE COMPLETE
        # ----------------------------------------------------

        if position >= len(messages):

            logger.info(
                "Text cycle completed. Restarting from 1. "
                "user=%s source=%s",
                user_id,
                source_channel,
            )

            position = 0

            reset_forward_position(
                user_id,
                slot_number,
                source_key,
            )

        # ----------------------------------------------------
        # MESSAGE TO SEND
        # ----------------------------------------------------

        message = messages[position]

        successful_groups = 0

        # ----------------------------------------------------
        # SEND TO ALL SELECTED GROUPS
        # ----------------------------------------------------

        for group_id, group_name in selected_groups:

            try:

                sent = await send_text_message(
                    client,
                    group_id,
                    message,
                )

                if not sent:
                    continue

                successful_groups += 1

                # ------------------------------------------------
                # SUCCESS COUNTER
                # ------------------------------------------------

                try:

                    from bot import forwarded_counts

                    forwarded_counts[user_id] = (
                        forwarded_counts.get(
                            user_id,
                            0,
                        ) + 1
                    )

                except Exception:
                    pass

                logger.info(
                    "TEXT SEND SUCCESS: "
                    "user=%s position=%s message=%s group=%s",
                    user_id,
                    position + 1,
                    message.id,
                    group_id,
                )

                await asyncio.sleep(1)

            except Exception as e:

                # ------------------------------------------------
                # FAILED COUNTER
                # ------------------------------------------------

                try:

                    from bot import failed_counts

                    failed_counts[user_id] = (
                        failed_counts.get(
                            user_id,
                            0,
                        ) + 1
                    )

                except Exception:
                    pass

                logger.error(
                    "TEXT SEND FAILED: "
                    "user=%s position=%s message=%s "
                    "group=%s name=%s error=%s",
                    user_id,
                    position + 1,
                    message.id,
                    group_id,
                    group_name,
                    e,
                )

        # ----------------------------------------------------
        # MOVE TO NEXT MESSAGE ONLY AFTER SUCCESS
        # ----------------------------------------------------

        if successful_groups > 0:

            next_position = position + 1

            # ------------------------------------------------
            # IF LAST MESSAGE -> NEXT CYCLE STARTS FROM 1
            # ------------------------------------------------

            if next_position >= len(messages):

                logger.info(
                    "Last text message sent. "
                    "Next cycle will start from first message. "
                    "user=%s source=%s",
                    user_id,
                    source_channel,
                )

                next_position = 0

            set_forward_position(
                user_id,
                slot_number,
                source_key,
                next_position,
            )

        # ----------------------------------------------------
        # WAIT BEFORE NEXT MESSAGE
        # ----------------------------------------------------

        await asyncio.sleep(
            interval
        )

    except Exception as e:

        logger.exception(
            "Forwarder error for user=%s: %s",
            user_id,
            e,
        )


# ============================================================
# BACKGROUND FORWARDER
# ============================================================

async def background_forwarder(
    application,
):

    logger.info(
        "AdsNova Pro Text Forwarder started."
    )

    try:

        while True:

            users = get_all_users()

            for user_id in users:

                try:

                    await forward_for_user(
                        user_id,
                        application,
                    )

                except Exception as e:

                    logger.exception(
                        "User forward error: %s",
                        e,
                    )

                await asyncio.sleep(
                    0.2
                )

            await asyncio.sleep(
                5
            )

    except asyncio.CancelledError:

        logger.info(
            "Forwarder worker stopped."
        )

        await close_all_clients()

        raise

    except Exception:

        logger.exception(
            "Forwarder worker crashed."
        )

        await close_all_clients()

        raise
