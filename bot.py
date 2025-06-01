import os
import logging
from datetime import datetime

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
ASK_BIRTH, ASK_SIGN = range(2)

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
        await update.message.reply_text("Отлично! Теперь напиши свой знак зодиака (например: Лев, Рыбы и т.д.):")
        return ASK_SIGN
    except ValueError:
        await update.message.reply_text("Неверный формат. Введи дату так: 01.03.1998")
        return ASK_BIRTH

# Получаем знак
async def ask_sign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sign = update.message.text.strip().capitalize()
    birth_date = context.user_data.get("birth_date")
    user = update.effective_user

    supabase.table("users").update({
        "birth_date": str(birth_date),
        "zodiac_sign": sign
    }).eq("tg_id", user.id).execute()

    await update.message.reply_text(
        f"Спасибо! Профиль обновлён. Ты — {sign}, родился {birth_date.strftime('%d.%m.%Y')} ☀️"
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
            ASK_SIGN: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_sign)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    logger.info("Bot started")
    app.run_polling()
