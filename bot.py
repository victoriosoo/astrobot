import os
import logging
import asyncio
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
from openai import OpenAI
from supabase import create_client, Client

# Загрузка переменных окружения
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
ASK_BIRTH, ASK_TIME, ASK_LOCATION = range(3)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    name = user.first_name

    # Проверка в Supabase
    existing = supabase.table("users").select("id").eq("tg_id", tg_id).execute()
    if not existing.data:
        supabase.table("users").insert({"tg_id": tg_id, "name": name}).execute()

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
        "Готов узнать о себе больше?\nНажми 'Готов', и мы начнём.",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔮 Готов")]], resize_keyboard=True)
    )
    return ASK_BIRTH

# Получаем дату рождения
async def ask_birth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != "🔮 Готов":
        await update.message.reply_text("Нажми кнопку '🔮 Готов', чтобы начать")
        return ASK_BIRTH

    await update.message.reply_text("1/3 — Введи свою дату рождения в формате ДД.ММ.ГГГГ:", reply_markup=ReplyKeyboardRemove())
    return ASK_TIME

# Получаем время рождения
async def ask_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    try:
        birth_date = datetime.strptime(user_input, "%d.%m.%Y").date()
        context.user_data["birth_date"] = birth_date
        await update.message.reply_text("2/3 — А теперь введи время рождения в формате ЧЧ:ММ (например, 03:00):")
        return ASK_LOCATION
    except ValueError:
        await update.message.reply_text("Неверный формат. Введи дату так: 01.03.1998")
        return ASK_TIME

# Получаем страну и город (в одной строке)
async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["birth_location"] = update.message.text.strip()
    user = update.effective_user

    location_parts = context.user_data["birth_location"].split(",")
    country = location_parts[-1].strip() if len(location_parts) > 1 else ""
    city = location_parts[0].strip()

    supabase.table("users").update({
        "birth_date": str(context.user_data["birth_date"]),
        "birth_time": "03:00",  # временно жёстко задано для MVP
        "birth_country": country,
        "birth_city": city
    }).eq("tg_id", user.id).execute()

    await update.message.reply_text(
        "Спасибо! Теперь, на основе этих данных, мы можем рассказать тебе куда больше, чем ты сам о себе знаешь.\n\n"
        "Выбирай, что хочешь узнать:",
        reply_markup=ReplyKeyboardMarkup([
            ["🔮 Натальный разбор"],
            ["🌙 Луна сегодня"],
            ["⚡ Энергия дня"]
        ], resize_keyboard=True)
    )
    return ConversationHandler.END

# Отмена
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Окей, если что — просто напиши /start", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Запуск
if __name__ == "__main__":
    app = ApplicationBuilder().token(TG_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_BIRTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_birth)],
            ASK_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_time)],
            ASK_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_location)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    logger.info("Bot started")
    app.run_polling()

