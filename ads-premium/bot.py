import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from database import init_db, save_user, is_premium, get_bot_config, set_source_channel, set_time_interval

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = "8999765663:AAHOS2-3WUrXjDYQIE_5NQhe1e7SHFTyGY" # Aapka token

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)
    
    keyboard = [
        [InlineKeyboardButton("🔑 Login / Add Accounts", callback_data="login_acc")],
        [InlineKeyboardButton("📊 Status", callback_data="status"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton("💎 Subscription", callback_data="subscription"), InlineKeyboardButton("❓ Help", callback_data="help")],
        [InlineKeyboardButton("🔄 Switch Account", callback_data="switch_acc"), InlineKeyboardButton("🔄 Refresh", callback_data="refresh")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🏠 **Main Dashboard**\n\nNeeeche se koi option select karein.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

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
        # Option 1: Channel selection list simulation / fetch
        keyboard = [
            [InlineKeyboardButton("📢 @MySampleChannel1", callback_data="set_chan_1")],
            [InlineKeyboardButton("📢 @OfficialUpdatesChannel", callback_data="set_chan_2")],
            [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]
        ]
        await query.edit_message_text("📢 **Option 1: Source Channel Setup**\n\nAapke account ke yeh channels mile hain. Ek select karein:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("set_chan_"):
        set_source_channel(user_id, "Selected Channel")
        await query.edit_message_text("✅ **Source Channel Successfully Set ho gaya hai!**\nAb is channel ke messages aage forward honge.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]), parse_mode="Markdown")

    elif data == "opt_2":
        # Option 2: Groups list with tick marks and Select All
        keyboard = [
            [InlineKeyboardButton("☑️ Group A", callback_data="grp_toggle_1"), InlineKeyboardButton("✅ Group B", callback_data="grp_toggle_2")],
            [InlineKeyboardButton("☑️ Group C", callback_data="grp_toggle_3"), InlineKeyboardButton("☑️ Group D", callback_data="grp_toggle_4")],
            [InlineKeyboardButton("🟢 Select All", callback_data="grp_select_all")],
            [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]
        ]
        await query.edit_message_text("👥 **Option 2: Auto Forward to Groups**\n\nJin groups mein message forward karna hai unhein select karein:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "grp_select_all":
        keyboard = [
            [InlineKeyboardButton("✅ Group A", callback_data="grp_toggle_1"), InlineKeyboardButton("✅ Group B", callback_data="grp_toggle_2")],
            [InlineKeyboardButton("✅ Group C", callback_data="grp_toggle_3"), InlineKeyboardButton("✅ Group D", callback_data="grp_toggle_4")],
            [InlineKeyboardButton("🟢 Selected All", callback_data="grp_select_all")],
            [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]
        ]
        await query.edit_message_text("👥 **Option 2: Auto Forward to Groups**\n\nSabhi groups select ho chuke hain ✅", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "opt_3":
        # Option 3: Time intervals
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
        await query.edit_message_text(f"✅ **Time Interval Successfully Set to {t_val}s!**\nYeh ab Status menu mein bhi dikhega.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]), parse_mode="Markdown")

    elif data == "opt_5":
        # Option 5: Auto-Reply Share Message with @Iqraxmusic_bot
        msg_text = "✨ @Iqraxmusic_bot start and get video free"
        await query.edit_message_text(f"🤖 **Option 5: Auto-Reply Share Message**\n\nYeh message sabhi incoming personal chats par auto-share hoga:\n\n`{msg_text}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")]]), parse_mode="Markdown")

    elif data == "status":
        config = get_bot_config(user_id)
        chan = config[0] if config and config[0] else "Not Set"
        t_int = config[2] if config else 30
        status_text = (
            f"📊 **Bot Status Dashboard**\n\n"
            f"• Source Channel: {chan}\n"
            f"• Time Interval Selected: {t_int}s\n"
            f"• Premium Status: {'Active 💎' if is_premium(user_id) else 'Free Plan ❌'}"
        )
        await query.edit_message_text(status_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]), parse_mode="Markdown")

    elif data == "subscription":
        sub_text = (
            "💎 **Premium Subscription**\n\n"
            "Unlock unlimited features and high-speed processing!\n"
            "To buy subscription, contact admin here: **@AdsNova0**"
        )
        await query.edit_message_text(sub_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]), parse_mode="Markdown")

    elif data == "help":
        await query.edit_message_text("❓ **Help & Guide**\n\nAapko kisi bhi samasya ke liye support @AdsNova0 par milegi.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]), parse_mode="Markdown")

    elif data == "login_acc":
        await query.edit_message_text("🔑 **Login / Add Accounts**\n\nAap apna phone number yahan connect kar sakte hain.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]), parse_mode="Markdown")

    elif data == "switch_acc":
        await query.edit_message_text("🔄 **Switch Account**\n\nApne logged-in accounts ke beech switch karein.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]), parse_mode="Markdown")

    elif data == "refresh":
        await query.edit_message_text("🔄 Dashboard refreshed successfully!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]), parse_mode="Markdown")

def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot is running successfully...")
    app.run_polling()

if __name__ == "__main__":
    main()
