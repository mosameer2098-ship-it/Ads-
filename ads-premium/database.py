import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, is_premium INTEGER DEFAULT 0, expiry_date TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS user_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, slot_num INTEGER, phone TEXT, session_string TEXT, account_name TEXT, account_id TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS bot_config (user_id INTEGER PRIMARY KEY, source_channel TEXT, time_interval INTEGER DEFAULT 30)")
    cursor.execute("CREATE TABLE IF NOT EXISTS user_groups (user_id INTEGER, group_id TEXT, group_name TEXT, is_selected INTEGER DEFAULT 0)")
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
        if row[1]:
            try:
                exp_date = datetime.strptime(row[1], "%Y-%m-%d")
                if datetime.now() > exp_date:
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
    cursor.execute("SELECT source_channel, time_interval FROM bot_config WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row if row else ("Promotion Channel", 30)

def set_source_channel(user_id, channel):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO bot_config (user_id, source_channel, time_interval) VALUES (?, ?, COALESCE((SELECT time_interval FROM bot_config WHERE user_id = ?), 30))", (user_id, channel, user_id))
    conn.commit()
    conn.close()

def set_time_interval(user_id, interval):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO bot_config (user_id, source_channel, time_interval) VALUES (?, COALESCE((SELECT source_channel FROM bot_config WHERE user_id = ?), 'Promotion Channel'), ?)", (user_id, user_id, interval))
    conn.commit()
    conn.close()

def get_user_groups(user_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    # Dummy sync / fetch for demo if empty
    cursor.execute("SELECT COUNT(*) FROM user_groups WHERE user_id = ?", (user_id,))
    if cursor.fetchone()[0] == 0:
        # Sample 25 groups for testing pagination like screenshot
        for i in range(1, 26):
            cursor.execute("INSERT INTO user_groups (user_id, group_id, group_name, is_selected) VALUES (?, ?, ?, 0)", (user_id, f"g_{i}", f"Promotion Group {i}"))
        conn.commit()
    
    cursor.execute("SELECT group_id, group_name, is_selected FROM user_groups WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def toggle_group_selection(user_id, group_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT is_selected FROM user_groups WHERE user_id = ? AND group_id = ?", (user_id, group_id))
    row = cursor.fetchone()
    if row:
        new_val = 0 if row[0] == 1 else 1
        cursor.execute("UPDATE user_groups SET is_selected = ? WHERE user_id = ? AND group_id = ?", (new_val, user_id, group_id))
        conn.commit()
    conn.close()

def set_all_groups_selection(user_id, select_state):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE user_groups SET is_selected = ? WHERE user_id = ?", (select_state, user_id))
    conn.commit()
    conn.close()
    
