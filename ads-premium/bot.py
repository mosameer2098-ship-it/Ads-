import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telethon import TelegramClient
from telethon.sessions import StringSession
from database import (init_db, save_user, is_premium, get_user_expiry, get_bot_config, 
                      set_source_channel, set_time_interval, add_subscription_by_id, 
                      remove_subscription_by_id, get_all_premium_users, get_user_groups, 
                      toggle_group_selection, set_all_groups_selection, get_user_channels, 
                      get_remaining_days, save_user_session, get_user_session, save_real_groups_and_channels)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [8453975447]

# Temporary memory for interactive login flow (API ID & Hash for telethon login)
API_ID = 6 // Apni Telegram API ID yahan dalein (default public test id ya apni my.telegram.org wali)
API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"

user_login_state = {} # user_id -> {"step": "phone/otp/password", "phone": "...", "client": client, "phone_hash": "..."}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)
    
    keyboard = [
        [InlineKeyboardButton("🔑 Login / Add Accounts", callback_data="login_acc")],
        [InlineKeyboardButton("📊 Status", callback_data="status"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton("💎 Subscription", callback_data="subscription"), InlineKeyboardButton("❓ Help", callback_data="help")],
        [InlineKeyboardButton("🔄 Switch Account", callback_data="switch_acc"), InlineKeyboardButton("🔄 Refresh", callback_data="refresh")]
    ]
    await update.message.reply_text(f"🏠 **Main Dashboard**\n\nNeeche se koi option select karein.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "login_acc":
        user_login_state[user_id] = {"step": "waiting_phone"}
        await query.edit_message_text(
            "📱 **Telegram Account Login**\n\nKripya apna **Phone Number** country code ke sath bhejein (Jaise: `+919876543210`):",
            parse_mode="Markdown"
        )

    elif data == "settings":
        keyboard = [
            [InlineKeyboardButton("1️⃣ Source Channel Setup", callback_data="opt_1")],
            [InlineKeyboardButton("2️⃣ Auto Forward to Groups", callback_data="opt_2")],
            [InlineKeyboardButton("3️⃣ Time Interval Settings", callback_data="opt_3")],
            [InlineKeyboardButton("5️⃣ Auto-Reply Share Message", callback_data="opt_5")],
            [InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]
        ]
        await query.edit_message_text("⚙️ **Settings Menu**\n\nAap apni zaroorat ke mutabiq option chun sakte hain:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "main_menu":
        user_login_state.pop(user_id, None)
        keyboard = [
            [InlineKeyboardButton("🔑 Login / Add Accounts", callback_data="login_acc")],
            [InlineKeyboardButton("📊 Status", callback_data="status"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
            [InlineKeyboardButton("💎 Subscription", callback_data="subscription"), InlineKeyboardButton("❓ Help", callback_data="help")],
            [InlineKeyboardButton("🔄 Switch Account", callback_data="switch_acc"), InlineKeyboardButton("🔄 Refresh", callback_data="refresh")]
        ]
        await query.edit_message_text(f"🏠 **Main Dashboard**\n\nNeeche se koi option select karein.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "opt_1" or data.startswith("set_chan_sel_"):
        channels = get_user_channels(user_id)
        if not channels:
            await query.edit_message_text("❌ Aapke account mein koi channel nahi mila!\n\n**Plz join the group and forward your message**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]), parse_mode="Markdown")
            return

        if data.startswith("set_chan_sel_"):
            c_name = data.split("_", 3)[3]
            set_source_channel(user_id, c_name)
            await query.edit_message_text(f"✅ **Source Channel Successfully Set to '{c_name}'!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]), parse_mode="Markdown")
            return

        keyboard = []
        for cid, cname in channels:
            keyboard.append([InlineKeyboardButton(f"📢 {cname}", callback_data=f"set_chan_sel_{cid}_{cname}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")])

        text = f"📢 **Select Source Channel**\n\nChoose the channel to forward ads from:\nShowing 1-{len(channels)} of {len(channels)}"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "opt_2" or data.startswith("grp_page_") or data.startswith("grp_tog_") or data == "grp_select_all" or data == "grp_deselect_all" or data == "grp_done":
        groups = get_user_groups(user_id)
        if not groups:
            await query.edit_message_text("❌ Aapke account mein koi group nahi mila!\n\n**Plz join the group and forward your message**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]), parse_mode="Markdown")
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
            await query.edit_message_text("✅ **Selected groups successfully saved for auto-forwarding!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]), parse_mode="Markdown")
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
            nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"grp_page_{page+1}"))
        if nav_buttons:
            keyboard.append(nav_buttons)

        keyboard.append([
            InlineKeyboardButton("Select All", callback_data="grp_select_all"),
            InlineKeyboardButton("Deselect All", callback_data="grp_deselect_all")
        ])
        keyboard.append([InlineKeyboardButton("✅ Done", callback_data="grp_done")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")])

        text = f"👥 **Select Target Groups**\n\nShowing {start_idx + 1}-{end_idx} of {total_groups}\n\nTap groups to select/deselect:"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "opt_3":
        config = get_bot_config(user_id)
        current_time = config[1] if config else 30
        keyboard = [
            [InlineKeyboardButton("20s", callback_data="time_20"), InlineKeyboardButton("30s", callback_data="time_30"), InlineKeyboardButton("60s", callback_data="time_60")],
            [InlineKeyboardButton("120s", callback_data="time_120"), InlineKeyboardButton("300s", callback_data="time_300")],
            [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]
        ]
        await query.edit_message_text(f"⏱️ **Option 3: Time Interval Settings**\n\nCurrent Active Time: **{current_time} seconds**\nNeeche se naya time select karein:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("time_"):
        t_val = data.split("_")[1]
        set_time_interval(user_id, int(t_val))
        await query.edit_message_text(f"✅ **Time Interval Successfully Set to {t_val}s!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]), parse_mode="Markdown")

    elif data == "opt_5":
        msg_text = "✨ @Iqraxmusic_bot start and get video free"
        await query.edit_message_text(f"🤖 **Option 5: Auto-Reply Share Message**\n\nYeh message sabhi incoming personal chats par auto-share hoga:\n\n`{msg_text}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]), parse_mode="Markdown")

    elif data == "status":
        config = get_bot_config(user_id)
        chan = config[0] if config and config[0] else "Not Set"
        t_int = config[1] if config else 30
        status_text = f"📊 **Bot Status Dashboard**\n\n• Source Channel: {chan}\n• Time Interval Selected: {t_int}s\n• Premium Status: {'Active 💎' if is_premium(user_id) else 'Free Plan ❌'}"
        await query.edit_message_text(status_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]), parse_mode="Markdown")

    elif data == "subscription":
        if is_premium(user_id):
            expiry = get_user_expiry(user_id)
            rem_days = get_remaining_days(user_id)
            sub_text = (
                f"💎 **Your Premium Subscription**\n\n"
                f"Status: **Active ✅**\n"
                f"⏳ Days Remaining: **{rem_days} Days**\n"
                f"📅 Expiry Date: **{expiry}**\n\n"
                f"Aapke paas sabhi features unlocked hain!"
            )
        else:
            sub_text = "💎 **Premium Subscription**\n\nUnlock unlimited features!\nTo buy subscription, contact admin here: **@AdsNova0**"
        
        await query.edit_message_text(sub_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]), parse_mode="Markdown")

    elif data == "help":
        await query.edit_message_text("❓ **Help & Guide**\n\nAapko support @AdsNova0 par milegi.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]), parse_mode="Markdown")

    elif data in ["switch_acc", "refresh"]:
        session = get_user_session(user_id)
        if session:
            try:
                client = TelegramClient(StringSession(session[1]), API_ID, API_HASH)
                await client.connect()
                groups = []
                channels = []
                async for dialog in client.iter_dialogs():
                    if dialog.is_group:
                        groups.append((dialog.id, dialog.name))
                    elif dialog.is_channel:
                        channels.append((dialog.id, dialog.name))
                await client.disconnect()
                save_real_groups_and_channels(user_id, groups, channels)
                await query.edit_message_text(f"🔄 **Refreshed Successfully!**\nFound {len(groups)} groups and {len(channels)} channels from your account.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]), parse_mode="Markdown")
            except Exception as e:
                await query.edit_message_text(f"❌ Refresh failed: {e}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]), parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ Pehle apni ID login karein (`Login / Add Accounts`).", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]), parse_mode="Markdown")

# Handle interactive login inputs (Phone, OTP, Password)
async def handle_message_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if user_id not in user_login_state:
        return
        
    state = user_login_state[user_id]
    step = state.get("step")
    
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
            await update.message.reply_text("📨 OTP bhej diya gaya hai! Kripya woh **OTP** yahan enter karein (agar number ke beech space ho toh hata kar dalein, e.g., `1 2 3 4 5` ki jagah `12345`):")
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
            # Login successful! Fetch real groups and channels
            session_str = client.session.save()
            me = await client.get_me()
            acc_name = f"{me.first_name or ''} {me.last_name or ''}".strip()
            
            groups = []
            channels = []
            async for dialog in client.iter_dialogs():
                if dialog.is_group:
                    groups.append((dialog.id, dialog.name))
                elif dialog.is_channel:
                    channels.append((dialog.id, dialog.name))
                    
            await client.disconnect()
            
            save_user_session(user_id, phone, session_str, acc_name)
            save_real_groups_and_channels(user_id, groups, channels)
            user_login_state.pop(user_id, None)
            
            if not groups and not channels:
                await update.message.reply_text("✅ Login Successful, lekin aapke account mein koi group ya channel nahi mila!\n\n**Plz join the group and forward your message**")
            else:
                await update.message.reply_text(f"✅ **Login Successful! ({acc_name})**\n\n• Real Groups Found: `{len(groups)}`\n• Real Channels Found: `{len(channels)}`\n\nAap ab Settings mein jaakar apne groups aur channels dekh sakte hain!", parse_mode="Markdown")
                
        except Exception as e:
            if "Password" in str(e) or "two-step" in str(e).lower():
                state["step"] = "waiting_password"
                await update.message.reply_text("🔒 Aapke account par **Two-Step Verification (Password)** laga hai. Kripya apna cloud password enter karein:")
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
                if dialog.is_group:
                    groups.append((dialog.id, dialog.name))
                elif dialog.is_channel:
                    channels.append((dialog.id, dialog.name))
                    
            await client.disconnect()
            
            save_user_session(user_id, state["phone"], session_str, acc_name)
            save_real_groups_and_channels(user_id, groups, channels)
            user_login_state.pop(user_id, None)
            
            if not groups and not channels:
                await update.message.reply_text("✅ Login Successful, lekin aapke account mein koi group ya channel nahi mila!\n\n**Plz join the group and forward your message**")
            else:
                await update.message.reply_text(f"✅ **Login Successful! ({acc_name})**\n\n• Real Groups Found: `{len(groups)}`\n• Real Channels Found: `{len(channels)}`\n\nAap ab Settings mein jaakar apne groups aur channels dekh sakte hain!", parse_mode="Markdown")
                
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
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_input))
    
    print("Bot is running successfully with Interactive Login & Real Groups...")
    app.run_polling()

if __name__ == "__main__":
    main()
