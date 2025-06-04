import os
import logging
import asyncio
from datetime import datetime, time as dt_time

from dotenv import load_dotenv
from telegram import (
    Update,
    ReplyKeyboardRemove,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
from supabase import create_client, Client
from openai import OpenAI

# --------------------------------------------------
# ENV & INIT
# --------------------------------------------------
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

# --------------------------------------------------
# Conversation states
# --------------------------------------------------
READY, DATE, TIME, LOCATION = range(4)

# --------------------------------------------------
# /start command
# --------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id

    # ensure user row exists
    if not supabase.table("users").select("id").eq("tg_id", tg_id).execute().data:
        supabase.table("users").insert({"tg_id": tg_id, "name": user.first_name}).execute()

    # intro
    await update.message.reply_text(
        "Привет! Я CosmoAstro — твой астрологический навигатор по самому важному путешествию: тебе самому 🌌\n\n"
        "Здесь ты можешь:\n"
        "✨ Получить натальную карту по дате, времени и месту рождения\n"
        "🌙 Узнавать, как луна влияет на твой день\n"
        "🪐 Понять, в какие дни действовать, а в какие — просто побыть собой\n\n"
        "Всё, что тебе нужно — ответить на 3 простых вопроса."
    )

    await asyncio.sleep(5)

    await update.message.reply_text(
        "Готов узнать о себе больше?\nНажми \"Готов\", и мы начнём.",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔮 Готов")]], resize_keyboard=True),
    )
    return READY

# --------------------------------------------------
# Step 0 — wait for "Готов"
# --------------------------------------------------
async def wait_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != "🔮 Готов":
        return READY  # ignore anything else

    await update.message.reply_text(
        "1/3 — Введи свою дату рождения в формате ДД.ММ.ГГГГ:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return DATE

# --------------------------------------------------
# Step 1 — date
# --------------------------------------------------
async def ask_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    try:
        birth_date = datetime.strptime(raw, "%d.%m.%Y").date()
        context.user_data["birth_date"] = birth_date
    except ValueError:
        await update.message.reply_text("Неверный формат. Попробуй так: 02.03.1998")
        return DATE

    await update.message.reply_text("2/3 — А теперь введи время рождения в формате ЧЧ:ММ (например, 03:00):")
    return TIME

# --------------------------------------------------
# Step 2 — time
# --------------------------------------------------
async def ask_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    try:
        birth_time = datetime.strptime(raw, "%H:%M").time()
        context.user_data["birth_time"] = birth_time
    except ValueError:
        await update.message.reply_text("Неверный формат времени. Попробуй так: 03:00")
        return TIME

    await update.message.reply_text(
        "3/3 — И наконец, введи страну и город рождения, например: Латвия, Рига",
    )
    return LOCATION

# --------------------------------------------------
# Step 3 — location
# --------------------------------------------------
async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    if "," not in raw:
        await update.message.reply_text("Неверный формат. Введи через запятую: Страна, Город")
        return LOCATION

    country, city = [x.strip() for x in raw.split(",", maxsplit=1)]
    context.user_data["birth_country"] = country
    context.user_data["birth_city"] = city

    # Persist to supabase
    user = update.effective_user
    supabase.table("users").update(
        {
            "birth_date": str(context.user_data["birth_date"]),
            "birth_time": str(context.user_data["birth_time"]),
            "birth_country": country,
            "birth_city": city,
        }
    ).eq("tg_id", user.id).execute()

    # Final message with menu
    await update.message.reply_text(
        "Спасибо! Теперь, на основе этих данных, мы можем рассказать тебе куда больше, чем ты сам о себе знаешь.\n\n"
        "Выбирай, что хочешь узнать:",
        reply_markup=ReplyKeyboardMarkup(
            [["🔮 Натальный разбор"], ["🌙 Луна сегодня"], ["⚡ Энергия дня"]], resize_keyboard=True
        ),
    )
    return ConversationHandler.END

# --------------------------------------------------
# Cancel
# --------------------------------------------------
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Окей, если что — просто напиши /start", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --------------------------------------------------
# Main
# --------------------------------------------------
if __name__ == "__main__":
    app = ApplicationBuilder().token(TG_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            READY: [MessageHandler(filters.TEXT & ~filters.COMMAND, wait_ready)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_date)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_time)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_location)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    logger.info("Bot started")
    app.run_polling()

