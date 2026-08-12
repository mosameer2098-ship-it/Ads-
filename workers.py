import asyncio
import logging
from datetime import datetime, timedelta

from database import (
    get_all_users,
    get_user_expiry,
    is_premium,
)


logger = logging.getLogger(__name__)


# ============================================================
# EXPIRY REMINDER WORKER
# ============================================================

async def expiry_reminder_worker(application):

    logger.info("Expiry reminder worker started.")

    already_sent = set()

    while True:

        try:

            users = get_all_users()

            for user in users:

                try:

                    user_id = (
                        user[0]
                        if isinstance(user, (tuple, list))
                        else int(user)
                    )

                    # ------------------------------------------------
                    # PREMIUM CHECK
                    # ------------------------------------------------

                    if not is_premium(user_id):
                        continue

                    expiry = get_user_expiry(user_id)

                    if not expiry:
                        continue

                    # ------------------------------------------------
                    # EXPIRY DATE PARSE
                    # ------------------------------------------------

                    try:

                        expiry_date = datetime.strptime(
                            str(expiry),
                            "%Y-%m-%d %H:%M:%S",
                        )

                    except ValueError:

                        try:

                            expiry_date = datetime.fromisoformat(
                                str(expiry)
                            )

                        except Exception:

                            logger.warning(
                                "Invalid expiry date for user %s: %s",
                                user_id,
                                expiry,
                            )

                            continue

                    now = datetime.now()

                    remaining = expiry_date - now

                    # ------------------------------------------------
                    # REMINDER KEY
                    # ------------------------------------------------

                    days_left = remaining.total_seconds() / 86400

                    reminder_type = None

                    if 0 < days_left <= 1:

                        reminder_type = "1day"

                    elif 1 < days_left <= 3:

                        reminder_type = "3days"

                    elif 3 < days_left <= 7:

                        reminder_type = "7days"

                    # ------------------------------------------------
                    # SEND REMINDER
                    # ------------------------------------------------

                    if reminder_type:

                        reminder_key = (
                            f"{user_id}_{reminder_type}_"
                            f"{expiry_date.strftime('%Y-%m-%d')}"
                        )

                        if reminder_key in already_sent:
                            continue

                        if reminder_type == "1day":

                            text = (
                                "⚠️ **Subscription Expiring Soon!**\n\n"
                                "Aapka AdsNova Pro subscription "
                                "lagbhag **1 din** me expire hone wala hai.\n\n"
                                "Renewal ke liye Admin se contact karein."
                            )

                        elif reminder_type == "3days":

                            text = (
                                "⏳ **Subscription Reminder**\n\n"
                                "Aapka AdsNova Pro subscription "
                                "lagbhag **3 din** me expire hone wala hai.\n\n"
                                "Service continue rakhne ke liye "
                                "renewal karwa lein."
                            )

                        else:

                            text = (
                                "💎 **Subscription Reminder**\n\n"
                                "Aapka AdsNova Pro subscription "
                                "lagbhag **7 din** me expire hoga.\n\n"
                                "Renewal ke liye Admin se contact karein."
                            )

                        try:

                            await application.bot.send_message(
                                chat_id=user_id,
                                text=text,
                                parse_mode="Markdown",
                            )

                            already_sent.add(
                                reminder_key
                            )

                            logger.info(
                                "Expiry reminder sent to user %s: %s",
                                user_id,
                                reminder_type,
                            )

                        except Exception as e:

                            logger.warning(
                                "Could not send reminder to %s: %s",
                                user_id,
                                e,
                            )

                except Exception as e:

                    logger.warning(
                        "Expiry processing error: %s",
                        e,
                    )

            # --------------------------------------------------------
            # CLEAN OLD REMINDER KEYS
            # --------------------------------------------------------

            if len(already_sent) > 10000:

                already_sent.clear()

            # --------------------------------------------------------
            # CHECK EVERY 30 MINUTES
            # --------------------------------------------------------

            await asyncio.sleep(1800)

        except asyncio.CancelledError:

            logger.info(
                "Expiry reminder worker stopped."
            )

            break

        except Exception as e:

            logger.exception(
                "Expiry reminder worker error: %s",
                e,
            )

            await asyncio.sleep(60)
