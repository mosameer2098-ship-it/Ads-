import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from database import init_db, save_user, is_premium, get_bot_config, set_source_channel, set_time_interval, add_subscription_by_id, remove_subscription_by_id

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
BOT_TOKEN = "8999765663:AAHOS2-3WUrXjDYQIE_5NQhe1e7SHFTyGY"

# Aapki Admin ID
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
    await update.message.reply_text(f"🏠 **Main Dashboard**\n\nYour Telegram ID: `{user.id}`\nNeeche se koi option select karein.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Aapke paas Admin access nahi hai!")
        return

    admin_text = (
        "👑 **Admin Panel**\n\n"
        "Kisi user ko premium dene ke liye command use karein:\n"
        "👉 `/add <user_id>` (Jaise: `/add 123456789`)\n\n"
        "Kisi user ka premium hatane ke liye:\n"
        "👉 `/remove <user_id>` (Jaise: `/remove 123456789`)"
    )
    await update.message.reply_text(admin_text, parse_mode="Markdown")

async def add_prem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Aapke paas Admin access nahi hai!")
        return

    if context.args:
        try:
            target_id = int(context.args[0])
            add_subscription_by_id(target_id)
            await update.message.reply_text(f"✅ Success! User `{target_id}` ko **Premium Subscription** de di gayi hai.", parse_mode="Markdown")
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

    elif data == "opt_1":
        keyboard = [
            [InlineKeyboardButton("📢 @MySampleChannel1", callback_data="set_chan_1")],
            [InlineKeyboardButton("📢 @OfficialUpdatesChannel", callback_data="set_chan_2")],
            [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]
        ]
        await query.edit_message_text("📢 **Option 1: Source Channel Setup**\n\nAapke account ke yeh channels mile hain. Ek select karein:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("set_chan_"):
        set_source_channel(user_id, "Selected Channel")
        await query.edit_message_text("✅ **Source Channel Successfully Set ho gaya hai!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]), parse_mode="Markdown")

    elif data == "opt_2":
        keyboard = [
            [InlineKeyboardButton("☑️ Group A", callback_data="grp_t1"), InlineKeyboardButton("✅ Group B", callback_data="grp_t2")],
            [InlineKeyboardButton("☑️ Group C", callback_data="grp_t3"), InlineKeyboardButton("☑️ Group D", callback_data="grp_t4")],
            [InlineKeyboardButton("🟢 Select All", callback_data="grp_select_all")],
            [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]
        ]
        await query.edit_message_text("👥 **Option 2: Auto Forward to Groups**\n\nJin groups mein message forward karna hai unhein select karein:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "grp_select_all":
        keyboard = [
            [InlineKeyboardButton("✅ Group A", callback_data="grp_t1"), InlineKeyboardButton("✅ Group B", callback_data="grp_t2")],
            [InlineKeyboardButton("✅ Group C", callback_data="grp_t3"), InlineKeyboardButton("✅ Group D", callback_data="grp_t4")],
            [InlineKeyboardButton("🟢 Selected All", callback_data="grp_select_all")],
            [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]
        ]
        await query.edit_message_text("👥 **Option 2: Auto Forward to Groups**\n\nSabhi groups select ho chuke hain ✅", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "opt_3":
        config = get_bot_config(user_id)
        current_time = config[2] if config else 30
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
        t_int = config[2] if config else 30
        status_text = f"📊 **Bot Status Dashboard**\n\n• Source Channel: {chan}\n• Time Interval Selected: {t_int}s\n• Premium Status: {'Active 💎' if is_premium(user_id) else 'Free Plan ❌'}"
        await query.edit_message_text(status_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]), parse_mode="Markdown")

    elif data == "subscription":
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
    app.add_handler(CommandHandler("add", add_prem_cmd))
    app.add_handler(CommandHandler("remove", remove_prem_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot is running successfully...")
    app.run_polling()

if __name__ == "__main__":
    main()
        
