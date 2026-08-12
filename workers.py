import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


async def expiry_reminder_worker(application):

    await asyncio.sleep(10)

    while True:

        try:

            conn = sqlite3.connect("bot_database.db")
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
                            "⚠️ **Alert:** Aapka AdsNova Pro "
                            "subscription **kal khatam hone wala hai!**\n\n"
                            "Plan ko uninterrupted chalane ke liye "
                            "jaldi renew karein:\n"
                            "🛒 Contact Admin: @AdsNova0"
                        ),
                        parse_mode="Markdown"
                    )

                    await asyncio.sleep(1)

                except Exception as e:

                    logger.warning(
                        f"Expiry reminder failed "
                        f"for user {user_id}: {e}"
                    )

            await asyncio.sleep(43200)

        except Exception as e:

            logger.error(
                f"Expiry reminder worker error: {e}"
            )

            await asyncio.sleep(3600)
