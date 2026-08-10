import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telethon import TelegramClient
from telethon.sessions import StringSession
from database import (init_db, save_user, is_premium, get_user_expiry, get_bot_config, 
                      set_source_channel, set_time_interval, get_user_groups, 
                      toggle_group_selection, set_all_groups_selection, get_user_channels, 
                      get_remaining_days, save_user_session, get_user_sessions, 
                      save_real_groups_and_channels, get_active_slot, set_active_slot, 
                      get_slot_session, remove_user_session, set_slot_stopped,
                      add_premium_subscription, remove_premium_subscription)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = 32222378
API_HASH = "35fa506b69e293835d37158ea97557cf"

ADMIN_ID = 8132623749

user_login_state = {}

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
    keyboard.append([InlineKeyboardButton("🤖 TG ID BOT", url="https://t.me/useridinfobot")])
    return InlineKeyboardMarkup(keyboard)

async def set_bot_commands(application):
    user_commands = [
        BotCommand("start", "Start the bot 🚀"),
        BotCommand("menu", "Open main menu 📋"),
        BotCommand("status", "Check posting status 📊"),
        BotCommand("stop", "Stop ad posting ⏹️"),
        BotCommand("logout", "Logout from account 🚪"),
    ]
    await application.bot.set_my_commands(user_commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)
    
    welcome_text = (
        "🌹 **Auto Forwarding Ads Bot - Main Menu** 🌹\n\n"
        "✨ Premium Service - Fast & Reliable\n"
        "⚡ Random Intervals for natural posting\n"
        "🛡️ Your profile stays unchanged\n\n"
        "👇 Choose an option below:"
    )
    kb = await get_main_keyboard(user.id)
    if update.callback_query:
        await update.callback_query.edit_message_text(welcome_text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=kb)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    config = get_bot_config(user_id)
    chan = config[0] if config and config[0] else "Not Set"
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

    status_text = (
        "📊 **Your Account & Posting Status**\n\n"
        f"🆔 User ID: `{user_id}`\n"
        f"📂 Active Account Slot: Slot {active_slot}\n"
        f"🔐 Login Status: {login_status}\n"
        f"🌟 Subscription: {sub_status}\n\n"
        f"🚀 Forwarding Status: {forwarding_status}\n"
        f"📢 Source Channel: {chan}\n"
        f"👥 Target Groups: {sel_groups} groups selected\n"
        f"⏱️ Posting Interval: {t_int} seconds\n\n"
        f"📨 Messages Forwarded: 0\n\n"
        f"👤 **Logged-in Account Details**\n"
        f"📌 Account Status: Connected ✅\n"
        f"🏷️ Name: {acc_name}"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"🛑 Stop Slot {active_slot}", callback_data=f"stop_slot_{active_slot}"), InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]))

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    active_slot = get_active_slot(user_id)
    set_slot_stopped(user_id, active_slot, 1)
    await update.message.reply_text(f"🛑 Slot {active_slot} has been stopped successfully.")

async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    active_slot = get_active_slot(user_id)
    remove_user_session(user_id, active_slot)
    await update.message.reply_text(f"🚪 Slot {active_slot} logged out successfully.")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Aap is command ko use nahi kar sakte!")
        return
    await update.message.reply_text("👑 **Admin Panel:**\n- `/addsub <user_id>` (30 Days)\n- `/delsub <user_id>`", parse_mode="Markdown")

