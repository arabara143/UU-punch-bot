from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from datetime import datetime, timedelta, timezone

# ===== CONFIG =====
import os
TOKEN = os.getenv("8109447299:AAHTsy_nlNQcUZg8QEfn2FwvKyUiISFwKfQ")

ADMIN_CHAT_ID = 7582293874  # <-- replace with your numeric chat_id
WASHROOM_LIMIT = timedelta(minutes=10)
FOOD_LIMIT = timedelta(minutes=30)
UTC_PLUS_7 = timezone(timedelta(hours=7))
LATE_CHECKIN_HOUR = 16  # 16:00 UTC+7

# ===== STORAGE =====
activity_start = {}  # user_id -> (start_time, activity_type)
user_checkin = {}    # user_id -> True if checked-in

# ===== KEYBOARD =====
def get_keyboard(user_id=None):
    keyboard = [
        [KeyboardButton("Check-In")],
        [KeyboardButton("Check-Out")],
        [KeyboardButton("Food")],
        [KeyboardButton("Washroom")],
        [KeyboardButton("Others")]
    ]

    if user_id in activity_start:
        start_time, activity_type = activity_start[user_id]
        now = datetime.now(UTC_PLUS_7)

        # Determine remaining time
        limit = None
        if activity_type == "Washroom":
            limit = WASHROOM_LIMIT
        elif activity_type == "Food":
            limit = FOOD_LIMIT

        if limit:
            remaining = limit - (now - start_time)
            remaining_str = str(remaining).split('.')[0] if remaining > timedelta(0) else "00:00:00"
            back_text = f"Back ({remaining_str} left)"
        else:
            back_text = "Back"

        keyboard.append([KeyboardButton(back_text)])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ===== START COMMAND =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Punch System\nSelect an option:",
        reply_markup=get_keyboard(update.message.from_user.id)
    )

# ===== HANDLE MESSAGES =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    name = update.message.from_user.full_name
    text = update.message.text
    now = datetime.now(UTC_PLUS_7)

    # ----- BACK BUTTON -----
    if text.startswith("Back"):
        if user_id in activity_start:
            start_time, activity_type = activity_start[user_id]
            duration = now - start_time
            exceeded = False
            limit = None

            if activity_type == "Washroom":
                limit = WASHROOM_LIMIT
            elif activity_type == "Food":
                limit = FOOD_LIMIT

            if limit and duration > limit:
                exceeded = True
                # Notify admin
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"{name} exceeded {activity_type} duration: {str(duration).split('.')[0]}"
                )

            del activity_start[user_id]

            msg = f"{name} returned from {activity_type}.\nTime spent: {str(duration).split('.')[0]}"
            if exceeded:
                msg += "\nTime limit exceeded ❌"
            await update.message.reply_text(msg, reply_markup=get_keyboard(user_id))
        else:
            await update.message.reply_text("❌ You are not in any activity.", reply_markup=get_keyboard(user_id))
        return

    # ----- CHECK-IN -----
    if text == "Check-In":
        user_checkin[user_id] = True
        if now.hour >= LATE_CHECKIN_HOUR:
            await update.message.reply_text("LATE CHECK IN ❌", reply_markup=get_keyboard(user_id))
            # Notify admin
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"{name} checked in late at {now.strftime('%H:%M:%S')}"
            )
        else:
            await update.message.reply_text(f"{name} checked in at {now.strftime('%H:%M:%S')}", reply_markup=get_keyboard(user_id))
        return

    # ----- CHECK-OUT -----
    if text == "Check-Out":
        await update.message.reply_text(f"{name} checked out at {now.strftime('%H:%M:%S')}", reply_markup=get_keyboard(user_id))
        return

    # ----- ACTIVITIES -----
    if text in ["Food", "Washroom", "Others"]:
        if user_id not in user_checkin:
            await update.message.reply_text("❌ You must check-in first.", reply_markup=get_keyboard(user_id))
            return

        # Start activity
        activity_start[user_id] = (now, text)
        await update.message.reply_text(f"{name} started {text} at {now.strftime('%H:%M:%S')}", reply_markup=get_keyboard(user_id))
        return

    # ----- UNKNOWN -----
    await update.message.reply_text("Please select a valid option from the buttons.", reply_markup=get_keyboard(user_id))

# ===== MAIN APP =====
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("Bot running...")
app.run_polling()
