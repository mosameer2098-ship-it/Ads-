from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from database import (
    get_active_slot,
    get_slot_session,
)


async def get_main_keyboard(user_id, user_languages):

    active_slot = get_active_slot(user_id)

    slot_info = get_slot_session(
        user_id,
        active_slot
    )

    is_stopped = (
        slot_info[3]
        if slot_info
        else 0
    )

    lang = user_languages.get(
        user_id,
        "hi"
    )

    keyboard = []

    # ========================================================
    # ACCOUNT / SLOT BUTTON
    # ========================================================

    if slot_info:

        if is_stopped:

            btn_text = (
                f"🟢 Start Slot {active_slot}"
                if lang == "en"
                else f"🟢 Slot {active_slot} Shuru Karein"
            )

            keyboard.append([
                InlineKeyboardButton(
                    btn_text,
                    callback_data=f"start_slot_{active_slot}"
                ),
                InlineKeyboardButton(
                    "🚪 Logout",
                    callback_data="logout_acc"
                )
            ])

        else:

            btn_text = (
                f"🛑 Stop Slot {active_slot}"
                if lang == "en"
                else f"🛑 Slot {active_slot} Rokein"
            )

            keyboard.append([
                InlineKeyboardButton(
                    btn_text,
                    callback_data=f"stop_slot_{active_slot}"
                ),
                InlineKeyboardButton(
                    "🚪 Logout",
                    callback_data="logout_acc"
                )
            ])

    else:

        btn_text = (
            f"🔑 Login Slot {active_slot}"
            if lang == "en"
            else f"🔑 Slot {active_slot} Login Karein"
        )

        keyboard.append([
            InlineKeyboardButton(
                btn_text,
                callback_data=f"slot_click_{active_slot}"
            )
        ])

    # ========================================================
    # STATUS + SETTINGS
    # ========================================================

    keyboard.append([
        InlineKeyboardButton(
            "📊 Live Analytics Status",
            callback_data="status"
        ),
        InlineKeyboardButton(
            "⚙️ Settings",
            callback_data="settings"
        )
    ])

    # ========================================================
    # SUBSCRIPTION
    # ========================================================

    keyboard.append([
        InlineKeyboardButton(
            "💎 Subscription Details",
            callback_data="subscription"
        )
    ])

    # ========================================================
    # REFERRAL
    # ========================================================

    keyboard.append([
        InlineKeyboardButton(
            "🎁 Free Trial (Referral)",
            callback_data="referral_info"
        )
    ])

    # ========================================================
    # LANGUAGE
    # ========================================================

    keyboard.append([
        InlineKeyboardButton(
            f"🌐 Language: "
            f"{'English' if lang == 'en' else 'Hinglish'}",
            callback_data="toggle_lang"
        )
    ])

    # ========================================================
    # REFRESH + HELP
    # ========================================================

    keyboard.append([
        InlineKeyboardButton(
            "✨ Refresh",
            callback_data="refresh"
        ),
        InlineKeyboardButton(
            "🛠️ Help Centre",
            callback_data="help_centre"
        )
    ])

    return InlineKeyboardMarkup(keyboard)
