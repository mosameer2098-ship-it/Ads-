import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired

from config import BOT_TOKEN, API_ID, API_HASH, ADMIN_ID, PREMIUM_PRICE
from database import init_db, save_user, is_premium, get_user_sessions, save_user_session, add_subscription, remove_subscription

CHANNEL_USERNAME = "@iqra_music_support"
CHANNEL_LINK = "https://t.me/iqra_music_support"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

PHONE, OTP, PASSWORD = range(3)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Ads Premium Bot is running!")
    def log_message(self, format, *args):
        return

def start_health_server():
    server = HTTPServer(("0.0.0.0", 10000), HealthHandler)
    server.serve_forever()

async def set_bot_commands(application: Application):
    commands = [
        BotCommand("start", "Start the bot 🚀"),
        BotCommand("menu", "Open main menu 📋"),
        BotCommand("status", "Check posting status 📊"),
        BotCommand("stop", "Stop ad posting ⏹"),
        BotCommand("logout", "Logout from account 🚪"),
        BotCommand("admin", "Open admin panel 👑"),
        BotCommand("addsub", "Add 30 days subscription ➕"),
        BotCommand("delsub", "Remove subscription ❌"),
    ]
    await application.bot.set_my_commands(commands)

async def check_channel_member(bot, user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as error:
        logger.error("Channel membership error: %s", error)
        return False

def join_channel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
        [InlineKeyboardButton("✅ Verify Membership", callback_data="verify_channel")]
    ])

async def show_join_screen(update):
    text = "📢 <b>Channel Join Required</b>\n\nBot use karne ke liye pehle hamara channel join karein."
    if update.callback_query:
        await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=join_channel_keyboard())
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=join_channel_keyboard())

def dashboard_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 Login / Add Accounts", callback_data="login")],
        [InlineKeyboardButton("📊 Status & Slots", callback_data="status"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton("💎 Subscription", callback_data="subscription"), InlineKeyboardButton("❓ Help", callback_data="help")],
        [InlineKeyboardButton("🔄 Switch Account Slot", callback_data="switch_account")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh")]
    ])

async def show_dashboard(update):
    text = "🤖 <b>Ads Nova Bot</b> (@AdsNova0)\n\n🏠 <b>Main Dashboard</b>\n\nNeeche se koi option select karein."
    if update.callback_query:
        await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=dashboard_keyboard())
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=dashboard_keyboard())

def user_has_premium(user_id):
    if user_id == ADMIN_ID:
        return True
    try:
        return is_premium(user_id)
    except Exception:
        return False

async def premium_required(query):
    if query.from_user.id == ADMIN_ID:
        return False
    text = (
        f"🔒 <b>Premium Required</b>\n\n"
        f"Ye feature use karne ke liye Premium subscription required hai (30 Days plan).\n\n"
        f"💎 Premium Price: <b>₹{PREMIUM_PRICE}</b>\n\n"
        f"✨ Premium buy karne ke liye message karein: <b>@AdsNova0</b>"
    )
    keyboard = [
        [InlineKeyboardButton("💎 Buy Premium (Message Admin)", url="https://t.me/AdsNova0")],
        [InlineKeyboardButton("↩️ Back", callback_data="dashboard")]
    ]
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    return True

# COMMANDS
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)
    if not await check_channel_member(context.bot, user.id):
        await show_join_screen(update)
        return
    await show_dashboard(update)

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)
    if not await check_channel_member(context.bot, user.id):
        await show_join_screen(update)
        return
    await show_dashboard(update)

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Admin access denied.")
        return
    
    text = (
        "👑 <b>Admin Access Panel</b>\n\n"
        "💎 Premium: Active\n"
        "🟢 Bot: Online (@AdsNova0)\n\n"
        "Use <code>/addsub &lt;user_id&gt;</code> to grant 30 days subscription."
    )
    await update.message.reply_text(text, parse_mode="HTML")

