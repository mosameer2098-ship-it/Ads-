import sqlite3
from datetime import datetime, timedelta

DB_NAME = "bot_database.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            expiry_date TEXT,
            plan_type TEXT DEFAULT 'paid'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_config (
            user_id INTEGER PRIMARY KEY,
            source_channel TEXT,
            time_interval INTEGER DEFAULT 30
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            user_id INTEGER,
            slot_number INTEGER,
            phone TEXT,
            session_string TEXT,
            account_name TEXT,
            is_stopped INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, slot_number)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            user_id INTEGER,
            group_id INTEGER,
            group_name TEXT,
            selected INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, group_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            user_id INTEGER,
            channel_id INTEGER,
            channel_name TEXT,
            PRIMARY KEY (user_id, channel_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            custom_share_message TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_slots (
            user_id INTEGER PRIMARY KEY,
            slot_number INTEGER DEFAULT 1
        )
    """)

    # Persistent message tracking prevents duplicates after restart.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS forwarded_messages (
            user_id INTEGER,
            slot_number INTEGER,
            message_id INTEGER,
            completed_at TEXT,
            PRIMARY KEY (user_id, slot_number, message_id)
        )
    """)

    conn.commit()
    conn.close()


def save_user(user):
    conn = get_connection()
    conn.execute("""
        INSERT INTO users
        (user_id, username, first_name, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name
    """, (
        user.id,
        user.username,
        user.first_name,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()


def get_all_users():
    conn = get_connection()
    rows = conn.execute("""
        SELECT user_id FROM users ORDER BY user_id
    """).fetchall()
    conn.close()
    return [row["user_id"] for row in rows]


def get_user(user_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT user_id, username, first_name, created_at
        FROM users WHERE user_id = ?
    """, (user_id,)).fetchone()
    conn.close()
    return row


def is_premium(user_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT expiry_date FROM subscriptions WHERE user_id = ?
    """, (user_id,)).fetchone()
    conn.close()

    if not row:
        return False

    try:
        expiry = datetime.strptime(row["expiry_date"], "%Y-%m-%d %H:%M:%S")
        return expiry > datetime.now()
    except Exception:
        return False


def get_user_expiry(user_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT expiry_date FROM subscriptions WHERE user_id = ?
    """, (user_id,)).fetchone()
    conn.close()
    return row["expiry_date"] if row else "N/A"


def get_remaining_days(user_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT expiry_date FROM subscriptions WHERE user_id = ?
    """, (user_id,)).fetchone()
    conn.close()

    if not row:
        return "Expired"

    try:
        expiry = datetime.strptime(row["expiry_date"], "%Y-%m-%d %H:%M:%S")
        remaining = expiry - datetime.now()

        if remaining.total_seconds() <= 0:
            return "Expired"

        return f"{remaining.days} Days {(remaining.seconds // 3600)} Hours"
    except Exception:
        return "N/A"


def add_premium_subscription(user_id, days=30, plan_type="paid"):
    conn = get_connection()
    row = conn.execute("""
        SELECT expiry_date FROM subscriptions WHERE user_id = ?
    """, (user_id,)).fetchone()

    now = datetime.now()

    if row:
        try:
            old_expiry = datetime.strptime(
                row["expiry_date"], "%Y-%m-%d %H:%M:%S"
            )
            start_date = old_expiry if old_expiry > now else now
        except Exception:
            start_date = now
    else:
        start_date = now

    expiry = start_date + timedelta(days=days)

    conn.execute("""
        INSERT OR REPLACE INTO subscriptions
        (user_id, expiry_date, plan_type)
        VALUES (?, ?, ?)
    """, (
        user_id,
        expiry.strftime("%Y-%m-%d %H:%M:%S"),
        plan_type
    ))
    conn.commit()
    conn.close()


def remove_premium_subscription(user_id):
    conn = get_connection()
    conn.execute("""
        DELETE FROM subscriptions WHERE user_id = ?
    """, (user_id,))
    conn.commit()
    conn.close()


def get_bot_config(user_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT source_channel, time_interval
        FROM bot_config WHERE user_id = ?
    """, (user_id,)).fetchone()
    conn.close()

    if row:
        return row["source_channel"], row["time_interval"] or 30

    return None, 30


def set_source_channel(user_id, channel_name):
    conn = get_connection()
    conn.execute("""
        INSERT INTO bot_config
        (user_id, source_channel, time_interval)
        VALUES (?, ?, 30)
        ON CONFLICT(user_id) DO UPDATE SET
            source_channel = excluded.source_channel
    """, (user_id, channel_name))
    conn.commit()
    conn.close()


def set_time_interval(user_id, interval):
    interval = max(1, int(interval))
    conn = get_connection()
    conn.execute("""
        INSERT INTO bot_config
        (user_id, source_channel, time_interval)
        VALUES (?, NULL, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            time_interval = excluded.time_interval
    """, (user_id, interval))
    conn.commit()
    conn.close()


def get_user_groups(user_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT group_id, group_name, selected
        FROM groups WHERE user_id = ? ORDER BY group_name
    """, (user_id,)).fetchall()
    conn.close()

    return [
        (row["group_id"], row["group_name"], row["selected"])
        for row in rows
    ]


def toggle_group_selection(user_id, group_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT selected FROM groups
        WHERE user_id = ? AND group_id = ?
    """, (user_id, group_id)).fetchone()

    if row:
        conn.execute("""
            UPDATE groups SET selected = ?
            WHERE user_id = ? AND group_id = ?
        """, (0 if row["selected"] else 1, user_id, group_id))

    conn.commit()
    conn.close()


def set_all_groups_selection(user_id, value):
    conn = get_connection()
    conn.execute("""
        UPDATE groups SET selected = ? WHERE user_id = ?
    """, (1 if value else 0, user_id))
    conn.commit()
    conn.close()


def get_user_channels(user_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT channel_id, channel_name
        FROM channels WHERE user_id = ? ORDER BY channel_name
    """, (user_id,)).fetchall()
    conn.close()

    return [
        (row["channel_id"], row["channel_name"])
        for row in rows
    ]


def get_active_slot(user_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT slot_number FROM active_slots WHERE user_id = ?
    """, (user_id,)).fetchone()

    if not row:
        conn.execute("""
            INSERT INTO active_slots (user_id, slot_number)
            VALUES (?, 1)
        """, (user_id,))
        slot = 1
    else:
        slot = row["slot_number"]

    conn.commit()
    conn.close()
    return slot


def set_active_slot(user_id, slot_number):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO active_slots (user_id, slot_number)
        VALUES (?, ?)
    """, (user_id, int(slot_number)))
    conn.commit()
    conn.close()


def get_slot_session(user_id, slot_number):
    conn = get_connection()
    row = conn.execute("""
        SELECT phone, session_string, account_name, is_stopped
        FROM user_sessions
        WHERE user_id = ? AND slot_number = ?
    """, (user_id, slot_number)).fetchone()
    conn.close()

    if not row:
        return None

    return (
        row["phone"],
        row["session_string"],
        row["account_name"],
        row["is_stopped"]
    )


def get_user_sessions(user_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT slot_number, phone, session_string,
               account_name, is_stopped
        FROM user_sessions
        WHERE user_id = ? ORDER BY slot_number
    """, (user_id,)).fetchall()
    conn.close()

    return [
        (
            row["slot_number"],
            row["phone"],
            row["session_string"],
            row["account_name"],
            row["is_stopped"]
        )
        for row in rows
    ]


def save_user_session(
    user_id, slot_number, phone, session_string, account_name
):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO user_sessions
        (user_id, slot_number, phone, session_string,
         account_name, is_stopped)
        VALUES (?, ?, ?, ?, ?, 0)
    """, (
        user_id, slot_number, phone, session_string, account_name
    ))
    conn.commit()
    conn.close()


def remove_user_session(user_id, slot_number):
    conn = get_connection()
    conn.execute("""
        DELETE FROM user_sessions
        WHERE user_id = ? AND slot_number = ?
    """, (user_id, slot_number))

    conn.execute("""
        DELETE FROM active_slots
        WHERE user_id = ? AND slot_number = ?
    """, (user_id, slot_number))

    conn.commit()
    conn.close()


def set_slot_stopped(user_id, slot_number, stopped):
    conn = get_connection()
    conn.execute("""
        UPDATE user_sessions SET is_stopped = ?
        WHERE user_id = ? AND slot_number = ?
    """, (1 if stopped else 0, user_id, slot_number))
    conn.commit()
    conn.close()


def save_real_groups_and_channels(user_id, groups_list, channels_list):
    conn = get_connection()

    old_selected = {}
    rows = conn.execute("""
        SELECT group_id, selected FROM groups WHERE user_id = ?
    """, (user_id,)).fetchall()

    for row in rows:
        old_selected[row["group_id"]] = row["selected"]

    conn.execute("DELETE FROM groups WHERE user_id = ?", (user_id,))

    for group_id, group_name in groups_list:
        conn.execute("""
            INSERT OR REPLACE INTO groups
            (user_id, group_id, group_name, selected)
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            int(group_id),
            group_name,
            old_selected.get(group_id, 0)
        ))

    conn.execute("DELETE FROM channels WHERE user_id = ?", (user_id,))

    for channel_id, channel_name in channels_list:
        conn.execute("""
            INSERT OR REPLACE INTO channels
            (user_id, channel_id, channel_name)
            VALUES (?, ?, ?)
        """, (user_id, int(channel_id), channel_name))

    conn.commit()
    conn.close()


def get_custom_share_message(user_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT custom_share_message
        FROM user_settings WHERE user_id = ?
    """, (user_id,)).fetchone()
    conn.close()

    if row and row["custom_share_message"]:
        return row["custom_share_message"]

    return "🚀 AdsNova Pro"


def set_custom_share_message(user_id, message):
    conn = get_connection()
    conn.execute("""
        INSERT INTO user_settings
        (user_id, custom_share_message)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            custom_share_message = excluded.custom_share_message
    """, (user_id, message))
    conn.commit()
    conn.close()


def check_referral_eligibility(user_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT user_id FROM subscriptions WHERE user_id = ?
    """, (user_id,)).fetchone()
    conn.close()
    return row is None


def claim_referral_reward(user_id):
    if not check_referral_eligibility(user_id):
        return False

    add_premium_subscription(user_id, days=2, plan_type="referral")
    return True


def was_message_forwarded(user_id, slot_number, message_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT 1 FROM forwarded_messages
        WHERE user_id = ? AND slot_number = ? AND message_id = ?
    """, (user_id, slot_number, message_id)).fetchone()
    conn.close()
    return row is not None


def mark_message_forwarded(user_id, slot_number, message_id):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO forwarded_messages
        (user_id, slot_number, message_id, completed_at)
        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        slot_number,
        message_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()
