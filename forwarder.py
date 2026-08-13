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
                slot_number
            )
            await client.disconnect()
            return None

        active_clients[key] = client

        logger.info(
            "Telethon client connected: user=%s slot=%s",
            user_id,
            slot_number
        )

        return client

    except Exception as e:
        logger.exception(
            "Client connection error: user=%s slot=%s: %s",
            user_id,
            slot_number,
            e
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
        await close_client(user_id, slot_number)


# ============================================================
# FIND SOURCE CHANNEL
# ============================================================

async def find_source_entity(client, source_channel):
    if not source_channel:
        return None

    source_channel = str(source_channel).strip()

    # Numeric Telegram ID
    try:
        if source_channel.lstrip("-").isdigit():
            return await client.get_entity(
                int(source_channel)
            )
    except Exception:
        pass

    # Username
    try:
        username = source_channel

        if not username.startswith("@"):
            username = "@" + username

        return await client.get_entity(username)

    except Exception:
        pass

    # Dialog title search
    try:
        dialogs = await client.get_dialogs(limit=None)

        needle = source_channel.replace(
            "@",
            ""
        ).lower()

        for dialog in dialogs:
            title = getattr(
                dialog,
                "title",
                None
            )

            if title and needle in title.lower():
                return dialog.entity

    except Exception as e:
        logger.warning(
            "Dialog source search failed: %s",
            e
        )

    return None


# ============================================================
# SELECTED GROUPS
# ============================================================

def get_selected_groups(user_id):
    return [
        (group[0], group[1])
        for group in get_user_groups(user_id)
        if len(group) >= 3 and group[2] == 1
    ]


# ============================================================
# GET SOURCE MESSAGES
# ============================================================

async def get_cycle_messages(
    client,
    source_entity
):
    """
    Gets the available channel messages in
    oldest -> newest order.

    limit=None allows the client to retrieve
    the available message history instead of
    only checking the latest 20 messages.
    """

    try:
        messages = await client.get_messages(
            source_entity,
            limit=None,
        )

        if not messages:
            return []

        valid_messages = []

        for message in messages:
            if not message:
                continue

            # Skip service/empty messages
            if not message.text and not message.media:
                continue

            valid_messages.append(message)

        # Telethon normally returns newest -> oldest.
        # Reverse to get oldest -> newest.
        valid_messages.reverse()

        return valid_messages

    except Exception as e:
        logger.exception(
            "Could not get source messages: %s",
            e
        )
        return []


# ============================================================
# FORWARD ONE USER
# ============================================================

async def forward_for_user(
    user_id,
    application=None
):
    try:
        slot_number = get_active_slot(user_id)

        slot_tuple = get_slot_session(
            user_id,
            slot_number
        )

        if not slot_tuple:
            return

        phone, session_string, account_name, stopped = slot_tuple

        if stopped:
            await close_client(
                user_id,
                slot_number
            )
            return

        config = get_bot_config(user_id)

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
            int(interval or 30)
        )

        if not source_channel:
            return

        selected_groups = get_selected_groups(
            user_id
        )

        if not selected_groups:
            return

        client = await get_client(
            user_id,
            slot_number,
            session_string
        )

        if not client:
            return

        source_entity = await find_source_entity(
            client,
            source_channel
        )

        if not source_entity:
            logger.error(
                "Source not found: user=%s source=%s",
                user_id,
                source_channel
            )
            return

        messages = await get_cycle_messages(
            client,
            source_entity
        )

        if not messages:
            logger.info(
                "No messages found: user=%s",
                user_id
            )
            return

        # A stable source key keeps the position
        # separate for different source channels.
        try:
            source_key = str(
                getattr(
                    source_entity,
                    "id",
                    source_channel
                )
            )
        except Exception:
            source_key = str(source_channel)

        current_index = get_forward_position(
            user_id,
            slot_number,
            source_key
        )

        # If the saved index is beyond the current
        # number of messages, start a new cycle.
        if current_index >= len(messages):
            current_index = 0

        message = messages[current_index]

        successful_groups = 0

        # ====================================================
        # SEND CURRENT MESSAGE TO SELECTED GROUPS
        # ====================================================

        for group_id, group_name in selected_groups:

            try:
                await client.forward_messages(
                    entity=int(group_id),
                    messages=message,
                    from_peer=source_entity,
                )

                successful_groups += 1

                try:
                    from bot import forwarded_counts

                    forwarded_counts[user_id] = (
                        forwarded_counts.get(
                            user_id,
                            0
                        ) + 1
                    )

                except Exception:
                    pass

                logger.info(
                    "Forward SUCCESS: user=%s "
                    "message=%s index=%s group=%s",
                    user_id,
                    message.id,
                    current_index,
                    group_id
                )

                await asyncio.sleep(1)

            except Exception as e:

                try:
                    from bot import failed_counts

                    failed_counts[user_id] = (
                        failed_counts.get(
                            user_id,
                            0
                        ) + 1
                    )

                except Exception:
                    pass

                logger.error(
                    "Forward FAILED: user=%s "
                    "message=%s group=%s "
                    "name=%s error=%s",
                    user_id,
                    message.id,
                    group_id,
                    group_name,
                    e
                )

        # ====================================================
        # MOVE TO NEXT MESSAGE
        # ====================================================

        if successful_groups > 0:

            next_index = current_index + 1

            # IMPORTANT:
            # After the last message, go back to 0.
            if next_index >= len(messages):
                next_index = 0

                logger.info(
                    "Cycle completed: user=%s "
                    "source=%s. Restarting from message 1.",
                    user_id,
                    source_channel
                )

            set_forward_position(
                user_id,
                slot_number,
                source_key,
                next_index
            )

        # Wait before sending the next message.
        await asyncio.sleep(interval)

    except Exception as e:
        logger.exception(
            "Forwarder error for user=%s: %s",
            user_id,
            e
        )


# ============================================================
# BACKGROUND FORWARDER
# ============================================================

async def background_forwarder(application):
    logger.info(
        "AdsNova Pro Forwarder started."
    )

    try:

        while True:

            users = get_all_users()

            for user_id in users:

                try:
                    await forward_for_user(
                        user_id,
                        application
                    )

                except Exception as e:
                    logger.exception(
                        "User forward error: %s",
                        e
                    )

                await asyncio.sleep(0.2)

            await asyncio.sleep(5)

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
