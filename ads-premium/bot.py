import os
import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateProfileRequest
from database import (init_db, save_user, is_premium, get_user_expiry, get_bot_config, 
                      set_source_channel, set_time_interval, get_user_groups, 
                      toggle_group_selection, set_all_groups_selection, get_user_channels, 
                      get_remaining_days, get_active_slot, set_active_slot, 
                      get_slot_session, get_user_sessions, remove_user_session, set_slot_stopped,
                      add_premium_subscription, remove_premium_subscription,
                      get_custom_share_message, check_referral_eligibility, claim_referral_reward,
                      save_user_session, save_real_groups_and_channels)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Heroku Environment Variables se directly uthayega
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = 32222378
API_HASH = "35fa506b69e293835d37158ea97557cf"

ADMIN_ID = 8453975447
BOT_USERNAME = "Automatic_posttbot"

FORCE_CHANNEL_USERNAME = "@iqra_music_support"
ADMIN_CONTACT_USERNAME = "AdsNova0"

# Bio mein set hone wala link text
BOT_BIO_LINK_TEXT = f"🚀 Bot: https://t.me/{BOT_USERNAME}"

user_login_state = {}
forwarded_counts = {}

# --- HELPER: AUTO UPDATE BIO FUNCTION ---
async def update_account_bio(client):
    try:
        # Telegram bio ki max limit 70 characters hoti hai
        bio_text = f"Bot: https://t.me/{BOT_USERNAME}"[:70]
        await client(UpdateProfileRequest(about=bio_text))
    except Exception as e:
        print(f"Bio update error: {e}")

# --- BACKGROUND FORWARDING WORKER (CLEAN COPY MODE WITHOUT TAG) ---
async def background_forwarder(application):
    await asyncio.sleep(5)
    while True:
        try:
            import sqlite3
            conn = sqlite3.connect("bot_database.db")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT user_id, slot_number, session_string FROM user_sessions WHERE is_stopped = 0")
            active_sessions = cursor.fetchall()
            conn.close()
            
            for session_row in active_sessions:
                user_id = session_row["user_id"]
                slot_num = session_row["slot_number"]
                session_str = session_row["session_string"]
                
                if user_id != ADMIN_ID and not is_premium(user_id):
                    continue
                
                config = get_bot_config(user_id)
                source_chan_name = config[0]
                interval = config[1] if config[1] else 30
                
                if not source_chan_name:
                    continue
                
                groups = get_user_groups(user_id)
                selected_groups = [g[0] for g in groups if g[2] == 1]
                
                if not selected_groups:
                    continue
                
                try:
                    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
                    await client.connect()
                    
                    if not await client.is_user_authorized():
                        await client.disconnect()
                        continue
                    
                    source_entity = None
                    channels = get_user_channels(user_id)
                    target_channel_id = None
                    for cid, cname in channels:
                        if cname.strip().lower() == source_chan_name.strip().lower():
                            target_channel_id = cid
                            break
                    
                    if target_channel_id:
                        try:
                            source_entity = await client.get_entity(int(target_channel_id))
                        except Exception:
                            pass
                    
                    if not source_entity:
                        async for dialog in client.iter_dialogs(limit=100):
                            if dialog.title.strip().lower() == source_chan_name.strip().lower() or str(dialog.id) == str(source_chan_name):
                                source_entity = dialog.entity
                                break
                    
                    if source_entity:
                        messages = await client.get_messages(source_entity, limit=1)
                        if messages:
                            latest_msg = messages[0]
                            for grp_id in selected_groups:
                                try:
                                    if latest_msg.media:
                                        await client.send_file(int(grp_id), latest_msg.media, caption=latest_msg.text)
                                    elif latest_msg.text:
                                        await client.send_message(int(grp_id), latest_msg.text)
                                        
                                    forwarded_counts[user_id] = forwarded_counts.get(user_id, 0) + 1
                                    await asyncio.sleep(2)
                                except Exception as f_err:
                                    print(f"Send error to group {grp_id}: {f_err}")
                    
                    await client.disconnect()
                except Exception as e:
                    print(f"Forwarder client error for user {user_id}: {e}")
                
                await asyncio.sleep(interval)
                
        except Exception as err:
            print(f"Background worker loop error: {err}")
            await asyncio.sleep(10)

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