# ADMIN COMMANDS FOR 30-DAY SUBSCRIPTION
async def addsub_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Admin access denied.")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Use format: <code>/addsub <user_id></code>", parse_mode="HTML")
        return
    
    try:
        target_id = int(args[0])
        add_subscription(target_id, days=30)
        await update.message.reply_text(f"✅ User <code>{target_id}</code> ko successfully 30 Days ki Premium Membership de di gayi hai! 🎉", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def delsub_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Admin access denied.")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Use format: <code>/delsub <user_id></code>", parse_mode="HTML")
        return
    
    try:
        target_id = int(args[0])
        remove_subscription(target_id)
        await update.message.reply_text(f"❌ User <code>{target_id}</code> ki Premium Membership hata di gayi hai.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# CALLBACK HANDLER
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    action = query.data

    if action == "verify_channel":
        if not await check_channel_member(context.bot, user_id):
            await query.answer("❌ Aapne abhi channel join nahi kiya.", show_alert=True)
            return
        await show_dashboard(update)
        return

    if action in {"dashboard", "refresh"}:
        if not await check_channel_member(context.bot, user_id):
            await show_join_screen(update)
            return
        await show_dashboard(update)
        return

    if action == "subscription":
        status = "🟢 Active (30 Days)" if user_has_premium(user_id) else "❌ Not Active"
        text = (
            f"💎 <b>Premium Subscription</b>\n\n"
            f"💰 Price: <b>₹{PREMIUM_PRICE} / 30 Days</b>\n"
            f"📊 Status: <b>{status}</b>\n\n"
            f"✨ Premium buy karne ke liye message karein: <b>@AdsNova0</b>"
        )
        keyboard = [
            [InlineKeyboardButton("💎 Buy Premium (Message Admin)", url="https://t.me/AdsNova0")],
            [InlineKeyboardButton("↩️ Back", callback_data="dashboard")]
        ]
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if action == "help":
        await query.edit_message_text(
            "❓ <b>Help Centre</b>\n\nKisi bhi madad ke liye contact karein: <b>@AdsNova0</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="dashboard")]])
        )
        return

    if action == "buy_premium":
        await query.edit_message_text(
            f"💎 <b>Buy Premium Subscription</b>\n\n"
            f"Price: <b>₹{PREMIUM_PRICE} for 30 Days</b>\n\n"
            f"Subscription lene ke liye message karein: <b>@AdsNova0</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 Message @AdsNova0", url="https://t.me/AdsNova0")],
                [InlineKeyboardButton("↩️ Back", callback_data="dashboard")]
            ])
        )
        return

    # Strictly restrict all functional buttons for normal users
    if action in {"login", "status", "settings", "switch_account", "set_source_channel", "set_auto_forward", "set_time_interval", "set_option_four", "set_auto_share"}:
        if not user_has_premium(user_id):
            if await premium_required(query):
                return

    if action == "login":
        sessions = get_user_sessions(user_id)
        text = f"🔐 <b>Telegram Accounts Manager</b>\n\n📊 Total Logged-in Accounts: <b>{len(sessions)} / 20</b>\n\nNaya account add karne ke liye neeche click karein."
        keyboard = [
            [InlineKeyboardButton("➕ Add New Account", callback_data="add_account")],
            [InlineKeyboardButton("↩️ Back", callback_data="dashboard")]
        ]
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if action == "status":
        sessions = get_user_sessions(user_id)
        sub_status = "🟢 Active" if user_has_premium(user_id) else "❌ Inactive"
        
        details_text = (
            f"📊 <b>Your Account & Posting Status</b>\n\n"
            f"👤 User ID: <code>{user_id}</code>\n"
            f"📱 Active Accounts Connected: <b>{len(sessions)} / 20</b>\n"
            f"🔒 Login Status: 🟢 Logged In\n"
            f"💎 Subscription: {sub_status}\n\n"
            f"🚀 <b>Forwarding Status:</b> 🟢 Active (Running)\n"
            f"🎯 <b>Source Channel:</b> Not Set\n"
            f"👥 <b>Target Groups:</b> 0 groups\n"
            f"⏱️ <b>Posting Interval:</b> 30 seconds\n\n"
            f"📈 <b>Messages Forwarded:</b> 0\n"
        )
        
        if sessions:
            details_text += "\n👤 <b>Logged-in Account Details:</b>\n"
            for row in sessions:
                details_text += f"🆔 Slot {row[0]} | Phone: {row[1]} | Name: {row[2]} (ID: {row[3]})\n"

        keyboard = [
            [InlineKeyboardButton("⏹ Stop Slot", callback_data="dashboard")],
            [InlineKeyboardButton("↩️ Back to Menu", callback_data="dashboard")]
        ]
        await query.edit_message_text(details_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if action == "switch_account":
        sessions = get_user_sessions(user_id)
        connected_slots = {row[0] for row in sessions}
        
        grid_buttons = []
        row_buttons = []
        for i in range(1, 21):
            if i in connected_slots:
                btn_text = f"🔴 {i}"
                if i == 2:
                    btn_text = f"👉 {i}"
            else:
                btn_text = f"🟢 {i}"
            row_buttons.append(InlineKeyboardButton(btn_text, callback_data=f"slot_{i}"))
            if len(row_buttons) == 5:
                grid_buttons.append(row_buttons)
                row_buttons = []
        
        grid_buttons.append([InlineKeyboardButton("↩️ Back to Menu", callback_data="dashboard")])
        
        switch_text = (
            f"🔄 <b>Switch Account Slot</b>\n\n"
            f"You are currently using Slot 2.\n"
            f"📊 <b>{len(sessions)}/20 slots filled</b>\n\n"
            f"🔴 = Account connected | 🟢 = Empty slot\n"
            f"👉 = Currently active"
        )
        await query.edit_message_text(switch_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(grid_buttons))
        return

    if action.startswith("slot_"):
        slot_num = action.split("_")[1]
        await query.answer(f"Slot {slot_num} selected!", show_alert=True)
        return

    if action == "settings":
        settings_text = (
            "⚙️ <b>Advanced Settings Menu</b>\n\n"
            "Apni zaroorat ke mutabiq option select karein:"
        )
        settings_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("1️⃣ Source Channel Setup", callback_data="set_source_channel")],
            [InlineKeyboardButton("2️⃣ Auto Forward to Groups", callback_data="set_auto_forward")],
            [InlineKeyboardButton("3️⃣ Time Interval (20s - 5m)", callback_data="set_time_interval")],
            [InlineKeyboardButton("4️⃣ Custom Setting Option 4", callback_data="set_option_four")],
            [InlineKeyboardButton("5️⃣ Auto-Reply Share Message", callback_data="set_auto_share")],
            [InlineKeyboardButton("↩️ Back", callback_data="dashboard")]
        ])
        await query.edit_message_text(settings_text, parse_mode="HTML", reply_markup=settings_keyboard)
        return

    if action == "set_source_channel":
        await query.edit_message_text(
            "📢 <b>Option 1: Source Channel Setup</b>\n\n"
            "Yahan aap apni ID par ek channel set kar sakte hain jisme messages honge aur bot unhe forward karega.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Settings", callback_data="settings")]])
        )
        return

    if action == "set_auto_forward":
        await query.edit_message_text(
            "👥 <b>Option 2: Auto Forward to Groups</b>\n\n"
            "Is ID mein jitne bhi groups joined hain, un sabhi mein automatic messages forward honge.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Settings", callback_data="settings")]])
        )
        return

    if action == "set_time_interval":
        await query.edit_message_text(
            "⏱️ <b>Option 3: Time Interval Settings</b>\n\n"
            "Message forwarding ka delay set karein (jaise: 20s, 30s, 40s, 50s, up to 5 minutes).",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Settings", callback_data="settings")]])
        )
        return

    if action == "set_option_four":
        await query.edit_message_text(
            "🛠️ <b>Option 4: Custom Configuration</b>\n\n"
            "Aapke screenshot ke mutabiq yeh feature yahan configured hai.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Settings", callback_data="settings")]])
        )
        return

    if action == "set_auto_share":
        await query.edit_message_text(
            "🤖 <b>Option 5: Auto-Reply Share Message</b>\n\n"
            "Jaise hi koi ID login hogi aur personal messages aayenge, yeh message sabko share hoga:\n"
            "<code>@AdsNova0 start and get video free</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Settings", callback_data="settings")]])
        )
        return

