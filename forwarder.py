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
    was_message_forwarded,
    mark_message_forwarded,
)

logger = logging.getLogger(__name__)

active_clients = {}


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
                user_id, slot_number
            )
            await client.disconnect()
            return None

        active_clients[key] = client
        logger.info(
            "Telethon client connected: user=%s slot=%s",
            user_id, slot_number
        )
        return client

    except Exception as e:
        logger.exception(
            "Client connection error: user=%s slot=%s: %s",
            user_id, slot_number, e
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


async def find_source_entity(client, source_channel):
    if not source_channel:
        return None

    source_channel = str(source_channel).strip()

    # First try a stored Telegram numeric ID.
    try:
        if source_channel.lstrip("-").isdigit():
            return await client.get_entity(int(source_channel))
    except Exception:
        pass

    # Then username / invite-style public reference.
    try:
        username = source_channel
        if not username.startswith("@"):
            username = "@" + username
        return await client.get_entity(username)
    except Exception:
        pass

    # Finally search dialogs by title.
    try:
        dialogs = await client.get_dialogs(limit=None)
        needle = source_channel.replace("@", "").lower()

        for dialog in dialogs:
            title = getattr(dialog, "title", None)
            if title and needle in title.lower():
                return dialog.entity
    except Exception as e:
        logger.warning("Dialog source search failed: %s", e)

    return None


def get_selected_groups(user_id):
    return [
        (group[0], group[1])
        for group in get_user_groups(user_id)
        if len(group) >= 3 and group[2] == 1
    ]


async def forward_for_user(user_id, application=None):
    try:
        slot_number = get_active_slot(user_id)
        slot_tuple = get_slot_session(user_id, slot_number)

        if not slot_tuple:
            return

        phone, session_string, account_name, stopped = slot_tuple

        if stopped:
            await close_client(user_id, slot_number)
            return

        config = get_bot_config(user_id)
        source_channel = config[0] if config else None
        interval = config[1] if config and len(config) > 1 else 30
        interval = max(3, int(interval or 30))

        if not source_channel:
            return

        selected_groups = get_selected_groups(user_id)

        if not selected_groups:
            return

        client = await get_client(
            user_id,
            slot_number,
            session_string,
        )

        if not client:
            return

        source_entity = await find_source_entity(
            client,
            source_channel,
        )

        if not source_entity:
            logger.error(
                "Source not found: user=%s source=%s",
                user_id, source_channel
            )
            return

        messages = await client.get_messages(
            source_entity,
            limit=20,
        )

        if not messages:
            return

        # Oldest -> newest. Only the first unprocessed message is sent.
        for message in reversed(messages):
            if not message:
                continue

            if not message.text and not message.media:
                continue

            if was_message_forwarded(
                user_id, slot_number, message.id
            ):
                continue

            successful_groups = 0

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
                            forwarded_counts.get(user_id, 0) + 1
                        )
                    except Exception:
                        pass

                    logger.info(
                        "Forward SUCCESS: user=%s message=%s group=%s",
                        user_id, message.id, group_id
                    )

                    await asyncio.sleep(1)

                except Exception as e:
                    try:
                        from bot import failed_counts
                        failed_counts[user_id] = (
                            failed_counts.get(user_id, 0) + 1
                        )
                    except Exception:
                        pass

                    logger.error(
                        "Forward FAILED: user=%s message=%s group=%s "
                        "name=%s error=%s",
                        user_id, message.id, group_id, group_name, e
                    )

            if successful_groups > 0:
                mark_message_forwarded(
                    user_id, slot_number, message.id
                )

            await asyncio.sleep(interval)
            break

    except Exception as e:
        logger.exception(
            "Forwarder error for user=%s: %s",
            user_id, e
        )


async def background_forwarder(application):
    logger.info("AdsNova Pro Forwarder started.")

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
                        "User forward error: %s", e
                    )

                await asyncio.sleep(0.2)

            await asyncio.sleep(5)

    except asyncio.CancelledError:
        logger.info("Forwarder worker stopped.")
        await close_all_clients()
        raise

    except Exception:
        logger.exception("Forwarder worker crashed.")
        await close_all_clients()
        raise
