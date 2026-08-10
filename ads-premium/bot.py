import os
import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment Variables / Config
BOT_TOKEN = os.getenv("BOT_TOKEN", "8999765663:AAE3BdnhY5vWRe8Kd3FYcVtJoHm4dp709hE")
ADMIN_ID = 8999765663  # Apni Admin Telegram ID yahan confirm kar lein

# Global variable for tracking messages
forwarded_counts = {}

# Helper Functions (Database & Config placeholders)
def get_bot_config(user_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT source_channel, interval FROM bot_config WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def get_active_slot(user_id):
    return 1  # Default slot

def get_slot_session(user_id, slot_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_sessions WHERE user_id = ? AND slot_id = ?", (user_id, slot_id))
    row = cursor.fetchone()
    conn.close()
    return row

def is_premium(user_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT expiry_date FROM subscriptions WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S") > datetime.now():
        return True
    return False

def get_user_groups(user_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_groups WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows


# --- STATUS COMMAND (WITH ADMIN DASHBOARD & SAFE NORMAL USER STATUS) ---
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # 1. ADMIN DASHBOARD (Sirf Admin ke liye alag view)
    if user_id == ADMIN_ID:
        try:
            conn = sqlite3.connect("bot_database.db")
            cursor = conn.cursor()
            
            # Total Users
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            # Premium Users
            cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE expiry_date > ?", (datetime.now(),))
            prem_users = cursor.fetchone()[0]
            
            # Active Running IDs (Sessions)
            cursor.execute("SELECT COUNT(*) FROM user_sessions WHERE is_stopped = 0")
            active_ids = cursor.fetchone()[0]
            
            conn.close()
        except Exception as e:
            total_users = "N/A"
            prem_users = "N/A"
            active_ids = "N/A"
            logger.error(f"Admin stats error: {e}")
        
        admin_text = (
            "👑 **Admin Dashboard** 👑\n\n"
            f"👥 Total Users: {total_users}\n"
            f"💎 Premium Users: {prem_users}\n"
            f"🚀 Currently Active IDs: {active_ids}\n"
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(admin_text, parse_mode="Markdown")
        else:
            await update.message.reply_text(admin_text, parse_mode="Markdown")
        return

    # 2. NORMAL USER STATUS (Jaisa pehle tha, bilkul waisa hi secure rakha gaya hai)
    config = get_bot_config(user_id)
    chan = config[0] if config and config[0] else "Auto-Detect (Active)"
    t_int = config[1] if config else 30
    active_slot = get_active_slot(user_id)
    slot_data = get_slot_session(user_id, active_slot)
    
    login_status = "Logged In" if slot_data else "Not Logged In"
    acc_name = slot_data[2] if slot_data and len(slot_data) > 2 else "N/A"
    is_stopped = slot_data[3] if slot_data and len(slot_data) > 3 else 0
    forwarding_status = "Stopped" if is_stopped else "Active (Running)"
    
    sub_status = "Active ✅" if is_premium(user_id) else "Inactive ❌"
    groups = get_user_groups(user_id)
    sel_groups = sum(1 for g in groups if len(g) > 2 and g[2] == 1)
    msg_count = forwarded_counts.get(user_id, 0)

    status_text = (
        "📊 **AdsNova Pro - Status Dashboard**\n\n"
        f"🆔 User ID: `{user_id}`\n"
        f"📂 Active Account Slot: Slot {active_slot}\n"
        f"🔐 Login Status: {login_status}\n"
        f"🌟 Subscription: {sub_status}\n\n"
        f"🚀 Forwarding Status: {forwarding_status}\n"
        f"📢 Source Channel: {chan}\n"
        f"👥 Target Groups: {sel_groups} groups selected\n"
        f"⏱️ Posting Interval: {t_int} seconds\n\n"
        f"📨 Messages Forwarded: {msg_count}\n\n"
        f"👤 **Logged-in Account Details**\n"
        f"🏷️ Name: {acc_name}"
    )
    
    reply_markup = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"🛑 Stop Slot {active_slot}", callback_data=f"stop_slot_{active_slot}"),
        InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")
    ]])

    if update.callback_query:
        await update.callback_query.edit_message_text(status_text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(status_text, parse_mode="Markdown", reply_markup=reply_markup)

# Start Command
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to AdsNova Pro! Use /status to check your dashboard.")

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CallbackQueryHandler(status_command, pattern="^status_menu$"))
    
    print("AdsNova Pro Bot is running successfully...")
    application.run_polling()

if __name__ == "__main__":
    main()