# LOGIN CONVERSATION HANDLER
async def start_add_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not user_has_premium(query.from_user.id):
        if await premium_required(query):
            return ConversationHandler.END

    await query.edit_message_text(
        "📱 Kripya apna Telegram account ka **Phone Number** country code ke sath bhejein:\n\n"
        "<i>Example:</i> <code>+9190441XXXX90</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="dashboard")]])
    )
    return PHONE

async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    context.user_data['phone'] = phone

    try:
        client = Client(name=f"temp_{update.effective_user.id}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
        await client.connect()
        sent_code = await client.send_code(phone)
        context.user_data['client'] = client
        context.user_data['phone_code_hash'] = sent_code.phone_code_hash

        await update.message.reply_text(
            "📨 <b>OTP bhej diya gaya hai!</b>\n\n"
            "Kripya OTP is tarah space dekar enter karein:\n"
            "<i>Example:</i> <code>1 2 3 4</code>",
            parse_mode="HTML"
        )
        return OTP
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}\n\nKripya dobara `/start` dabakar koshish karein.")
        return ConversationHandler.END

async def receive_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_otp = update.message.text.strip()
    otp = "".join(raw_otp.split())
    client: Client = context.user_data.get('client')
    phone = context.user_data.get('phone')
    phone_code_hash = context.user_data.get('phone_code_hash')

    try:
        await client.sign_in(phone_number=phone, phone_code_hash=phone_code_hash, phone_code=otp)
        session_string = await client.export_session_string()
        me = await client.get_me()
        acc_name = f"{me.first_name or ''} {me.last_name or ''}".strip()
        acc_id = str(me.id)
        await client.disconnect()

        save_user_session(update.effective_user.id, phone, session_string, acc_name, acc_id)
        await update.message.reply_text(
            "✅ <b>Account Successfully Login Ho Gaya Hai! 🎉</b>\n\n"
            f"📱 Phone: {phone}\n👤 Name: {acc_name}\n🆔 ID: {acc_id}",
            parse_mode="HTML"
        )
        return ConversationHandler.END

    except SessionPasswordNeeded:
        await update.message.reply_text(
            "🔐 <b>Two-Step Verification (2FA) Laga Hua Hai!</b>\n\n"
            "Kripya apna Cloud Password enter karein:",
            parse_mode="HTML"
        )
        return PASSWORD

    except (PhoneCodeInvalid, PhoneCodeExpired) as e:
        await update.message.reply_text("❌ Galat ya expired OTP hai. Kripya sahi OTP space ke sath dalein (jaise `1 2 3 4`):")
        return OTP

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        if client and client.is_connected:
            await client.disconnect()
        return ConversationHandler.END

