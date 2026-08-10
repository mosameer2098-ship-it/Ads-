import sqlite3

def init_db():
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            is_premium INTEGER DEFAULT 0,
            expiry_date TEXT
        )
    """)
    
    # User Sessions table (20 slots)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            slot_num INTEGER,
            phone TEXT,
            session_string TEXT,
            account_name TEXT,
            account_id TEXT
        )
    """)

    # Bot Configurations table (Source Channel, Selected Groups, Time Interval)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_config (
            user_id INTEGER PRIMARY KEY,
            source_channel TEXT,
            selected_groups TEXT,
            time_interval INTEGER DEFAULT 30
        )
    """)
    
    conn.commit()
    conn.close()

def save_user(user):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user.id,))
    existing = cursor.fetchone()
    if not existing:
        cursor.execute("INSERT INTO users (user_id, username, first_name, is_premium) VALUES (?, ?, ?, 0)",
                       (user.id, user.username, user.first_name))
        conn.commit()
    conn.close()

def is_premium(user_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT is_premium FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0] == 1:
        return True
    return False

def add_subscription(user_id, days=30):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    existing = cursor.fetchone()
    if not existing:
        cursor.execute("INSERT INTO users (user_id, is_premium) VALUES (?, 1)", (user_id,))
    else:
        cursor.execute("UPDATE users SET is_premium = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def remove_subscription(user_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_premium = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_user_sessions(user_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT slot_num, phone, account_name, account_id FROM user_sessions WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def save_user_session(user_id, phone, session_string, account_name, account_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT slot_num FROM user_sessions WHERE user_id = ?", (user_id,))
    existing_slots = [row[0] for row in cursor.fetchall()]
    
    next_slot = 1
    for i in range(1, 21):
        if i not in existing_slots:
            next_slot = i
            break
            
    cursor.execute("""
        INSERT INTO user_sessions (user_id, slot_num, phone, session_string, account_name, account_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, next_slot, phone, session_string, account_name, account_id))
    conn.commit()
    conn.close()

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

def get_bot_config(user_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT source_channel, selected_groups, time_interval FROM bot_config WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row
    return ("", "", 30)
