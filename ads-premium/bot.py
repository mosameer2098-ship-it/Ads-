import os
import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from database import (init_db, save_user, is_premium, get_user_expiry, get_bot_config, 
                      set_source_channel, set_time_interval, get_user_groups, 
                      toggle_group_selection, set_all_groups_selection, get_user_channels, 
                      get_remaining_days, save_user_session, get_user_sessions, 
                      get_active_slot, set_active_slot, 
                      get_slot_session, remove_user_session, set_slot_stopped,
                      add_premium_subscription, remove_premium_subscription,
                      get_custom_share_message)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = 32222378
API_HASH = "35fa506b69e293835d37158ea97557cf"

ADMIN_ID = 8453975447
BOT_USERNAME = "Automatic_posttbot"

FORCE_CHANNEL_USERNAME = "@iqra_music_support"
ADMIN_CONTACT_USERNAME = "AdsNova0"

user_login_state = {}
forwarded_counts = {}

# --- CHANNEL MEMBERSHIP CHECK ---
async def check_channel_membership(user_id, context):
    if user_id == ADMIN_ID:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id=FORCE_CHANNEL_USERNAME, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception:
        pass
    return False

# --- PREMIUM CHECK FOR BUTTONS ---
def check_user_access(user_id):
    if user_id == ADMIN_ID:
        return True
    return is_premium(user_id)

async def get_main_keyboard(user_id):
    active_slot = get_active_slot(user_id)
    slot_info = get_slot_session(user_id, active_slot)
    is_stopped = slot_info[3] if slot_info else 0
    
    keyboard = []
    if is_stopped:
        keyboard.append([InlineKeyboardButton(f"🛑 Stop Slot {active_slot}", callback_data=f"stop_slot_{active_slot}"), InlineKeyboardButton("🚪 Logout", callback_data="logout_acc")])
    else:
        keyboard.append([InlineKeyboardButton(f"🛑 Stop Slot {active_slot}", callback_data=f"stop_slot_{active_slot}"), InlineKeyboardButton("🚪 Logout", callback_data="logout_acc")])
        
    keyboard.append([InlineKeyboardButton("📊 Status", callback_data="status"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")])
    keyboard.append([InlineKeyboardButton("💎 Subscription", callback_data="subscription"), InlineKeyboardButton("💡 Help", callback_data="help")])
    keyboard.append([InlineKeyboardButton(f"🔄 Switch Account (Slot {active_slot})", callback_data="switch_acc")])
    keyboard.append([InlineKeyboardButton("✨ Refresh", callback_data="refresh"), InlineKeyboardButton("🛠️ Help Centre", callback_data="help")])
    return InlineKeyboardMarkup(keyboard)

async def set_bot_commands(application):
    user_commands = [
        BotCommand("start", "Start AdsNova Pro Bot 🚀"),
        BotCommand("menu", "Open main menu 📋"),
        BotCommand("status", "Check posting status 📊"),
        BotCommand("stop", "Stop ad posting ⏹️"),
        BotCommand("logout", "Logout from account 🚪"),
    ]
    await application.bot.set_my_commands(user_commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)
    
    is_joined = await check_channel_membership(user.id, context)
    if not is_joined:
        join_text = (
            "🚨 **Channel Join Required!** 🚨\n\n"
            "Bot ko use karne ke liye aapko hamara official channel join karna zaroori hai. "
            "Channel join karne ke baad niche diye gaye **'Check Membership'** button par click karein:"
        )
        keyboard = [
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_CHANNEL_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton("🔄 Check Membership", callback_data="check_membership")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(join_text, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await update.message.reply_text(join_text, parse_mode="Markdown", reply_markup=reply_markup)
        return

    welcome_text = (
        "💎 **AdsNova Pro Bot - Main Menu** 💎\n\n"
        "✨ Premium Automation Service - Fast & Reliable\n"
        "⚡ Random Intervals for natural posting\n"
        "🛡️ Your profile stays clean & unchanged\n\n"
        "👇 Choose an option below:"
    )
    kb = await get_main_keyboard(user.id)
    if update.callback_query:
        await update.callback_query.edit_message_text(welcome_text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=kb)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not await check_channel_membership(user_id, context):
        query = update.callback_query
        join_msg = "❌ Aapne channel leave kar diya hai! Pehle channel join karein phir dashboard access hoga."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_CHANNEL_USERNAME.replace('@', '')}"), InlineKeyboardButton("🔄 Check", callback_data="check_membership")]])
        if query: await query.edit_message_text(join_msg, reply_markup=kb)
        else: await update.message.reply_text(join_msg, reply_markup=kb)
        return

    # Non-premium restriction check
    if not check_user_access(user_id):
        text = "❌ **Access Denied!**\nAapka subscription active nahi hai. Sabhi features ko use karne ke liye pehle subscription buy karein."
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Buy Subscription", url=f"https://t.me/{ADMIN_CONTACT_USERNAME}")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
        ])
        if update.callback_query: await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
        else: await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        return

    if user_id == ADMIN_ID:
        try:
            import sqlite3
            conn = sqlite3.connect("bot_database.db")
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            try:
                cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE expiry_date > ?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
                prem_users = cursor.fetchone()[0]
            except Exception: prem_users = 0
            try:
                cursor.execute("SELECT COUNT(*) FROM user_sessions WHERE is_stopped = 0")
                active_ids = cursor.fetchone()[0]
            except Exception: active_ids = 0
            conn.close()
        except Exception:
            total_users, prem_users, active_ids = "N/A", "N/A", "N/A"

        admin_text = (
            "👑 **Admin Dashboard** 👑\n\n"
            f"👥 Total Users: {total_users}\n"
            f"💎 Premium Users: {prem_users}\n"
            f"🚀 Currently Active IDs: {active_ids}\n"
        )
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]])
        if update.callback_query: await update.callback_query.edit_message_text(admin_text, parse_mode="Markdown", reply_markup=reply_markup)
        else: await update.message.reply_text(admin_text, parse_mode="Markdown", reply_markup=reply_markup)
        return

    config = get_bot_config(user_id)
    chan = config[0] if config and config[0] else "Auto-Detect (Active)"
    t_int = config[1] if config else 30
    active_slot = get_active_slot(user_id)
    slot_data = get_slot_session(user_id, active_slot)
    
    login_status = "Logged In" if slot_data else "Not Logged In"
    acc_name = slot_data[2] if slot_data else "N/A"
    is_stopped = slot_data[3] if slot_data else 0
    forwarding_status = "Stopped" if is_stopped else "Active (Running)"
    sub_status = "Active ✅" if is_premium(user_id) else "Inactive ❌"
    groups = get_user_groups(user_id)
    sel_groups = sum(1 for g in groups if g[2] == 1)
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
        f"📌 Account Status: Connected ✅\n"
        f"🏷️ Name: {acc_name}"
    )
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(f"🛑 Stop Slot {active_slot}", callback_data=f"stop_slot_{active_slot}"), InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]])
    if update.callback_query: await update.callback_query.edit_message_text(status_text, parse_mode="Markdown", reply_markup=reply_markup)
    else: await update.message.reply_text(status_text, parse_mode="Markdown", reply_markup=reply_markup)

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await check_channel_membership(user_id, context): return
    if not check_user_access(user_id): return
    active_slot = get_active_slot(user_id)
    set_slot_stopped(user_id, active_slot, 1)
    await update.message.reply_text(f"🛑 Slot {active_slot} stopped successfully.")

