import os
import logging
import asyncio
from datetime import datetime
from textwrap import dedent

from dotenv import load_dotenv
from telegram import (
    Update,
    ReplyKeyboardRemove,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    constants,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
from supabase import create_client, Client
from openai import OpenAI

# ---------- ENV & INIT ----------
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- STATES ----------
READY, DATE, TIME, LOCATION = range(4)

# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    name = user.first_name

    # Ensure user row exists
    if not supabase.table("users").select("id").eq("tg_id", tg_id).execute().data:
        supabase.table("users").insert({"tg_id": tg_id, "name": name}).execute()

    await update.message.reply_text(
        dedent(
            """
            Привет! Я CosmoAstro — твой астрологический навигатор по самому важному путешествию: тебе самому 🌌

            Здесь ты можешь:
            ✨ Получить натальную карту по дате, времени и месту рождения
            🌙 Узнавать, как луна влияет на твой день
            🪐 Понять, в какие дни действовать, а в какие — просто побыть собой

            Всё, что тебе нужно — ответить на 3 простых вопроса.
            """
        )
    )

    await asyncio.sleep(5)

    await update.message.reply_text(
        "Готов узнать о себе больше?\nНажми 'Готов', и мы начнём.",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔮 Готов")]], resize_keyboard=True)
    )
    return READY

# ---------- PROFILE QUESTIONS ----------
async def ask_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != "🔮 Готов":
        return READY
    await update.message.reply_text("1/3 — Введи дату рождения (ДД.ММ.ГГГГ):", reply_markup=ReplyKeyboardRemove())
    return DATE

async def save_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        birth_date = datetime.strptime(update.message.text.strip(), "%d.%m.%Y").date()
        context.user_data["birth_date"] = birth_date
        await update.message.reply_text("2/3 — Введи время рождения (ЧЧ:ММ):")
        return TIME
    except ValueError:
        await update.message.reply_text("Формат даты неверен, попробуй ещё раз: 01.03.1998")
        return DATE

async def save_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        datetime.strptime(update.message.text.strip(), "%H:%M").time()
        context.user_data["birth_time"] = update.message.text.strip()
        await update.message.reply_text("3/3 — Введи страну и город, например: Латвия, Рига")
        return LOCATION
    except ValueError:
        await update.message.reply_text("Формат времени неверен, попробуй ещё раз: 03:00")
        return TIME

async def save_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location_raw = update.message.text.strip()
    parts = [p.strip() for p in location_raw.split(",")]
    if len(parts) < 2:
        await update.message.reply_text("Нужно два значения через запятую — страна, город. Пример: Латвия, Рига")
        return LOCATION

    country, city = parts[0], parts[1]
    user = update.effective_user

    supabase.table("users").update({
        "birth_date": str(context.user_data["birth_date"]),
        "birth_time": context.user_data["birth_time"],
        "birth_country": country,
        "birth_city": city,
    }).eq("tg_id", user.id).execute()

    await update.message.reply_text(
        "Спасибо! Теперь выбери, что хочешь узнать:",
        reply_markup=ReplyKeyboardMarkup([
            ["🔮 Натальный разбор"],
            ["🌙 Луна сегодня"],
            ["⚡ Энергия дня"],
            ["📜 Карта предназначения"],
        ], resize_keyboard=True)
    )
    return ConversationHandler.END

# ---------- PRODUCTS FLOW ----------
async def products_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📜 Карта предназначения":
        await show_destiny_description(update, context)

async def show_destiny_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = (
        "Карта предназначения — это персональное астрологическое послание, раскрывающее самую суть вашего пути: миссию души, врождённые таланты и сферы, где усилия приносят наибольший рост и доход. "
        "За пару минут вы получите ясный, вдохновляющий ориентир, который поможет принимать решения в гармонии с собой и обходить скрытые блоки."
    )
    await update.message.reply_text(desc)
    await asyncio.sleep(5)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Получить карту", callback_data="get_destiny")]
    ])
    await update.message.reply_text(
        "Готов открыть собственный маршрут к успеху и свободе? Нажми кнопку ниже и узнай своё истинное предназначение уже сейчас.",
        reply_markup=keyboard,
    )

async def destiny_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_row = supabase.table("users").select("name, birth_date, birth_time, birth_country, birth_city, id").eq("tg_id", user.id).execute().data[0]
    # Prompt building
    prompt_system = "Ты — опытный астропсихолог. Объясняй понятно, без жаргона, в дружелюбном тоне, на ‘ты’. Не упоминай ограничений модели и не говори, что это ‘искусственный интеллект’."
    prompt_user = dedent(
        f"""Данные для натального анализа:
Имя: {user_row['name'] or 'Друг'}
Дата рождения: {user_row['birth_date']}
Время рождения: {user_row['birth_time']}
Место рождения: {user_row['birth_city']}, {user_row['birth_country']}

Составь «Карту предназначения» (~350–450 слов). Структура:
1. 🎯 Миссия души – 2–3 предложения.
2. 💎 Врождённые таланты – маркированный список из 3–4 пунктов.
3. 💼 Профессия и деньги – абзац о подходящих сферах и стиле заработка.
4. ⚠️ Возможные блоки – 2 пункта с коротким советом, как их обходить.
5. 🛠 Рекомендации – 3 конкретных шага для раскрытия потенциала.

Никаких пунктов «заключение» — просто заверши последним советом."""
    )

    completion = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt_system}, {"role": "user", "content": prompt_user}],
        temperature=0.8,
        max_tokens=800,
    )
    report_text = completion.choices[0].message.content.strip()

    await query.edit_message_text(
        f"🔮 *Карта предназначения готова*:\n\n{report_text}",
        parse_mode=constants.ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )

# ---------- CANCEL ----------
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено. Напиши /start, если захочешь начать заново.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ---------- MAIN ----------
if __name__ == "__main__":
    app = ApplicationBuilder().token(TG_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            READY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_date)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_date)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_time)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_location)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    # Router for main menu buttons
    app.add_handler(MessageHandler(filters.Regex("📜 Карта предназначения"), products_router))
    app.add_handler(CallbackQueryHandler(destiny_callback, pattern="^get_destiny$"))

    logger.info("Bot started")
    app.run_polling()

