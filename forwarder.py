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


# ============================================================
# FORWARDING STATS
# ============================================================

forwarded_counts = {}
failed_counts = {}


# ============================================================
# BACKGROUND FORWARDER
# ============================================================

async def background_forwarder(application):

    await asyncio.sleep(5)

    while True:

        try:

            conn = sqlite3.connect("bot_database.db")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT user_id, slot_number, session_string
                FROM user_sessions
                WHERE is_stopped = 0
                """
            )

            active_sessions = cursor.fetchall()

            conn.close()

            for session_row in active_sessions:

                user_id = session_row["user_id"]
                slot_num = session_row["slot_number"]
                session_str = session_row["session_string"]

                # ------------------------------------------------
                # PREMIUM CHECK
                # ------------------------------------------------

                if user_id != ADMIN_ID and not is_premium(user_id):
                    continue

                # ------------------------------------------------
                # USER CONFIG
                # ------------------------------------------------

                config = get_bot_config(user_id)

                if not config:
                    continue

                source_chan_name = config[0]

                interval = (
                    config[1]
                    if len(config) > 1 and config[1]
                    else 30
                )

                if not source_chan_name:
                    continue

                # ------------------------------------------------
                # SELECTED GROUPS
                # ------------------------------------------------

                groups = get_user_groups(user_id)

                selected_groups = [
                    g[0]
                    for g in groups
                    if g[2] == 1
                ]

                if not selected_groups:
                    continue

                client = None

                try:

                    # ------------------------------------------------
                    # TELETHON CLIENT
                    # ------------------------------------------------

                    client = TelegramClient(
                        StringSession(session_str),
                        API_ID,
                        API_HASH
                    )

                    await client.connect()

                    if not await client.is_user_authorized():

                        await client.disconnect()

                        continue

                    # ------------------------------------------------
                    # FIND SOURCE CHANNEL
                    # ------------------------------------------------

                    source_entity = None

                    channels = get_user_channels(user_id)

                    target_channel_id = None

                    for cid, cname in channels:

                        if (
                            cname.strip().lower()
                            == source_chan_name.strip().lower()
                        ):

                            target_channel_id = cid

                            break

                    # ------------------------------------------------
                    # FIND BY SAVED CHANNEL ID
                    # ------------------------------------------------

                    if target_channel_id:

                        try:

                            source_entity = await client.get_entity(
                                int(target_channel_id)
                            )

                        except Exception:

                            source_entity = None

                    # ------------------------------------------------
                    # AUTO DETECT SOURCE CHANNEL
                    # ------------------------------------------------

                    if not source_entity:

                        async for dialog in client.iter_dialogs(
                            limit=100
                        ):

                            dialog_title = (
                                dialog.title.strip().lower()
                                if dialog.title
                                else ""
                            )

                            if (
                                dialog_title
                                == source_chan_name.strip().lower()
                                or
                                str(dialog.id)
                                == str(source_chan_name)
                            ):

                                source_entity = dialog.entity

                                break

                    # ------------------------------------------------
                    # SOURCE NOT FOUND
                    # ------------------------------------------------

                    if not source_entity:

                        await client.disconnect()

                        await asyncio.sleep(
                            interval + random.randint(1, 5)
                        )

                        continue

                    # ------------------------------------------------
                    # GET LATEST MESSAGE
                    # ------------------------------------------------

                    messages = await client.get_messages(
                        source_entity,
                        limit=1
                    )

                    if not messages:

                        await client.disconnect()

                        await asyncio.sleep(
                            interval + random.randint(1, 5)
                        )

                        continue

                    latest_msg = messages[0]

                    # ------------------------------------------------
                    # SEND TO SELECTED GROUPS
                    # ------------------------------------------------

                    for grp_id in selected_groups:

                        try:

                            if latest_msg.media:

                                await client.send_file(
                                    int(grp_id),
                                    latest_msg.media,
                                    caption=latest_msg.text or ""
                                )

                            elif latest_msg.text:

                                await client.send_message(
                                    int(grp_id),
                                    latest_msg.text
                                )

                            # ------------------------------------------------
                            # SUCCESS COUNT
                            # ------------------------------------------------

                            forwarded_counts[user_id] = (
                                forwarded_counts.get(user_id, 0) + 1
                            )

                            logger.info(
                                f"Forwarded message "
                                f"from user {user_id} "
                                f"to group {grp_id}"
                            )

                            # ------------------------------------------------
                            # RANDOM DELAY
                            # ------------------------------------------------

                            await asyncio.sleep(
                                random.randint(3, 7)
                            )

                        except Exception as f_err:

                            failed_counts[user_id] = (
                                failed_counts.get(user_id, 0) + 1
                            )

                            logger.error(
                                f"Send error to group "
                                f"{grp_id}: {f_err}"
                            )

                    # ------------------------------------------------
                    # DISCONNECT
                    # ------------------------------------------------

                    await client.disconnect()

                except Exception as e:

                    logger.error(
                        f"Forwarder client error "
                        f"for user {user_id}, "
                        f"slot {slot_num}: {e}"
                    )

                    try:

                        if client:
                            await client.disconnect()

                    except Exception:
                        pass

                # ------------------------------------------------
                # NEXT CYCLE
                # ------------------------------------------------

                await asyncio.sleep(
                    interval + random.randint(1, 5)
                )

        except Exception as err:

            logger.error(
                f"Background worker loop error: {err}"
            )

            await asyncio.sleep(10)