def check_user_access(user_id):
    if user_id == ADMIN_ID:
        return True
    return is_premium(user_id)

def get_subscription_type_label(user_id):
    if user_id == ADMIN_ID:
        return "Lifetime (Admin) ♾️"
    
    try:
        import sqlite3
        conn = sqlite3.connect("bot_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT plan_type FROM subscriptions WHERE user_id = ? AND expiry_date > ?", (user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            p_type = row[0]
            if p_type == "referral" or p_type == "trial":
                return "Free Referral Trial 🎁"
            elif p_type == "paid":
                return "Paid Premium 💎"
    except Exception:
        pass
    
    return "Paid Premium 💎"

async def get_main_keyboard(user_id):
    active_slot = get_active_slot(user_id)
    slot_info = get_slot_session(user_id, active_slot)
    is_stopped = slot_info[3] if slot_info else 0
    
    keyboard = []
    if slot_info:
        if is_stopped:
            keyboard.append([InlineKeyboardButton(f"🟢 Start Slot {active_slot}", callback_data=f"start_slot_{active_slot}"), InlineKeyboardButton("🚪 Logout", callback_data="logout_acc")])
        else:
            keyboard.append([InlineKeyboardButton(f"🛑 Stop Slot {active_slot}", callback_data=f"stop_slot_{active_slot}"), InlineKeyboardButton("🚪 Logout", callback_data="logout_acc")])
    else:
        keyboard.append([InlineKeyboardButton(f"🔑 Login Slot {active_slot}", callback_data=f"slot_click_{active_slot}")])
        
    keyboard.append([InlineKeyboardButton("📊 Status", callback_data="status"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")])
    keyboard.append([InlineKeyboardButton("💎 Subscription", callback_data="subscription"), InlineKeyboardButton("🎁 Free Trial (Referral)", callback_data="referral_info")])
    keyboard.append([InlineKeyboardButton(f"🔄 Switch Account (Slot {active_slot})", callback_data="switch_acc")])
    keyboard.append([InlineKeyboardButton("✨ Refresh", callback_data="refresh"), InlineKeyboardButton("🛠️ Help Centre", callback_data="help_centre")])
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
    
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref_"):
            try:
                referrer_id = int(arg.split("_")[1])
                if referrer_id != user.id:
                    if check_referral_eligibility(user.id):
                        claim_referral_reward(user.id)
                        try:
                            await context.bot.send_message(
                                chat_id=user.id, 
                                text="🎁 **Badhai ho!** Referral link se join karne par aapko **2 din ka Free Trial** mil gaya hai ab aap bot ko test kar sakte hain!"
                            )
                        except Exception:
                            pass
            except Exception:
                pass

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

    if not check_user_access(user_id):
        text = "❌ **Access Denied!**\nAapka subscription active nahi hai. Sabhi features ko use karne ke liye pehle subscription buy karein."
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Buy Subscription (Contact Admin)", url=f"https://t.me/{ADMIN_CONTACT_USERNAME}")],
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
    sub_type_label = get_subscription_type_label(user_id)
    groups = get_user_groups(user_id)
    sel_groups = sum(1 for g in groups if g[2] == 1)
    msg_count = forwarded_counts.get(user_id, 0)

    status_text = (
        "📊 **AdsNova Pro - Status Dashboard**\n\n"
        f"🆔 User ID: `{user_id}`\n"
        f"📂 Active Account Slot: Slot {active_slot}\n"
        f"🔐 Login Status: {login_status}\n"
        f"🌟 Subscription: Active ✅ ({sub_type_label})\n\n"
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
        await update.message.reply_text(f"✅ User `{t_id}` ko 30 din ka paid subscription mil gaya!", parse_mode="Markdown")
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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if user_id not in user_login_state:
        return
        
    state = user_login_state[user_id]
    step = state.get("step")
    slot_num = state.get("slot_number")
    
    if step == "waiting_phone":
        state["phone"] = text
        state["step"] = "waiting_otp"
        
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        state["client"] = client
        
        try:
            await client.connect()
            sent = await client.send_code_request(text)
            state["phone_code_hash"] = sent.phone_code_hash
            await update.message.reply_text("📩 OTP code aapke Telegram account par bhej diya gaya hai. Kripya OTP yahan enter karein (Jaise: 1 2 3 4 5):")
        except Exception as e:
            user_login_state.pop(user_id, None)
            await update.message.reply_text(f"❌ Error sending OTP: {e}\nDubara login karne ke liye Menu se try karein.")
            
    elif step == "waiting_otp":
        state["otp"] = text.replace(" ", "")
        client = state["client"]
        phone = state["phone"]
        phone_code_hash = state["phone_code_hash"]
        
        try:
            await client.sign_in(phone=phone, code=state["otp"], phone_code_hash=phone_code_hash)
            me = await client.get_me()
            session_str = client.session.save()
            acc_name = f"{me.first_name or ''} {me.last_name or ''}".strip() or me.username or phone
            
            # Auto set bot link in account bio
            await update_account_bio(client)
            
            save_user_session(user_id, slot_num, phone, session_str, acc_name)
            set_active_slot(user_id, slot_num)
            
            try:
                dialogs = await client.get_dialogs(limit=None)
                groups = []
                channels = []
                for d in dialogs:
                    if d.is_channel or d.is_group:
                        entity = d.entity
                        if getattr(entity, 'broadcast', False):
                            channels.append((d.id, d.title))
                        elif getattr(entity, 'megagroup', False) or d.is_group:
                            groups.append((d.id, d.title))
                        else:
                            channels.append((d.id, d.title))
                save_real_groups_and_channels(user_id, groups, channels)
            except Exception:
                pass
                
            await client.disconnect()
            user_login_state.pop(user_id, None)
            
            await update.message.reply_text(f"✅ **Slot {slot_num} Connected Successfully!**\nAccount: {acc_name}\n\n✨ (Aapke bio mein bot ka link automatically set kar diya gaya hai!)", parse_mode="Markdown")
            await start(update, context)
            
        except Exception as e:
            err_str = str(e)
            if "SessionPasswordNeeded" in err_str or "password" in err_str.lower() or "Two-steps verification" in err_str:
                state["step"] = "waiting_password"
                await update.message.reply_text("🔒 Aapke account par 2-Step Verification (Password) laga hua hai. Apna password yahan bhejein:")
            else:
                user_login_state.pop(user_id, None)
                await update.message.reply_text(f"❌ Login Failed: {e}\nDubara koshish karein.")
                
    elif step == "waiting_password":
        client = state["client"]
        password = text
        
        try:
            await client.sign_in(password=password)
            me = await client.get_me()
            session_str = client.session.save()
            acc_name = f"{me.first_name or ''} {me.last_name or ''}".strip() or me.username or state["phone"]
            
            # Auto set bot link in account bio
            await update_account_bio(client)
            
            save_user_session(user_id, slot_num, state["phone"], session_str, acc_name)
            set_active_slot(user_id, slot_num)
            
            try:
                dialogs = await client.get_dialogs(limit=None)
                groups = []
                channels = []
                for d in dialogs:
                    if d.is_channel or d.is_group:
                        entity = d.entity
                        if getattr(entity, 'broadcast', False):
                            channels.append((d.id, d.title))
                        elif getattr(entity, 'megagroup', False) or d.is_group:
                            groups.append((d.id, d.title))
                        else:
                            channels.append((d.id, d.title))
                save_real_groups_and_channels(user_id, groups, channels)
            except Exception:
                pass
                
            await client.disconnect()
            user_login_state.pop(user_id, None)
            
            await update.message.reply_text(f"✅ **Slot {slot_num} Connected Successfully!**\nAccount: {acc_name}\n\n✨ (Aapke bio mein bot ka link automatically set kar diya gaya hai!)", parse_mode="Markdown")
            await start(update, context)
            
        except Exception as e:
            user_login_state.pop(user_id, None)
            await update.message.reply_text(f"❌ Password Error: {e}\nDubara koshish karein.")

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

    if data == "subscription":
        if user_id == ADMIN_ID:
            sub_text = "💎 **Subscription Status & Details** 💎\n\n🌟 Your Subscription: Active ✅\n🏷️ Type: `Lifetime (Admin) ♾️`\n⏳ Expiry Date: `Unlimited`"
        elif is_premium(user_id):
            expiry_str = get_user_expiry(user_id)
            remaining = get_remaining_days(user_id)
            sub_type_label = get_subscription_type_label(user_id)
            sub_text = (
                "💎 **Subscription Status & Details** 💎\n\n"
                f"🌟 Your Subscription: Active ✅\n"
                f"🏷️ Type: `{sub_type_label}`\n"
                f"⏳ Expiry Date: `{expiry_str}`\n"
                f"⏱️ Remaining Time: `{remaining}`"
            )
        else:
            sub_text = (
                "💎 **Subscription Status & Details** 💎\n\n"
                "🌟 Your Subscription: Inactive ❌\n\n"
                "Plan buy karne ke liye niche diye gaye button par click karke Admin ko message karein:"
            )
        
        keyboard = []
        if user_id != ADMIN_ID and not is_premium(user_id):
            keyboard.append([InlineKeyboardButton("🛒 Buy Subscription (Contact Admin)", url=f"https://t.me/{ADMIN_CONTACT_USERNAME}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")])
        await query.edit_message_text(sub_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "referral_info":
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        share_text = f"🎁 Is link se AdsNova Pro Bot ko start karo aur 2 din bilkul free mein bot test karo! 👇\n{ref_link}"
        share_url = f"https://t.me/share/url?url={ref_link}&text={share_text}"
        
        ref_msg = (
            "🎁 **Free Trial & Referral System** 🎁\n\n"
            "Aap apna yeh unique referral link doston ke sath share karein:\n"
            f"`{ref_link}`\n\n"
            "💡 **Note:** Jo bhi is link se bot start karega, use **2 din is bot ko test karne ke liye free trial** milega. Agar pasand aaye toh subscription buy kar sakta hai!"
        )
        keyboard = [
            [InlineKeyboardButton("🚀 Share Link Now", url=share_url)],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
        ]
        await query.edit_message_text(
            ref_msg, 
            parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data == "help_centre":
        help_text = (
            "💡 **AdsNova Pro - Help & Guide** 💡\n\n"
            "1️⃣ **Login / Add Accounts:** Apne multiple Telegram accounts (upto 20 slots) connect karne ke liye iska use karein.\n"
            "2️⃣ **Source Channel Setup:** Jahan se ads/messages forward karne hain, us channel ko select karein.\n"
            "3️⃣ **Auto Forward to Groups:** Jinki groups mein ads bhejni hain, unhe select karein.\n"
            "4️⃣ **Time Interval:** Messages ke beech ka gap (jaise 20s, 30s) set karein.\n\n"
            f"📞 Kisi bhi samasya ya subscription ke liye Admin se sampark karein: @{ADMIN_CONTACT_USERNAME}"
        )
        await query.edit_message_text(
            help_text, 
            parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]])
        )
        return

    if data == "refresh":
        await start(update, context)
        return

    if not check_user_access(user_id):
        text = "❌ **Subscription Required!**\nAapka subscription active nahi hai. Bot ke features use karne ke liye pehle plan buy karein."
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Buy Subscription (Contact Admin)", url=f"https://t.me/{ADMIN_CONTACT_USERNAME}")],
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
        
        text = f"🔄 **Switch Account (Multi-Account Slots)**\n\n📍 Active Slot: {active_slot}\n📊 {filled_slots}/20 slots filled\n\n(🟢 = Connected, 🔴 = Saved, 👉 = Current Active)"
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
        welcome_text = "💎 **AdsNova Pro Bot - Main Menu** 💎\n\n🛑 Slot Stopped Successfully."
        kb = await get_main_keyboard(user_id)
        await query.edit_message_text(welcome_text, parse_mode="Markdown", reply_markup=kb)

    elif data.startswith("start_slot_"):
        slot_num = int(data.split("_")[2])
        set_slot_stopped(user_id, slot_num, 0)
        welcome_text = "💎 **AdsNova Pro Bot - Main Menu** 💎\n\n🟢 Slot Restarted Successfully."
        kb = await get_main_keyboard(user_id)
        await query.edit_message_text(welcome_text, parse_mode="Markdown", reply_markup=kb)

    elif data == "logout_acc":
        active_slot = get_active_slot(user_id)
        remove_user_session(user_id, active_slot)
        welcome_text = f"💎 **AdsNova Pro Bot - Main Menu** 💎\n\n🚪 Slot {active_slot} Logged Out Successfully."
        kb = await get_main_keyboard(user_id)
        await query.edit_message_text(welcome_text, parse_mode="Markdown", reply_markup=kb)

    elif data == "settings":
        keyboard = [
            [InlineKeyboardButton("📢 1 Source Channel Setup", callback_data="opt_1")],
            [InlineKeyboardButton("👥 2 Auto Forward to Groups", callback_data="opt_2")],
            [InlineKeyboardButton("⏱️ 3 Time Interval Settings", callback_data="opt_3")],
            [InlineKeyboardButton("💬 4 Auto-Reply Share Message", callback_data="opt_4")],
            [InlineKeyboardButton("🔄 Refresh Channels List", callback_data="refresh_channels")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
        ]
        await query.edit_message_text("⚙️ **AdsNova Settings Menu**\n\nAap apni zaroorat ke mutabiq option chun sakte hain:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "refresh_channels":
        active_slot = get_active_slot(user_id)
        slot_data = get_slot_session(user_id, active_slot)
        if not slot_data:
            await query.answer("❌ Pehle account login karein!", show_alert=True)
            return
        
        phone, session_str, _, _ = slot_data
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        
        try:
            await client.connect()
            if await client.is_user_authorized():
                dialogs = await client.get_dialogs(limit=None)
                groups = []
                channels = []
                for d in dialogs:
                    if d.is_channel or d.is_group:
                        entity = d.entity
                        if getattr(entity, 'broadcast', False):
                            channels.append((d.id, d.title))
                        elif getattr(entity, 'megagroup', False) or d.is_group:
                            groups.append((d.id, d.title))
                        else:
                            channels.append((d.id, d.title))
                save_real_groups_and_channels(user_id, groups, channels)
                await client.disconnect()
                await query.answer("✅ Saare channels successfully refresh ho gaye hain!", show_alert=True)
            else:
                await client.disconnect()
                await query.answer("❌ Session expired! Dubara login karein.", show_alert=True)
        except Exception as e:
            await query.answer(f"❌ Error: {e}", show_alert=True)
        
        keyboard = [
            [InlineKeyboardButton("📢 1 Source Channel Setup", callback_data="opt_1")],
            [InlineKeyboardButton("👥 2 Auto Forward to Groups", callback_data="opt_2")],
            [InlineKeyboardButton("⏱️ 3 Time Interval Settings", callback_data="opt_3")],
            [InlineKeyboardButton("💬 4 Auto-Reply Share Message", callback_data="opt_4")],
            [InlineKeyboardButton("🔄 Refresh Channels List", callback_data="refresh_channels")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
        ]
        await query.edit_message_text("⚙️ **AdsNova Settings Menu**\n\nChannels successfully refreshed!", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "opt_1" or data.startswith("set_chan_sel_"):
        channels = get_user_channels(user_id)
        if not channels:
            await query.edit_message_text("❌ Aapke account mein koi channel nahi mila! Settings mein jakar 'Refresh Channels List' par click karein.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]))
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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    async def post_init(app):
        asyncio.create_task(background_forwarder(app))
        
    application.post_init = post_init

    print("AdsNova Pro Bot is running successfully...")
    application.run_polling()

if __name__ == "__main__":
    main()