async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await check_channel_membership(user_id, context): return
    if not check_user_access(user_id): return
    active_slot = get_active_slot(user_id)
    remove_user_session(user_id, active_slot)
    await update.message.reply_text(f"🚪 Slot {active_slot} logged out successfully.")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text("👑 **Admin Panel:**\n- `/addsub <user_id>`\n- `/delsub <user_id>`\n- `/broadcast <msg>`", parse_mode="Markdown")

async def addsub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: return
    try:
        t_id = int(context.args[0])
        add_premium_subscription(t_id, days=30)
        await update.message.reply_text(f"✅ User `{t_id}` ko 30 din ka subscription mil gaya!", parse_mode="Markdown")
    except Exception as e: await update.message.reply_text(f"❌ Error: {e}")

async def delsub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: return
    try:
        t_id = int(context.args[0])
        remove_premium_subscription(t_id)
        await update.message.reply_text(f"❌ User `{t_id}` ka subscription hata diya gaya.", parse_mode="Markdown")
    except Exception as e: await update.message.reply_text(f"❌ Error: {e}")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: return
    broadcast_msg = " ".join(context.args)
    bot_link = f"https://t.me/{BOT_USERNAME}"
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Start AdsNova Pro", url=bot_link)]])
    
    import sqlite3
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    
    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=broadcast_msg, parse_mode="Markdown", reply_markup=reply_markup)
            await asyncio.sleep(0.05)
        except Exception: continue
    await update.message.reply_text("✅ Broadcast complete!")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "check_membership":
        is_joined = await check_channel_membership(user_id, context)
        if is_joined: await start(update, context)
        else: await query.answer("❌ Aapne abhi tak channel join nahi kiya hai!", show_alert=True)
        return

    if not await check_channel_membership(user_id, context):
        join_text = "❌ **Channel Join Required!**\nAapne channel leave kar diya hai. Bot use karne ke liye pehle channel join karein:"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_CHANNEL_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton("🔄 Check Membership", callback_data="check_membership")]
        ])
        await query.edit_message_text(join_text, parse_mode="Markdown", reply_markup=kb)
        return

    if data == "main_menu":
        user_login_state.pop(user_id, None)
        await start(update, context)
        return

    # Subscription button sabhi ke liye open rahega taaki non-premium user buy kar sake
    if data == "subscription":
        if user_id == ADMIN_ID:
            sub_text = "💎 **Subscription Status & Details** 💎\n\n🌟 Your Subscription: Active ✅\n⏳ Expiry Date: `Lifetime (Admin) ♾️`\n⏱️ Remaining Time: `Unlimited`"
        elif is_premium(user_id):
            expiry_str = get_user_expiry(user_id)
            remaining = get_remaining_days(user_id)
            sub_text = f"💎 **Subscription Status & Details** 💎\n\n🌟 Your Subscription: Active ✅\n⏳ Expiry Date: `{expiry_str}`\n⏱️ Remaining Time: `{remaining}`"
        else:
            sub_text = "💎 **Subscription Status & Details** 💎\n\n🌟 Your Subscription: Inactive ❌\n\nAapka subscription active nahi hai. Plan buy karne ke liye niche click karein:"
        
        keyboard = []
        if user_id != ADMIN_ID and not is_premium(user_id):
            keyboard.append([InlineKeyboardButton("🛒 Buy Subscription", url=f"https://t.me/{ADMIN_CONTACT_USERNAME}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")])
        await query.edit_message_text(sub_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Baaki sabhi buttons ke liye Non-Premium Restriction Check
    if not check_user_access(user_id):
        text = "❌ **Subscription Required!**\nAapka subscription active nahi hai. Bot ke features use karne ke liye pehle plan buy karein."
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Buy Subscription", url=f"https://t.me/{ADMIN_CONTACT_USERNAME}")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
        return

    if data == "status":
        await status_command(update, context)

    elif data == "switch_acc":
        sessions = get_user_sessions(user_id)
        filled_slots = len(sessions)
        active_slot = get_active_slot(user_id)
        connected_slots = {s[0] for s in sessions}
        
        keyboard = []
        row = []
        for i in range(1, 21):
            icon = "🟢"
            if i in connected_slots: icon = "🔴"
            if i == active_slot: icon = "👉"
            row.append(InlineKeyboardButton(f"{icon} {i}", callback_data=f"slot_click_{i}"))
            if len(row) == 5:
                keyboard.append(row)
                row = []
        keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")])
        
        text = f"🔄 **Switch Account**\n\n📍 Active Slot: {active_slot}\n📊 {filled_slots}/20 slots filled"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("slot_click_"):
        slot_num = int(data.split("_")[2])
        slot_data = get_slot_session(user_id, slot_num)
        if slot_data:
            set_active_slot(user_id, slot_num)
            await query.edit_message_text(f"✅ Switched to Slot {slot_num}!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]))
        else:
            user_login_state[user_id] = {"step": "waiting_phone", "slot_number": slot_num}
            await query.edit_message_text(f"📱 **Telegram Account Login (Slot {slot_num})**\n\nApna Phone Number country code ke sath bhejein (Jaise: +919876543210):", parse_mode="Markdown")

    elif data.startswith("stop_slot_"):
        slot_num = int(data.split("_")[2])
        set_slot_stopped(user_id, slot_num, 1)
        await query.edit_message_text(f"🛑 Slot {slot_num} Stopped.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]))

    elif data == "logout_acc":
        active_slot = get_active_slot(user_id)
        remove_user_session(user_id, active_slot)
        await query.edit_message_text(f"🚪 Slot {active_slot} Logged Out!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]))

    elif data == "settings":
        # Aapka bilkul exact purana Settings Menu look
        keyboard = [
            [InlineKeyboardButton("📢 1 Source Channel Setup", callback_data="opt_1")],
            [InlineKeyboardButton("👥 2 Auto Forward to Groups", callback_data="opt_2")],
            [InlineKeyboardButton("⏱️ 3 Time Interval Settings", callback_data="opt_3")],
            [InlineKeyboardButton("💬 4 Auto-Reply Share Message", callback_data="opt_4")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
        ]
        await query.edit_message_text("⚙️ **AdsNova Settings Menu**\n\nAap apni zaroorat ke mutabiq option chun sakte hain:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "opt_1" or data.startswith("set_chan_sel_"):
        channels = get_user_channels(user_id)
        if not channels:
            await query.edit_message_text("❌ Aapke account mein koi channel nahi mila!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]))
            return
        if data.startswith("set_chan_sel_"):
            idx = int(data.split("_")[3])
            c_name = channels[idx][1]
            set_source_channel(user_id, c_name)
            await query.edit_message_text(f"✅ Source Channel Successfully Set to '{c_name}'!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]))
            return
        keyboard = [[InlineKeyboardButton(f"📌 {cname}", callback_data=f"set_chan_sel_{i}")] for i, (cid, cname) in enumerate(channels)]
        keyboard.append([InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")])
        await query.edit_message_text("📢 **Select Source Channel**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "opt_2" or data.startswith("grp_page_") or data.startswith("grp_tog_") or data in ["grp_select_all", "grp_deselect_all", "grp_done"]:
        groups = get_user_groups(user_id)
        if not groups:
            await query.edit_message_text("❌ Aapke account mein koi group nahi mila!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]))
            return
        total_groups = len(groups)
        page = 0
        if data.startswith("grp_page_"): page = int(data.split("_")[2])
        elif data.startswith("grp_tog_"):
            parts = data.split("_")
            toggle_group_selection(user_id, parts[2])
            page = int(parts[3])
            groups = get_user_groups(user_id)
        elif data == "grp_select_all": set_all_groups_selection(user_id, 1); groups = get_user_groups(user_id)
        elif data == "grp_deselect_all": set_all_groups_selection(user_id, 0); groups = get_user_groups(user_id)
        elif data == "grp_done":
            await query.edit_message_text("✅ Selected groups successfully saved!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]))
            return

        per_page = 10
        start_idx = page * per_page
        end_idx = min(start_idx + per_page, total_groups)
        keyboard = [[InlineKeyboardButton(f"{'✅' if is_sel == 1 else '☑️'} {g_name}", callback_data=f"grp_tog_{g_id}_{page}")] for g_id, g_name, is_sel in groups[start_idx:end_idx]]
        
        nav = []
        if page > 0: nav.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"grp_page_{page-1}"))
        if end_idx < total_groups: nav.append(InlineKeyboardButton("➡️ Next", callback_data=f"grp_page_{page+1}"))
        if nav: keyboard.append(nav)
        keyboard.append([InlineKeyboardButton("☑️ Select All", callback_data="grp_select_all"), InlineKeyboardButton("🔲 Deselect All", callback_data="grp_deselect_all")])
        keyboard.append([InlineKeyboardButton("✔️ Done", callback_data="grp_done")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")])
        await query.edit_message_text(f"👥 **Select Target Groups**\n\nShowing {start_idx+1}-{end_idx} of {total_groups}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "opt_3":
        config = get_bot_config(user_id)
        current_time = config[1] if config else 30
        keyboard = [
            [InlineKeyboardButton("⚡ 20s", callback_data="time_20"), InlineKeyboardButton("⚡ 30s", callback_data="time_30"), InlineKeyboardButton("⚡ 60s", callback_data="time_60")],
            [InlineKeyboardButton("⚡ 120s", callback_data="time_120"), InlineKeyboardButton("⚡ 300s", callback_data="time_300")],
            [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]
        ]
        await query.edit_message_text(f"⏱️ **Time Interval Settings**\n\nCurrent Active Time: {current_time} seconds", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("time_"):
        t_val = int(data.split("_")[1])
        set_time_interval(user_id, t_val)
        await query.edit_message_text(f"✅ Time Interval Successfully Set to {t_val}s!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]))

    elif data == "opt_4":
        if user_id != ADMIN_ID: return
        user_login_state[user_id] = {"step": "waiting_custom_msg"}
        current_msg = get_custom_share_message(ADMIN_ID)
        await query.edit_message_text(f"💬 **Custom Auto-Reply Share Message**\n\nCurrent message:\n`{current_msg}`\n\nNaya message bhejein:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]))

def main():
    init_db()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", start))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("logout", logout_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("addsub", addsub_command))
    application.add_handler(CommandHandler("delsub", delsub_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    
    application.add_handler(CallbackQueryHandler(button_handler))

    loop = asyncio.get_event_loop()
    loop.run_until_complete(set_bot_commands(application))
    
    print("AdsNova Pro Bot is running successfully...")
    application.run_polling()

if __name__ == "__main__":
    main()