async def addsub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Aap is command ko use nahi kar sakte!")
        return
    if not context.args:
        await update.message.reply_text("❌ Kripya User ID bhi likhein!\nUsage: `/addsub <user_id>`", parse_mode="Markdown")
        return
    try:
        target_user_id = int(context.args[0])
        add_premium_subscription(target_user_id, days=30)
        await update.message.reply_text(f"✅ User `{target_user_id}` ko 30 din ki Premium Subscription successfully de di gayi hai!", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def delsub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Aap is command ko use nahi kar sakte!")
        return
    if not context.args:
        await update.message.reply_text("❌ Kripya User ID bhi likhein!\nUsage: `/delsub <user_id>`", parse_mode="Markdown")
        return
    try:
        target_user_id = int(context.args[0])
        remove_premium_subscription(target_user_id)
        await update.message.reply_text(f"❌ User `{target_user_id}` ki subscription hata di gayi hai.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "main_menu":
        user_login_state.pop(user_id, None)
        await start(update, context)

    elif data == "switch_acc":
        sessions = get_user_sessions(user_id)
        filled_slots = len(sessions)
        active_slot = get_active_slot(user_id)
        
        connected_slots = {s[0] for s in sessions}
        
        keyboard = []
        row = []
        for i in range(1, 21):
            icon = "🟢"
            if i in connected_slots:
                icon = "🔴"
            if i == active_slot:
                icon = "👉"
            
            row.append(InlineKeyboardButton(f"{icon} {i}", callback_data=f"slot_click_{i}"))
            if len(row) == 5:
                keyboard.append(row)
                row = []
        
        keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")])
        
        text = (
            "🔄 **Switch Account**\n\n"
            f"📍 You are currently using Slot {active_slot}.\n"
            f"📊 {filled_slots}/20 slots filled\n\n"
            "🔴 = Account connected | 🟢 = Empty slot\n"
            "👉 = Currently active\n\n"
            "👇 Select a slot to switch or login:"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("slot_click_"):
        slot_num = int(data.split("_")[2])
        slot_data = get_slot_session(user_id, slot_num)
        
        if slot_data:
            set_active_slot(user_id, slot_num)
            await query.edit_message_text(f"✅ Switched to Slot {slot_num} successfully!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]))
        else:
            user_login_state[user_id] = {"step": "waiting_phone", "slot_number": slot_num}
            await query.edit_message_text(
                f"📱 **Telegram Account Login (Slot {slot_num})**\n\nKripya apna Phone Number country code ke sath bhejein (Jaise: +919876543210):", parse_mode="Markdown"
            )

    elif data.startswith("stop_slot_"):
        slot_num = int(data.split("_")[2])
        set_slot_stopped(user_id, slot_num, 1)
        
        text = (
            f"🛑 **Slot {slot_num} Stopped**\n\n"
            "Ad posting for this slot has been stopped. Other active slots continue running normally."
        )
        keyboard = [
            [InlineKeyboardButton(f"▶️ Restart Slot {slot_num}", callback_data=f"restart_slot_{slot_num}")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("restart_slot_"):
        slot_num = int(data.split("_")[2])
        set_slot_stopped(user_id, slot_num, 0)
        set_active_slot(user_id, slot_num)
        await start(update, context)

    elif data == "logout_acc":
        active_slot = get_active_slot(user_id)
        remove_user_session(user_id, active_slot)
        await query.edit_message_text(f"🚪 Slot {active_slot} Logged Out Successfully!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]))

    elif data == "settings":
        keyboard = [
            [InlineKeyboardButton("📢 1 Source Channel Setup", callback_data="opt_1")],
            [InlineKeyboardButton("👥 2 Auto Forward to Groups", callback_data="opt_2")],
            [InlineKeyboardButton("⏱️ 3 Time Interval Settings", callback_data="opt_3")],
            [InlineKeyboardButton("💬 5 Auto-Reply Share Message", callback_data="opt_5")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
        ]
        await query.edit_message_text("⚙️ **Settings Menu**\n\nAap apni zaroorat ke mutabiq option chun sakte hain:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "opt_1" or data.startswith("set_chan_sel_"):
        channels = get_user_channels(user_id)
        if not channels:
            await query.edit_message_text(
                "❌ **Aapke account mein koi channel nahi mila!**\n\nPlz join the channel and forward your message", 
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]])
            )
            return

        if data.startswith("set_chan_sel_"):
            idx = int(data.split("_")[3])
            c_name = channels[idx][1]
            set_source_channel(user_id, c_name)
            await query.edit_message_text(
                f"✅ Source Channel Successfully Set to '{c_name}'!", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]])
            )
            return

        keyboard = []
        for index, (cid, cname) in enumerate(channels):
            keyboard.append([InlineKeyboardButton(f"📌 {cname}", callback_data=f"set_chan_sel_{index}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")])

        text = f"📢 **Select Source Channel**\n\nChoose the channel to forward ads from:\nShowing 1-{len(channels)} of {len(channels)}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    elif data == "opt_2" or data.startswith("grp_page_") or data.startswith("grp_tog_") or data == "grp_select_all" or data == "grp_deselect_all" or data == "grp_done":
        groups = get_user_groups(user_id)
        if not groups:
            await query.edit_message_text("❌ **Aapke account mein koi group nahi mila!**\n\nPlz join the group and forward your message", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]))
            return

        total_groups = len(groups)
        page = 0
        if data.startswith("grp_page_"):
            page = int(data.split("_")[2])
        elif data.startswith("grp_tog_"):
            parts = data.split("_")
            g_id = parts[2]
            page = int(parts[3])
            toggle_group_selection(user_id, g_id)
            groups = get_user_groups(user_id)
        elif data == "grp_select_all":
            set_all_groups_selection(user_id, 1)
            groups = get_user_groups(user_id)
        elif data == "grp_deselect_all":
            set_all_groups_selection(user_id, 0)
            groups = get_user_groups(user_id)
        elif data == "grp_done":
            await query.edit_message_text("✅ Selected groups successfully saved for auto-forwarding!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]))
            return

        per_page = 10
        start_idx = page * per_page
        end_idx = min(start_idx + per_page, total_groups)
        current_groups = groups[start_idx:end_idx]

        keyboard = []
        for g_id, g_name, is_sel in current_groups:
            icon = "✅" if is_sel == 1 else "☑️"
            keyboard.append([InlineKeyboardButton(f"{icon} {g_name}", callback_data=f"grp_tog_{g_id}_{page}")])

        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"grp_page_{page-1}"))
        if end_idx < total_groups:
            nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"grp_page_{page+1}"))
        if nav_buttons:
            keyboard.append(nav_buttons)

        keyboard.append([
            InlineKeyboardButton("☑️ Select All", callback_data="grp_select_all"),
            InlineKeyboardButton("🔲 Deselect All", callback_data="grp_deselect_all")
        ])
        keyboard.append([InlineKeyboardButton("✔️ Done", callback_data="grp_done")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")])

        text = f"👥 **Select Target Groups**\n\nShowing {start_idx + 1}-{end_idx} of {total_groups}\n\nTap groups to select/deselect:"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "opt_3":
        config = get_bot_config(user_id)
        current_time = config[1] if config else 30
        keyboard = [
            [InlineKeyboardButton("⚡ 20s", callback_data="time_20"), InlineKeyboardButton("⚡ 30s", callback_data="time_30"), InlineKeyboardButton("⚡ 60s", callback_data="time_60")],
            [InlineKeyboardButton("⚡ 120s", callback_data="time_120"), InlineKeyboardButton("⚡ 300s", callback_data="time_300")],
            [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]
        ]
        await query.edit_message_text(f"⏱️ **Time Interval Settings**\n\nCurrent Active Time: {current_time} seconds\nNeeche se naya time select karein:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("time_"):
        t_val = data.split("_")[1]
        set_time_interval(user_id, int(t_val))
        await query.edit_message_text(f"✅ Time Interval Successfully Set to {t_val}s!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]))

    elif data == "opt_5":
        msg_text = "✨ @Iqraxmusic_bot start and get video free"
        await query.edit_message_text(f"💬 **Auto-Reply Share Message**\n\nYeh message sabhi incoming personal chats par auto-share hoga:\n\n{msg_text}", parse_mode="Markdown")

    elif data == "status":
        await status_command(update, context)

    elif data == "subscription":
        if is_premium(user_id):
            expiry = get_user_expiry(user_id)
            rem_days = get_remaining_days(user_id)
            sub_text = (
                "💎 **Your Premium Subscription**\n\n"
                "✨ Status: Active ✅\n"
                f"⏳ Days Remaining: {rem_days} Days\n"
                f"📅 Expiry Date: {expiry}\n\n"
                "🎉 Aapke paas sabhi features unlocked hain!"
            )
        else:
            sub_text = "💎 **Premium Subscription**\n\nUnlock unlimited features!\nTo buy subscription, contact admin here: @AdsNova0"
        
        await query.edit_message_text(sub_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]))

    elif data == "help":
        await query.edit_message_text("💡 **Help & Guide**\n\nAapko support @AdsNova0 par milegi.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]))

    elif data == "refresh":
        await start(update, context)

async def handle_message_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if user_id not in user_login_state:
        return
        
    state = user_login_state[user_id]
    step = state.get("step")
    slot_number = state.get("slot_number", 1)
    
    if step == "waiting_phone":
        phone = text
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        try:
            sent = await client.send_code_request(phone)
            state["phone"] = phone
            state["client"] = client
            state["phone_code_hash"] = sent.phone_code_hash
            state["step"] = "waiting_otp"
            await update.message.reply_text(
                "📩 **OTP bhej diya gaya hai!**\n\n"
                "Kripya OTP space dekar dalein:\n"
                "❌ `12345` (Galat tarika)\n"
                "✅ `1 2 3 4 5` (Sahi tarika)", parse_mode="Markdown"
            )
        except Exception as e:
            await client.disconnect()
            user_login_state.pop(user_id, None)
            await update.message.reply_text(f"❌ Error: {e}\n\nDobara koshish karne ke liye /start dabayein.")
            
    elif step == "waiting_otp":
        otp = text.replace(" ", "")
        client = state["client"]
        phone = state["phone"]
        phone_code_hash = state["phone_code_hash"]
        
        try:
            await client.sign_in(phone=phone, code=otp, phone_code_hash=phone_code_hash)
            session_str = client.session.save()
            me = await client.get_me()
            acc_name = f"{me.first_name or ''} {me.last_name or ''}".strip()
            
            groups = []
            channels = []
            async for dialog in client.iter_dialogs():
                entity = dialog.entity
                if (dialog.is_group or getattr(entity, 'megagroup', False)) and not getattr(entity, 'broadcast', False):
                    groups.append((dialog.id, dialog.name))
                elif getattr(entity, 'broadcast', False) and not getattr(entity, 'megagroup', False):
                    if getattr(entity, 'creator', False) or getattr(entity, 'admin_rights', None) is not None:
                        channels.append((dialog.id, dialog.name))
                    
            await client.disconnect()
            
            save_user_session(user_id, slot_number, phone, session_str, acc_name)
            set_active_slot(user_id, slot_number)
            save_real_groups_and_channels(user_id, groups, channels)
            user_login_state.pop(user_id, None)
            
            kb = await get_main_keyboard(user_id)
            await update.message.reply_text(
                f"✅ **Login Successful in Slot {slot_number}! ({acc_name})**\n\n"
                f"• Real Groups Found: {len(groups)}\n"
                f"• Creator/Admin Channels Found: {len(channels)}\n\n"
                "Aap ab Settings mein jaakar apne groups aur channels select kar sakte hain!", parse_mode="Markdown",
                reply_markup=kb
            )
                
        except Exception as e:
            if "Password" in str(e) or "two-step" in str(e).lower():
                state["step"] = "waiting_password"
                await update.message.reply_text("🔒 Aapke account par Two-Step Verification (Password) laga hai. Kripya apna cloud password enter karein:")
            else:
                await client.disconnect()
                user_login_state.pop(user_id, None)
                await update.message.reply_text(f"❌ Login Failed: {e}\n\nDobara koshish karne ke liye /start dabayein.")
                
    elif step == "waiting_password":
        password = text
        client = state["client"]
        try:
            await client.sign_in(password=password)
            session_str = client.session.save()
            me = await client.get_me()
            acc_name = f"{me.first_name or ''} {me.last_name or ''}".strip()
            
            groups = []
            channels = []
            async for dialog in client.iter_dialogs():
                entity = dialog.entity
                if (dialog.is_group or getattr(entity, 'megagroup', False)) and not getattr(entity, 'broadcast', False):
                    groups.append((dialog.id, dialog.name))
                elif getattr(entity, 'broadcast', False) and not getattr(entity, 'megagroup', False):
                    if getattr(entity, 'creator', False) or getattr(entity, 'admin_rights', None) is not None:
                        channels.append((dialog.id, dialog.name))
                    
            await client.disconnect()
            
            save_user_session(user_id, slot_number, state["phone"], session_str, acc_name)
            set_active_slot(user_id, slot_number)
            save_real_groups_and_channels(user_id, groups, channels)
            user_login_state.pop(user_id, None)
            
            kb = await get_main_keyboard(user_id)
            await update.message.reply_text(
                f"✅ **Login Successful in Slot {slot_number}! ({acc_name})**\n\n"
                f"• Real Groups Found: {len(groups)}\n"
                f"• Creator/Admin Channels Found: {len(channels)}\n\n"
                "Aap ab Settings mein jaakar apne groups aur channels select kar sakte hain!", parse_mode="Markdown",
                reply_markup=kb
            )
                
        except Exception as e:
            await client.disconnect()
            user_login_state.pop(user_id, None)
            await update.message.reply_text(f"❌ Password Incorrect: {e}\n\nDobara koshish karne ke liye /start dabayein.")

def main():
    if not BOT_TOKEN:
        print("❌ Error: BOT_TOKEN environment variable set nahi hai!")
        return
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("logout", logout_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("addsub", addsub_command))
    app.add_handler(CommandHandler("delsub", delsub_command))
    
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_input))
    
    async def post_init(application):
        await set_bot_commands(application)
        
    app.post_init = post_init
    
    print("Bot is running perfectly...")
    app.run_polling()

if __name__ == "__main__":
    main()
