import asyncio
import logging
import random
import sqlite3

from telethon import TelegramClient
from telethon.sessions import StringSession

from config import API_ID, API_HASH, ADMIN_ID

from database import (
    is_premium,
    get_bot_config,
    get_user_groups,
    get_user_channels,
)

logger = logging.getLogger(__name__)

# Runtime forwarding statistics
forwarded_counts = {}
failed_counts = {}


def get_active_sessions():
    conn = sqlite3.connect("bot_database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT user_id, slot_number, session_string
            FROM user_sessions
            WHERE is_stopped = 0
              AND session_string IS NOT NULL
              AND session_string != ''
        """)

        return cursor.fetchall()

    finally:
        conn.close()


def find_source_channel_id(user_id, source_name):
    channels = get_user_channels(user_id)

    source_name = str(source_name).strip().lower()

    for channel_id, channel_name in channels:
        if str(channel_name).strip().lower() == source_name:
            return channel_id

        if str(channel_id) == str(source_name):
            return channel_id

    return None


async def find_source_entity(client, user_id, source_name):
    channel_id = find_source_channel_id(
        user_id,
        source_name,
    )

    if channel_id is not None:
        try:
            return await client.get_entity(
                int(channel_id)
            )
        except Exception as e:
            logger.warning(
                "Saved channel lookup failed for user %s: %s",
                user_id,
                e,
            )

    source_name_lower = str(
        source_name
    ).strip().lower()

    try:
        async for dialog in client.iter_dialogs(
            limit=200
        ):
            title = (
                dialog.title.strip().lower()
                if dialog.title
                else ""
            )

            if title == source_name_lower:
                return dialog.entity

            if str(dialog.id) == str(source_name):
                return dialog.entity

    except Exception as e:
        logger.warning(
            "Dialog search failed for user %s: %s",
            user_id,
            e,
        )

    return None


async def forward_latest_message(
    client,
    latest_msg,
    selected_groups,
    user_id,
):
    for group_id in selected_groups:

        try:

            if latest_msg.media:
                await client.send_file(
                    int(group_id),
                    latest_msg.media,
                    caption=latest_msg.text or "",
                )

            elif latest_msg.text:
                await client.send_message(
                    int(group_id),
                    latest_msg.text,
                )

            else:
                continue

            forwarded_counts[user_id] = (
                forwarded_counts.get(user_id, 0) + 1
            )

            logger.info(
                "Forwarded message: user=%s group=%s",
                user_id,
                group_id,
            )

            await asyncio.sleep(
                random.randint(3, 7)
            )

        except Exception as e:

            failed_counts[user_id] = (
                failed_counts.get(user_id, 0) + 1
            )

            logger.error(
                "Forward failed: user=%s group=%s error=%s",
                user_id,
                group_id,
                e,
            )


async def process_session(
    application,
    session_row,
):
    user_id = session_row["user_id"]
    slot_num = session_row["slot_number"]
    session_string = session_row["session_string"]

    if (
        user_id != ADMIN_ID
        and not is_premium(user_id)
    ):
        return 30

    config = get_bot_config(user_id)

    if not config:
        return 30

    source_name = config[0]

    interval = (
        config[1]
        if len(config) > 1 and config[1]
        else 30
    )

    try:
        interval = max(
            5,
            int(interval)
        )
    except Exception:
        interval = 30

    if not source_name:
        return interval

    groups = get_user_groups(user_id)

    selected_groups = [
        group[0]
        for group in groups
        if group[2] == 1
    ]

    if not selected_groups:
        return interval

    client = None

    try:

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
                slot_num,
            )

            return interval

        source_entity = await find_source_entity(
            client,
            user_id,
            source_name,
        )

        if not source_entity:

            logger.warning(
                "Source channel not found: user=%s source=%s",
                user_id,
                source_name,
            )

            return interval

        messages = await client.get_messages(
            source_entity,
            limit=1,
        )

        if not messages:
            return interval

        latest_msg = messages[0]

        if not latest_msg:
            return interval

        await forward_latest_message(
            client,
            latest_msg,
            selected_groups,
            user_id,
        )

        return interval

    except Exception as e:

        logger.error(
            "Forwarder error: user=%s slot=%s error=%s",
            user_id,
            slot_num,
            e,
        )

        return interval

    finally:

        if client:

            try:
                await client.disconnect()
            except Exception:
                pass


async def background_forwarder(application):
    """
    Background Telegram forwarding worker.

    Har active session ko uske configured source
    aur selected target groups ke according process karta hai.
    """

    await asyncio.sleep(5)

    logger.info(
        "Background forwarder started."
    )

    while True:

        try:

            active_sessions = get_active_sessions()

            if not active_sessions:
                await asyncio.sleep(10)
                continue

            for session_row in active_sessions:

                try:

                    interval = await process_session(
                        application,
                        session_row,
                    )

                    await asyncio.sleep(
                        interval
                        + random.randint(1, 5)
                    )

                except Exception as e:

                    logger.error(
                        "Session processing error: %s",
                        e,
                    )

                    await asyncio.sleep(5)

        except asyncio.CancelledError:

            logger.info(
                "Background forwarder stopped."
            )
            raise

        except Exception as e:

            logger.exception(
                "Background forwarder loop error: %s",
                e,
            )

            await asyncio.sleep(10)
