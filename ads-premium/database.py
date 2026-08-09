import sqlite3
from datetime import datetime

DB_NAME = "bot.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            premium INTEGER DEFAULT 0,
            premium_expiry TEXT,
            verified INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS account_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            slot_number INTEGER NOT NULL,
            status TEXT DEFAULT 'Not Connected',
            created_at TEXT
        )
    """)

    # Multiple Telegram Accounts (Userbots) ke session save karne ke liye table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            phone_number TEXT NOT NULL,
            session_string TEXT NOT NULL,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_user(user):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO users
        (user_id, username, first_name, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        user.id,
        user.username or "",
        user.first_name or "",
        datetime.utcnow().isoformat(),
    ))

    cursor.execute("""
        UPDATE users
        SET username = ?, first_name = ?
        WHERE user_id = ?
    """, (
        user.username or "",
        user.first_name or "",
        user.id,
    ))

    conn.commit()
    conn.close()


def get_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,)
    )

    result = cursor.fetchone()
    conn.close()

    return result


def is_premium(user_id):
    user = get_user(user_id)

    if not user:
        return False

    if user[3] != 1:
        return False

    expiry = user[4]

    if expiry:
        try:
            expiry_date = datetime.fromisoformat(expiry)

            if datetime.utcnow() > expiry_date:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE users
                    SET premium = 0
                    WHERE user_id = ?
                """, (user_id,))

                conn.commit()
                conn.close()

                return False

        except ValueError:
            return False

    return True


# =========================================================
# MULTI-ACCOUNT SESSION FUNCTIONS
# =========================================================

def save_user_session(user_id, phone_number, session_string):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_sessions (user_id, phone_number, session_string, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        phone_number,
        session_string,
        datetime.utcnow().isoformat(),
    ))
    conn.commit()
    conn.close()


def get_user_sessions(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, phone_number, created_at FROM user_sessions WHERE user_id = ?",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows
    
