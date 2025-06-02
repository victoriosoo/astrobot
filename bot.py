import os
import logging
from datetime import datetime, time

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardRemove
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
ASK_BIRTH, ASK_TIME, ASK_COUNTRY, ASK_CITY = range(4)

# Определение знака зодиака
ZODIAC_SIGNS = [
    (120, "Козерог"), (218, "Водолей"), (320, "Рыбы"), (420, "Овен"),
    (521, "Телец"), (621, "Близнецы"), (722, "Рак"), (823, "Лев"),
    (923, "Дева"), (1023, "Весы"), (1122, "Скорпион"), (1222, "Стрелец"), (1231, "Козерог")
]

def get_zodiac_sign(date: datetime.date) -> str:
    month_day = int(date.strftime("%m%d"))
    for limit, sign in ZODIAC_SIGNS:
        if month_day <= limit:
            return sign
    return "Козерог"

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    name = user.first_name

    # Проверка в Supabase
    existing = supabase.table("users").select("id").eq("tg_id", tg_id).execute()
    if not existing.data:
        supabase.table("users").insert({
            "tg_id": tg_id,
            "name": name
        }).execute()

    await update.message.reply_text(
        "Привет! Я CosmoAstro 🪐\n"
        "Давай настроим твой профиль. Сначала напиши свою дату рождения в формате ДД.ММ.ГГГГ:"
    )
    return ASK_BIRTH

# Получаем дату рождения
async def ask_birth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    try:
        birth_date = datetime.strptime(user_input, "%d.%m.%Y").date()
        context.user_data["birth_date"] = birth_date
        context.user_data["zodiac_sign"] = get_zodiac_sign(birth_date)
        await update.message.reply_text("Спасибо! А теперь введи время рождения в формате ЧЧ:ММ (например, 14:30):")
        return ASK_TIME
    except ValueError:
        await update.message.reply_text("Неверный формат. Введи дату так: 01.03.1998")
        return ASK_BIRTH

# Получаем время рождения
async def ask_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    try:
        birth_time = datetime.strptime(user_input, "%H:%M").time()
        context.user_data["birth_time"] = birth_time
        await update.message.reply_text("Хорошо! В какой стране ты родился?")
        return ASK_COUNTRY
    except ValueError:
        await update.message.reply_text("Неверный формат. Введи время так: 14:30")
        return ASK_TIME

# Получаем страну
async def ask_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["birth_country"] = update.message.text.strip()
    await update.message.reply_text("А в каком городе?")
    return ASK_CITY

# Получаем город и сохраняем всё
async def ask_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["birth_city"] = update.message.text.strip()
    user = update.effective_user

    data = {
        "birth_date": str(context.user_data.get("birth_date")),
        "birth_time": str(context.user_data.get("birth_time")),
        "birth_country": context.user_data.get("birth_country"),
        "birth_city": context.user_data.get("birth_city"),
        "zodiac_sign": context.user_data.get("zodiac_sign")
    }

    supabase.table("users").update(data).eq("tg_id", user.id).execute()

    await update.message.reply_text(
        f"Спасибо! Профиль обновлён. Ты — {data['zodiac_sign']}, родился {context.user_data['birth_date'].strftime('%d.%m.%Y')} в {data['birth_city']}, {data['birth_country']} в {data['birth_time']} ☀️"
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
            ASK_COUNTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_country)],
            ASK_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_city)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    logger.info("Bot started")
    app.run_polling()

