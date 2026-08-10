import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from database import (init_db, save_user, is_premium, get_user_expiry, get_bot_config, 
                      set_source_channel, set_time_interval, add_subscription_by_id, 
                      remove_subscription_by_id, get_all_premium_users, get_user_groups, 
                      toggle_group_selection, set_all_groups_selection, get_user_channels)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
BOT_TOKEN = "8999765663:AAHOS2-3WUrXjDYQIE_5NQhe1e7SHFTyGY"

ADMIN_IDS = [8453975447]

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

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Aapke paas Admin access nahi hai!")
        return

    prem_users = get_all_premium_users()
    admin_text = (
        f"👑 **Admin Panel**\n\n"
        f"• Total Active Premium Users: `{len(prem_users)}`\n\n"
        "Commands:\n"
        "👉 `/add <user_id>` - Premium dene ke liye\n"
        "👉 `/remove <user_id>` - Premium hatane ke liye\n"
        "👉 `/listpremium` - Sabhi premium users ki list dekhne ke liye"
    )
    await update.message.reply_text(admin_text, parse_mode="Markdown")

async def list_premium_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Aapke paas Admin access nahi hai!")
        return

    prem_users = get_all_premium_users()
    if not prem_users:
        await update.message.reply_text("ℹ️ Filhal koi bhi active premium user nahi hai.")
        return

    text = "💎 **Active Premium Users List:**\n\n"
    for uid, uname, expiry in prem_users:
        text += f"• ID: `{uid}` | Username: @{uname or 'None'} | Expiry: {expiry}\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def add_prem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Aapke paas Admin access nahi hai!")
        return

    if context.args:
        try:
            target_id = int(context.args[0])
            add_subscription_by_id(target_id, days=30)
            await update.message.reply_text(f"✅ Success! User `{target_id}` ko 30 Dino ke liye **Premium Subscription** de di gayi hai.", parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("❌ Galat User ID! Kripya sahi number dalein.")
    else:
        await update.message.reply_text("⚠️ Istamal karne ka tarika: `/add <user_id>`", parse_mode="Markdown")

async def remove_prem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Aapke paas Admin access nahi hai!")
        return

    if context.args:
        try:
            target_id = int(context.args[0])
            remove_subscription_by_id(target_id)
            await update.message.reply_text(f"⚠️ User `{target_id}` ki **Premium Subscription** hata di gayi hai.", parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("❌ Galat User ID!")
    else:
        await update.message.reply_text("⚠️ Istamal karne ka tarika: `/remove <user_id>`", parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "settings":
        keyboard = [
            [InlineKeyboardButton("1️⃣ Source Channel Setup", callback_data="opt_1")],
            [InlineKeyboardButton("2️⃣ Auto Forward to Groups", callback_data="opt_2")],
            [InlineKeyboardButton("3️⃣ Time Interval Settings", callback_data="opt_3")],
            [InlineKeyboardButton("5️⃣ Auto-Reply Share Message", callback_data="opt_5")],
            [InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]
        ]
        await query.edit_message_text("⚙️ **Settings Menu**\n\nAap apni zaroorat ke mutabiq option chun sakte hain:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "main_menu":
        keyboard = [
            [InlineKeyboardButton("🔑 Login / Add Accounts", callback_data="login_acc")],
            [InlineKeyboardButton("📊 Status", callback_data="status"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
            [InlineKeyboardButton("💎 Subscription", callback_data="subscription"), InlineKeyboardButton("❓ Help", callback_data="help")],
            [InlineKeyboardButton("🔄 Switch Account", callback_data="switch_acc"), InlineKeyboardButton("🔄 Refresh", callback_data="refresh")]
        ]
        await query.edit_message_text("🏠 **Main Dashboard**\n\nNeeche se koi option select karein.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "opt_1" or data.startswith("set_chan_sel_"):
        channels = get_user_channels(user_id)
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
            sub_text = f"💎 **Your Premium Subscription**\n\nStatus: **Active ✅**\nExpiry Date: **{expiry}**\n\nAapke paas sabhi features unlocked hain!"
        else:
            sub_text = "💎 **Premium Subscription**\n\nUnlock unlimited features!\nTo buy subscription, contact admin here: **@AdsNova0**"
        
        await query.edit_message_text(sub_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]), parse_mode="Markdown")

    elif data == "help":
        await query.edit_message_text("❓ **Help & Guide**\n\nAapko support @AdsNova0 par milegi.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]), parse_mode="Markdown")

    elif data in ["login_acc", "switch_acc", "refresh"]:
        await query.edit_message_text("🔄 Process executed successfully!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]), parse_mode="Markdown")

def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("listpremium", list_premium_cmd))
    app.add_handler(CommandHandler("add", add_prem_cmd))
    app.add_handler(CommandHandler("remove", remove_prem_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot is running successfully...")
    app.run_polling()

if __name__ == "__main__":
    main()
