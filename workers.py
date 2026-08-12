import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


async def expiry_reminder_worker(application):

    await asyncio.sleep(10)

    logger.info("Expiry reminder worker started.")

    while True:

        try:

            conn = sqlite3.connect(
                "bot_database.db"
            )
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            tomorrow = (
                datetime.now() + timedelta(days=1)
            ).strftime("%Y-%m-%d")

            cursor.execute(
                """
                SELECT user_id, expiry_date
                FROM subscriptions
                WHERE expiry_date LIKE ?
                """,
                (f"{tomorrow}%",)
            )

            expiring_users = cursor.fetchall()

            conn.close()

            for row in expiring_users:

                user_id = row["user_id"]

                try:

                    await application.bot.send_message(
                        chat_id=user_id,
                        text=(
                            "⚠️ **AdsNova Pro Subscription Alert**\n\n"
                            "Aapka subscription **kal expire hone wala hai**.\n\n"
                            "Service ko uninterrupted rakhne ke liye "
                            "apna premium plan renew karein.\n\n"
                            "🛒 Contact Admin: @AdsNova0"
                        ),
                        parse_mode="Markdown",
                    )

                    logger.info(
                        "Expiry reminder sent to user %s",
                        user_id,
                    )

                    await asyncio.sleep(1)

                except Exception as e:

                    logger.warning(
                        "Expiry reminder failed for user %s: %s",
                        user_id,
                        e,
                    )

            # 12 hours ke baad dobara check
            await asyncio.sleep(43200)

        except asyncio.CancelledError:

            logger.info(
                "Expiry reminder worker stopped."
            )
            raise

        except Exception as e:

            logger.exception(
                "Expiry reminder worker error: %s",
                e,
            )

            await asyncio.sleep(3600)
