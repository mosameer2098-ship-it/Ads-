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
)


logger = logging.getLogger(__name__)


# ============================================================
# ACTIVE CLIENTS
# ============================================================

active_clients = {}


# ============================================================
# GET CLIENT
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

    client = TelegramClient(
        StringSession(session_string),
        API_ID,
        API_HASH,
    )

    await client.connect()

    if not await client.is_user_authorized():
        logger.warning(
            "Session unauthorized: user=%s slot=%s",
            user_id,
            slot_number,
        )

        await client.disconnect()
        return None

    active_clients[key] = client

    return client


# ============================================================
# CLOSE CLIENT
# ============================================================

async def close_client(user_id, slot_number):

    key = (user_id, slot_number)

    client = active_clients.pop(key, None)

    if client:

        try:
            await client.disconnect()
        except Exception:
            pass


# ============================================================
# FORWARD USER MESSAGES
# ============================================================

async def forward_for_user(
    user_id,
    application,
):

    try:

        slot_number = get_active_slot(user_id)

        slot = get_slot_session(
            user_id,
            slot_number,
        )

        if not slot:
            return

        # ----------------------------------------------------
        # DATABASE STRUCTURE
        # ----------------------------------------------------

        phone = slot[0]
        session_string = slot[1]
        account_name = slot[2]
        stopped = slot[3]

        # ----------------------------------------------------
        # STOPPED
        # ----------------------------------------------------

        if stopped:

            await close_client(
                user_id,
                slot_number,
            )

            return

        if not session_string:
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
        # BOT CONFIG
        # ----------------------------------------------------

        config = get_bot_config(user_id)

        if not config or not config[0]:
            return

        source_channel = config[0].strip()

        interval = (
            config[1]
            if len(config) > 1 and config[1]
            else 30
        )

        # ----------------------------------------------------
        # TARGET GROUPS
        # ----------------------------------------------------

        groups = get_user_groups(user_id)

        selected_groups = [
            group
            for group in groups
            if len(group) >= 3 and group[2] == 1
        ]

        if not selected_groups:
            return

        # ----------------------------------------------------
        # SOURCE ENTITY
        # ----------------------------------------------------

        try:
            if source_channel.startswith("-100") or source_channel.isdigit() or source_channel.startswith("-"):
                source_entity = await client.get_entity(int(source_channel))
            else:
                source_entity = await client.get_entity(source_channel)

        except Exception as e:
            logger.error(
                "Source channel error user=%s channel=%s: %s",
                user_id,
                source_channel,
                e,
            )
            return

        # ----------------------------------------------------
        # FETCH MULTIPLE MESSAGES FROM HISTORY (OLD + NEW)
        # ----------------------------------------------------

        messages = await client.get_messages(
            source_entity,
            limit=10,
        )

        if not messages:
            return

        for message in reversed(messages):
            if not message.text and not message.media:
                continue

            last_message_key = f"last_msg_{user_id}_{slot_number}_{message.id}"
            is_sent = getattr(forward_for_user, last_message_key, False)

            if is_sent:
                continue

            setattr(forward_for_user, last_message_key, True)

            # Target groups me forward karein
            for group in selected_groups:

                try:

                    group_id = group[0]

                    await client.forward_messages(
                        entity=group_id,
                        messages=message,
                        from_peer=source_entity,
                    )

                    logger.info(
                        "Forwarded message %s -> %s (user=%s slot=%s)",
                        message.id,
                        group_id,
                        user_id,
                        slot_number,
                    )

                    await asyncio.sleep(1)

                except Exception as e:

                    logger.warning(
                        "Forward failed user=%s group=%s: %s",
                        user_id,
                        group[0],
                        e,
                    )

            # Ek message bhejne ke baad interval lein
            await asyncio.sleep(
                max(3, int(interval))
            )
            break

    except Exception as e:

        logger.exception(
            "Forwarder error for user=%s: %s",
            user_id,
            e,
        )


# ============================================================
# BACKGROUND FORWARDER
# ============================================================

async def background_forwarder(application):

    logger.info(
        "AdsNova Pro Forwarder started."
    )

    while True:

        try:

            from database import get_all_users

            users = get_all_users()

            if not users:
                await asyncio.sleep(10)
                continue

            for user in users:

                try:

                    if isinstance(user, (tuple, list)):
                        user_id = user[0]
                    else:
                        user_id = int(user)

                    await forward_for_user(
                        user_id,
                        application,
                    )

                except Exception as e:
                    logger.warning(
                        "User forward error: %s",
                        e,
                    )

                await asyncio.sleep(0.2)

            await asyncio.sleep(5)

        except asyncio.CancelledError:
            logger.info(
                "Forwarder worker stopped."
            )
            break

        except Exception as e:
            logger.exception(
                "Forwarder worker error: %s",
                e,
            )
            await asyncio.sleep(10)
