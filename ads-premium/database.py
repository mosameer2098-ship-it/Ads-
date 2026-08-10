import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, is_premium INTEGER DEFAULT 0, expiry_date TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS user_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, slot_num INTEGER, phone TEXT, session_string TEXT, account_name TEXT, account_id TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS bot_config (user_id INTEGER PRIMARY KEY, source_channel TEXT, selected_groups TEXT, time_interval INTEGER DEFAULT 30)")
    conn.commit()
    conn.close()

def save_user(user):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user.id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, username, first_name, is_premium) VALUES (?, ?, ?, 0)", (user.id, user.username, user.first_name))
        conn.commit()
    conn.close()

def is_premium(user_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT is_premium, expiry_date FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0] == 1:
        # Check expiry if set
        if row[1]:
            try:
                exp_date = datetime.strptime(row[1], "%Y-%m-%d")
                if datetime.now() > exp_date:
                    # Expired, turn off premium
                    remove_subscription_by_id(user_id)
                    return False
            except:
                pass
        return True
    return False

def get_user_expiry(user_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT expiry_date FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else "Lifetime / Active"

def add_subscription_by_id(user_id, days=30):
    from datetime import timedelta
    expiry = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, is_premium, expiry_date) VALUES (?, 1, ?)", (user_id, expiry))
    else:
        cursor.execute("UPDATE users SET is_premium = 1, expiry_date = ? WHERE user_id = ?", (expiry, user_id))
    conn.commit()
    conn.close()

def remove_subscription_by_id(user_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_premium = 0, expiry_date = NULL WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_all_premium_users():
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, expiry_date FROM users WHERE is_premium = 1")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_bot_config(user_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT source_channel, selected_groups, time_interval FROM bot_config WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row if row else ("", "", 30)

def set_source_channel(user_id, channel):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO bot_config (user_id, source_channel, selected_groups, time_interval) VALUES (?, ?, COALESCE((SELECT selected_groups FROM bot_config WHERE user_id = ?), ''), COALESCE((SELECT time_interval FROM bot_config WHERE user_id = ?), 30))", (user_id, channel, user_id, user_id))
    conn.commit()
    conn.close()

def set_time_interval(user_id, interval):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO bot_config (user_id, source_channel, selected_groups, time_interval) VALUES (?, COALESCE((SELECT source_channel FROM bot_config WHERE user_id = ?), ''), COALESCE((SELECT selected_groups FROM bot_config WHERE user_id = ?), ''), ?)", (user_id, user_id, user_id, interval))
    conn.commit()
    conn.close()