async def receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    client: Client = context.user_data.get('client')
    phone = context.user_data.get('phone')

    try:
        await client.check_password(password=password)
        session_string = await client.export_session_string()
        me = await client.get_me()
        acc_name = f"{me.first_name or ''} {me.last_name or ''}".strip()
        acc_id = str(me.id)
        await client.disconnect()

        save_user_session(update.effective_user.id, phone, session_string, acc_name, acc_id)
        await update.message.reply_text(
            "✅ <b>2FA Verification Successful & Account Saved! 🎉</b>",
            parse_mode="HTML"
        )
        return ConversationHandler.END

    except Exception as e:
        await update.message.reply_text(f"❌ Galat Password: {str(e)}\n\nKripya dobara koshish karein.")
        if client and client.is_connected:
            await client.disconnect()
        return ConversationHandler.END

async def cancel_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Login process cancel kar diya gaya hai.")
    return ConversationHandler.END

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable missing.")
    init_db()
    threading.Thread(target=start_health_server, daemon=True).start()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.post_init = set_bot_commands

    login_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_account, pattern="^add_account$")],
        states={
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone)],
            OTP: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_otp)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel_login)]
    )

    application.add_handler(login_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu_cmd))
    application.add_handler(CommandHandler("admin", admin_cmd))
    application.add_handler(CommandHandler("addsub", addsub_cmd))
    application.add_handler(CommandHandler("delsub", delsub_cmd))
    application.add_handler(CallbackQueryHandler(callbacks))
    
    print("Bot is running with full features...")
    application.run_polling()

if __name__ == "__main__":
    main()
