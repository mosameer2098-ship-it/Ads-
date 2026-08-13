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
# ACTIVE TELETHON CLIENTS
# ============================================================

active_clients = {}


# ============================================================
# GET / CREATE CLIENT
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

    if not API_ID or not API_HASH:
        logger.error(
            "Telethon API_ID/API_HASH missing."
        )
        return None

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
# FIND SOURCE CHANNEL
# ============================================================

async def find_source_entity(client, source_channel):

    source_channel = str(source_channel).strip()

    if not source_channel:
        return None

    # --------------------------------------------------------
    # Telegram numeric ID
    # --------------------------------------------------------

    try:

        if (
            source_channel.startswith("-100")
            or source_channel.startswith("-")
            or source_channel.isdigit()
        ):

            entity = await client.get_entity(
                int(source_channel)
            )

            return entity

    except Exception as e:

        logger.warning(
            "Numeric source lookup failed: %s",
            e,
        )

    # --------------------------------------------------------
    # Username lookup
    # --------------------------------------------------------

    try:

        username = source_channel

        if not username.startswith("@"):
            username = "@" + username

        entity = await client.get_entity(username)

        return entity

    except Exception as e:

        logger.warning(
            "Username source lookup failed: %s",
            e,
        )

    # --------------------------------------------------------
    # Search dialogs
    # --------------------------------------------------------

    try:

        dialogs = await client.get_dialogs(limit=None)

        search_name = source_channel.lower().replace(
            "@",
            "",
        )

        for dialog in dialogs:

            title = getattr(
                dialog,
                "title",
                None,
            )

            if not title:
                continue

            if search_name in title.lower():

                logger.info(
                    "Source found from dialogs: %s",
                    title,
                )

                return dialog.entity

    except Exception as e:

        logger.warning(
            "Dialog source search failed: %s",
            e,
        )

    return None


# ============================================================
# GET SELECTED GROUPS
# ============================================================

def get_selected_groups(user_id):

    groups = get_user_groups(user_id)

    selected = []

    for group in groups:

        if len(group) < 3:
            continue

        group_id = group[0]
        group_name = group[1]
        is_selected = group[2]

        if is_selected == 1:

            selected.append(
                (
                    group_id,
                    group_name,
                )
            )

    return selected


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

        slot_number = get_active_slot(user_id)

        slot_tuple = get_slot_session(
            user_id,
            slot_number,
        )

        if not slot_tuple:

            logger.info(
                "No session found: user=%s slot=%s",
                user_id,
                slot_number,
            )

            return

        phone = slot_tuple[0]
        session_string = slot_tuple[1]
        account_name = slot_tuple[2]
        stopped = slot_tuple[3]

        if stopped:

            await close_client(
                user_id,
                slot_number,
            )

            return

        if not session_string:

            logger.warning(
                "Empty session: user=%s slot=%s",
                user_id,
                slot_number,
            )

            return

        # ----------------------------------------------------
        # TELETHON CLIENT
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

        if not config:

            return

        source_channel = config[0]

        interval = (
            config[1]
            if len(config) > 1 and config[1]
            else 30
        )

        if not source_channel:

            logger.warning(
                "Source channel not configured: user=%s",
                user_id,
            )

            return

        # ----------------------------------------------------
        # SELECTED GROUPS
        # ----------------------------------------------------

        selected_groups = get_selected_groups(
            user_id
        )

        if not selected_groups:

            logger.warning(
                "No selected groups: user=%s",
                user_id,
            )

            return

        # ----------------------------------------------------
        # SOURCE ENTITY
        # ----------------------------------------------------

        source_entity = await find_source_entity(
            client,
            source_channel,
        )

        if not source_entity:

            logger.error(
                "Source channel not found: user=%s source=%s",
                user_id,
                source_channel,
            )

            return

        logger.info(
            "Source connected: user=%s source=%s",
            user_id,
            source_channel,
        )

        # ----------------------------------------------------
        # FETCH LATEST MESSAGE
        # ----------------------------------------------------

        messages = await client.get_messages(
            source_entity,
            limit=10,
        )

        if not messages:

            logger.info(
                "No messages found: user=%s",
                user_id,
            )

            return

        # ----------------------------------------------------
        # PROCESS OLDEST -> NEWEST
        # ----------------------------------------------------

        for message in reversed(messages):

            if not message:
                continue

            if not message.text and not message.media:
                continue

            message_key = (
                f"last_msg_"
                f"{user_id}_"
                f"{slot_number}_"
                f"{message.id}"
            )

            # ------------------------------------------------
            # CHECK WHETHER THIS MESSAGE WAS COMPLETED
            # ------------------------------------------------

            already_done = getattr(
                forward_for_user,
                message_key,
                False,
            )

            if already_done:
                continue

            successful_groups = 0

            # ------------------------------------------------
            # FORWARD TO ALL SELECTED GROUPS
            # ------------------------------------------------

            for group_id, group_name in selected_groups:

                try:

                    logger.info(
                        "Forwarding message=%s "
                        "user=%s -> group=%s (%s)",
                        message.id,
                        user_id,
                        group_id,
                        group_name,
                    )

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
                                0,
                            ) + 1
                        )

                    except Exception:
                        pass

                    logger.info(
                        "Forward SUCCESS message=%s "
                        "user=%s group=%s",
                        message.id,
                        user_id,
                        group_id,
                    )

                    await asyncio.sleep(1)

                except Exception as e:

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
                        "Forward FAILED "
                        "message=%s "
                        "user=%s "
                        "group=%s "
                        "name=%s "
                        "error=%s",
                        message.id,
                        user_id,
                        group_id,
                        group_name,
                        e,
                    )

            # ------------------------------------------------
            # ONLY MARK DONE IF AT LEAST ONE GROUP GOT IT
            # ------------------------------------------------

            if successful_groups > 0:

                setattr(
                    forward_for_user,
                    message_key,
                    True,
                )

                logger.info(
                    "Message completed: "
                    "message=%s user=%s successful_groups=%s",
                    message.id,
                    user_id,
                    successful_groups,
                )

            else:

                logger.warning(
                    "Message NOT marked completed because "
                    "all groups failed: message=%s user=%s",
                    message.id,
                    user_id,
                )

            # ------------------------------------------------
            # PROCESS ONLY ONE NEW MESSAGE PER CYCLE
            # ------------------------------------------------

            await asyncio.sleep(
                max(
                    3,
                    int(interval),
                )
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

                    if isinstance(
                        user,
                        (tuple, list),
                    ):

                        user_id = user[0]

                    else:

                        user_id = int(user)

                    await forward_for_user(
                        user_id,
                        application,
                    )

                except Exception as e:

                    logger.exception(
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
