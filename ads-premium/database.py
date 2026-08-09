import sqlite3
from datetime import datetime, timedelta

DB_NAME = "bot_database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_date TEXT
        )
    """)
    # Subscriptions table with 30-day validity tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            expiry_date TEXT
        )
    """)
    # Sessions/Slots table for multi-account login (up to 20 slots per user)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            slot_number INTEGER,
            phone TEXT,
            session_string TEXT,
            account_name TEXT,
            account_id TEXT,
            status TEXT DEFAULT 'Active'
        )
    """)
    conn.commit()
    conn.close()

def save_user(user):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user.id,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (user_id, username, first_name, joined_date) VALUES (?, ?, ?, ?)",
            (user.id, user.username, user.first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
    conn.close()

def is_premium(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT expiry_date FROM subscriptions WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        expiry_date = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        if datetime.now() < expiry_date:
            return True
        else:
            # Expired, remove from database
            remove_subscription(user_id)
    return False

def add_subscription(user_id, days=30):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    expiry_date = datetime.now() + timedelta(days=days)
    cursor.execute("""
        INSERT INTO subscriptions (user_id, expiry_date) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET expiry_date = ?
    """, (user_id, expiry_date.strftime("%Y-%m-%d %H:%M:%S"), expiry_date.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def remove_subscription(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subscriptions WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_user_sessions(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT slot_number, phone, account_name, account_id, status FROM user_sessions WHERE user_id = ? ORDER BY slot_number", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def save_user_session(user_id, phone, session_string, account_name="User", account_id="0"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Find next available slot from 1 to 20
    cursor.execute("SELECT slot_number FROM user_sessions WHERE user_id = ? ORDER BY slot_number", (user_id,))
    existing_slots = [row[0] for row in cursor.fetchall()]
    
    next_slot = 1
    for i in range(1, 21):
        if i not in existing_slots:
            next_slot = i
            break
            
    cursor.execute("""
        INSERT INTO user_sessions (user_id, slot_number, phone, session_string, account_name, account_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, next_slot, phone, session_string, account_name, account_id))
    conn.commit()
    conn.close()
    return next_slot
