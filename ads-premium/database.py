import sqlite3
from datetime import datetime, timedelta

def get_db_connection():
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users table (Added referral_claimed column for 2 days free trial rule)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_date TEXT,
            referral_claimed INTEGER DEFAULT 0
        )
    """)
    
    # Subscriptions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            expiry_date TEXT
        )
    """)
    
    # Bot Config table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_config (
            user_id INTEGER PRIMARY KEY,
            source_channel TEXT,
            time_interval INTEGER
        )
    """)
    
    # User Telegram Sessions table (Multi-account slots 1-20)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            user_id INTEGER,
            slot_number INTEGER,
            phone_number TEXT,
            session_string TEXT,
            account_name TEXT,
            is_stopped INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, slot_number)
        )
    """)
    
    # Active Slot tracking table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_slots (
            user_id INTEGER PRIMARY KEY,
            active_slot INTEGER DEFAULT 1
        )
    """)
    
    # User Groups table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_groups (
            user_id INTEGER,
            group_id TEXT,
            group_name TEXT,
            is_selected INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, group_id)
        )
    """)
    
    # User Channels table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_channels (
            user_id INTEGER,
            channel_id TEXT,
            channel_name TEXT,
            PRIMARY KEY (user_id, channel_id)
        )
    """)
    
    # Custom Admin Share Message table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    conn.commit()
    conn.close()

def save_user(user):
    conn = get_db_connection()
    cursor = conn.cursor()
    joined = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date, referral_claimed)
        VALUES (?, ?, ?, ?, 0)
    """, (user.id, user.username, user.first_name, joined))
    conn.commit()
    conn.close()

