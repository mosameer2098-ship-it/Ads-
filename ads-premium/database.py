import sqlite3
from datetime import datetime, timedelta

def init_db():
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_date TEXT,
            expiry_date TEXT,
            is_prem INTEGER DEFAULT 0
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
        CREATE TABLE IF NOT EXISTS user_groups (
            user_id INTEGER,
            group_id TEXT,
            group_name TEXT,
            is_selected INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, group_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_channels (
            user_id INTEGER,
            channel_id TEXT,
            channel_name TEXT,
            PRIMARY KEY (user_id, channel_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            user_id INTEGER,
            slot_number INTEGER,
            phone TEXT,
            session_string TEXT,
            acc_name TEXT,
            is_stopped INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, slot_number)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_slots (
            user_id INTEGER PRIMARY KEY,
            active_slot INTEGER DEFAULT 1
        )
    """)
    
    conn.commit()
    conn.close()

def save_user(user):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user.id,))
    row = cursor.fetchone()
    if not row:
        joined = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        expiry = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date, expiry_date, is_prem) VALUES (?, ?, ?, ?, ?, 1)",
                       (user.id, user.username, user.first_name, joined, expiry))
        conn.commit()
    conn.close()

def is_premium(user_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT expiry_date FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        expiry = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        if datetime.now() < expiry:
            return True
    return False

def get_user_expiry(user_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT expiry_date FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "N/A"

def get_remaining_days(user_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT expiry_date FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        expiry = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        rem = expiry - datetime.now()
        return max(0, rem.days)
    return 0

def add_premium_subscription(user_id, days=30):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    expiry = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE users SET expiry_date = ?, is_prem = 1 WHERE user_id = ?", (expiry, user_id))
    else:
        joined = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO users (user_id, username, first_name, joined_date, expiry_date, is_prem) VALUES (?, 'AdminAdded', 'User', ?, ?, 1)",
                       (user_id, joined, expiry))
    conn.commit()
    conn.close()

def remove_premium_subscription(user_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    expiry = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE users SET expiry_date = ?, is_prem = 0 WHERE user_id = ?", (expiry, user_id))
    conn.commit()
    conn.close()

def get_bot_config(user_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT source_channel, time_interval FROM bot_config WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def set_source_channel(user_id, channel_name):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO bot_config (user_id, source_channel, time_interval) VALUES (?, ?, COALESCE((SELECT time_interval FROM bot_config WHERE user_id = ?), 30))",
                   (user_id, channel_name, user_id))
    conn.commit()
    conn.close()

def set_time_interval(user_id, interval):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO bot_config (user_id, source_channel, time_interval) VALUES (?, COALESCE((SELECT source_channel FROM bot_config WHERE user_id = ?), NULL), ?)",
                   (user_id, user_id, interval))
    conn.commit()
    conn.close()

def save_real_groups_and_channels(user_id, groups, channels):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_groups WHERE user_id = ?", (user_id,))
    for g_id, g_name in groups:
        cursor.execute("INSERT OR IGNORE INTO user_groups (user_id, group_id, group_name, is_selected) VALUES (?, ?, ?, 0)",
                       (user_id, str(g_id), g_name))
    cursor.execute("DELETE FROM user_channels WHERE user_id = ?", (user_id,))
    for c_id, c_name in channels:
        cursor.execute("INSERT OR IGNORE INTO user_channels (user_id, channel_id, channel_name) VALUES (?, ?, ?)",
                       (user_id, str(c_id), c_name))
    conn.commit()
    conn.close()

def get_user_groups(user_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT group_id, group_name, is_selected FROM user_groups WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_user_channels(user_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, channel_name FROM user_channels WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def toggle_group_selection(user_id, group_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT is_selected FROM user_groups WHERE user_id = ? AND group_id = ?", (user_id, str(group_id)))
    row = cursor.fetchone()
    if row:
        new_val = 0 if row[0] == 1 else 1
        cursor.execute("UPDATE user_groups SET is_selected = ? WHERE user_id = ? AND group_id = ?", (new_val, user_id, str(group_id)))
        conn.commit()
    conn.close()

def set_all_groups_selection(user_id, val):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE user_groups SET is_selected = ? WHERE user_id = ?", (val, user_id))
    conn.commit()
    conn.close()

def save_user_session(user_id, slot_number, phone, session_string, acc_name):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO user_sessions (user_id, slot_number, phone, session_string, acc_name, is_stopped) VALUES (?, ?, ?, ?, ?, 0)",
                   (user_id, slot_number, phone, session_string, acc_name))
    conn.commit()
    conn.close()

def get_user_sessions(user_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT slot_number, phone, acc_name, is_stopped FROM user_sessions WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_slot_session(user_id, slot_number):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT phone, session_string, acc_name, is_stopped FROM user_sessions WHERE user_id = ? AND slot_number = ?", (user_id, slot_number))
    row = cursor.fetchone()
    conn.close()
    return row

def remove_user_session(user_id, slot_number):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_sessions WHERE user_id = ? AND slot_number = ?", (user_id, slot_number))
    conn.commit()
    conn.close()

def set_slot_stopped(user_id, slot_number, is_stopped):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE user_sessions SET is_stopped = ? WHERE user_id = ? AND slot_number = ?", (is_stopped, user_id, slot_number))
    conn.commit()
    conn.close()

def get_active_slot(user_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT active_slot FROM active_slots WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 1

def set_active_slot(user_id, slot_number):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO active_slots (user_id, active_slot) VALUES (?, ?)", (user_id, slot_number))
    conn.commit()
    conn.close()