# --- REFERRAL SYSTEM DATABASE FUNCTIONS ---
def check_referral_eligibility(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT referral_claimed FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row["referral_claimed"] == 0:
        return True
    return False

def claim_referral_reward(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Mark referral as claimed so user cannot claim it again
    cursor.execute("UPDATE users SET referral_claimed = 1 WHERE user_id = ?", (user_id,))
    
    # Add 2 days subscription trial
    expiry_time = datetime.now() + timedelta(days=2)
    expiry_str = expiry_time.strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("SELECT expiry_date FROM subscriptions WHERE user_id = ?", (user_id,))
    sub = cursor.fetchone()
    if sub:
        cursor.execute("UPDATE subscriptions SET expiry_date = ? WHERE user_id = ?", (expiry_str, user_id))
    else:
        cursor.execute("INSERT INTO subscriptions (user_id, expiry_date) VALUES (?, ?)", (user_id, expiry_str))
    
    conn.commit()
    conn.close()

def is_premium(user_id):
    ADMIN_ID = 8453975447
    if user_id == ADMIN_ID:
        return True
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT expiry_date FROM subscriptions WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return False
        
    expiry_str = row["expiry_date"]
    try:
        expiry_dt = datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S')
        if datetime.now() <= expiry_dt:
            return True
    except:
        pass
    return False

def is_subscription_expired(user_id):
    ADMIN_ID = 8453975447
    if user_id == ADMIN_ID:
        return False
        
    expiry_date = get_user_expiry(user_id)
    if not expiry_date:
        return True
        
    try:
        exp = datetime.strptime(expiry_date, '%Y-%m-%d %H:%M:%S')
        if datetime.now() > exp:
            return True
    except:
        return True
    return False

def get_user_expiry(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT expiry_date FROM subscriptions WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row["expiry_date"] if row else None

def get_remaining_days(user_id):
    expiry_str = get_user_expiry(user_id)
    if not expiry_str:
        return 0
    try:
        expiry_dt = datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S')
        diff = expiry_dt - datetime.now()
        return max(0, diff.days)
    except:
        return 0

def add_premium_subscription(user_id, days=30):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    current_expiry = get_user_expiry(user_id)
    now = datetime.now()
    
    if current_expiry:
        try:
            exp_dt = datetime.strptime(current_expiry, '%Y-%m-%d %H:%M:%S')
            if exp_dt > now:
                new_expiry = exp_dt + timedelta(days=days)
            else:
                new_expiry = now + timedelta(days=days)
        except:
            new_expiry = now + timedelta(days=days)
    else:
        new_expiry = now + timedelta(days=days)
        
    expiry_str = new_expiry.strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute("""
        INSERT OR REPLACE INTO subscriptions (user_id, expiry_date)
        VALUES (?, ?)
    """, (user_id, expiry_str))
    conn.commit()
    conn.close()

def remove_premium_subscription(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subscriptions WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_bot_config(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT source_channel, time_interval FROM bot_config WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return [row["source_channel"], row["time_interval"] if row["time_interval"] else 30]
    return [None, 30]

def set_source_channel(user_id, channel_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO bot_config (user_id, source_channel, time_interval)
        VALUES (?, ?, COALESCE((SELECT time_interval FROM bot_config WHERE user_id = ?), 30))
        ON CONFLICT(user_id) DO UPDATE SET source_channel = ?
    """, (user_id, channel_name, user_id, channel_name))
    conn.commit()
    conn.close()

def set_time_interval(user_id, interval):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO bot_config (user_id, source_channel, time_interval)
        VALUES (?, COALESCE((SELECT source_channel FROM bot_config WHERE user_id = ?), NULL), ?)
        ON CONFLICT(user_id) DO UPDATE SET time_interval = ?
    """, (user_id, user_id, interval, interval))
    conn.commit()
    conn.close()

def save_user_session(user_id, slot_number, phone, session_string, account_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO user_sessions (user_id, slot_number, phone_number, session_string, account_name, is_stopped)
        VALUES (?, ?, ?, ?, ?, 0)
    """, (user_id, slot_number, phone, session_string, account_name))
    conn.commit()
    conn.close()

def get_user_sessions(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT slot_number, phone_number, account_name, is_stopped FROM user_sessions WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_slot_session(user_id, slot_number):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT phone_number, session_string, account_name, is_stopped FROM user_sessions WHERE user_id = ? AND slot_number = ?", (user_id, slot_number))
    row = cursor.fetchone()
    conn.close()
    if row:
        return [row["phone_number"], row["session_string"], row["account_name"], row["is_stopped"]]
    return None

def remove_user_session(user_id, slot_number):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_sessions WHERE user_id = ? AND slot_number = ?", (user_id, slot_number))
    conn.commit()
    conn.close()

def set_slot_stopped(user_id, slot_number, is_stopped):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE user_sessions SET is_stopped = ? WHERE user_id = ? AND slot_number = ?", (is_stopped, user_id, slot_number))
    conn.commit()
    conn.close()

def get_active_slot(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT active_slot FROM active_slots WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row["active_slot"] if row else 1

def set_active_slot(user_id, slot_number):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO active_slots (user_id, active_slot)
        VALUES (?, ?)
    """, (user_id, slot_number))
    conn.commit()
    conn.close()

def save_real_groups_and_channels(user_id, groups, channels):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_groups WHERE user_id = ?", (user_id,))
    for g_id, g_name in groups:
        cursor.execute("""
            INSERT OR REPLACE INTO user_groups (user_id, group_id, group_name, is_selected)
            VALUES (?, ?, ?, 0)
        """, (user_id, str(g_id), g_name))
        
    cursor.execute("DELETE FROM user_channels WHERE user_id = ?", (user_id,))
    for c_id, c_name in channels:
        cursor.execute("""
            INSERT OR REPLACE INTO user_channels (user_id, channel_id, channel_name)
            VALUES (?, ?, ?)
        """, (user_id, str(c_id), c_name))
    conn.commit()
    conn.close()

def get_user_groups(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT group_id, group_name, is_selected FROM user_groups WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [(row["group_id"], row["group_name"], row["is_selected"]) for row in rows]

def toggle_group_selection(user_id, group_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE user_groups 
        SET is_selected = CASE WHEN is_selected = 1 THEN 0 ELSE 1 END 
        WHERE user_id = ? AND group_id = ?
    """, (user_id, group_id))
    conn.commit()
    conn.close()

def set_all_groups_selection(user_id, status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE user_groups SET is_selected = ? WHERE user_id = ?", (status, user_id))
    conn.commit()
    conn.close()

def get_user_channels(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, channel_name FROM user_channels WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [(row["channel_id"], row["channel_name"]) for row in rows]

def set_custom_share_message(user_id, message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('custom_share_msg', ?)", (message,))
    conn.commit()
    conn.close()

def get_custom_share_message(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM bot_settings WHERE key = 'custom_share_msg'")
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else "🔥 **100% Working & Free!**\n🎬 All Viral Videos & Music Unlocked Here 👇\n👉 @Iqraxmusic_bot (Click & Start Now)"
