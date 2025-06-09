import os
import io
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
from reportlab.pdfgen import canvas

# ─────────────────── env & clients ───────────────────
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # service‑role key ⇒ full access
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────── state machine ───────────────────
READY, DATE, TIME, LOCATION = range(4)

# ─────────────────── helpers ─────────────────────────

def text_to_pdf(text: str) -> bytes:
    """Convert plain text to PDF and return bytes."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    y = 800
    for line in text.splitlines():
        c.drawString(40, y, line)
        y -= 15
        if y < 40:
            c.showPage()
            y = 800
    c.save()
    buffer.seek(0)
    return buffer.read()

def upload_pdf(user_id: str, data: bytes) -> str:
    bucket = supabase.storage.from_("destiny-reports")
    filename = f"{user_id}.pdf"
    bucket.upload(filename, data, content_type="application/pdf", upsert=True)
    return bucket.get_public_url(filename)

def build_destiny_prompt(row: dict) -> str:
    return dedent(f"""
        SYSTEM:
        Ты — опытный астропсихолог. Объясняй понятно, без жаргона, в дружелюбном тоне, на «ты».
        Не упоминай ограничений модели и не говори, что это искусственный интеллект.

        USER:
        Данные для натального анализа:
        Имя: {row['name']}
        Дата рождения: {row['birth_date']}
        Время рождения: {row['birth_time']}
        Место рождения: {row['birth_city']}, {row['birth_country']}

        Составь «Карту предназначения» (650–800 слов). Структура:
        1. 🎯 Миссия души – 5–7 предложений.
        2. 💎 Врождённые таланты – маркированный список из 4–5 пунктов.
        3. 💼 Профессия и деньги – 5–7 предложений о подходящих сферах и стиле заработка.
        4. ⚠️ Возможные блоки – 4–5 пунктов с коротким советом, как их обходить.
        5. 🛠 Рекомендации – 5–7 предложений.
        В конце добавь абзац «Как применять знания на практике». Никаких заголовков «заключение».
    """)

# ─────────────────── command /start ──────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id

    # ensure user row exists
    if not supabase.table("users").select("id").eq("tg_id", tg_id).execute().data:
        supabase.table("users").insert({"tg_id": tg_id, "name": user.first_name}).execute()

    greeting = (
        "Привет! Я CosmoAstro — твой астрологический навигатор по самому важному путешествию: тебе самому 🌌\n\n"
        "Здесь ты можешь:\n"
        "✨ Получить натальную карту по дате, времени и месту рождения\n"
        "🌙 Узнавать, как луна влияет на твой день\n"
        "🪐 Понять, в какие дни действовать, а в какие — просто побыть собой\n\n"
        "Всё, что тебе нужно — ответить на 3 простых вопроса."
    )
    await update.message.reply_text(greeting)
    await asyncio.sleep(5)
    await update.message.reply_text(
        "Готов узнать о себе больше?\nНажми 'Готов', и мы начнём.",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔮 Готов")]], resize_keyboard=True)
    )
    return READY

async def ask_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("1/3 — Введи свою дату рождения в формате ДД.ММ.ГГГГ:", reply_markup=ReplyKeyboardRemove())
    return DATE

async def save_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    try:
        context.user_data["birth_date"] = datetime.strptime(txt, "%d.%m.%Y").date()
    except ValueError:
        await update.message.reply_text("Неверный формат. Попробуй ещё раз: 01.03.1998")
        return DATE
    await update.message.reply_text("2/3 — Введи время рождения в формате ЧЧ:ММ (например, 03:00):")
    return TIME

async def save_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    try:
        datetime.strptime(txt, "%H:%M")
        context.user_data["birth_time"] = txt
    except ValueError:
        await update.message.reply_text("Неверный формат времени. Пример: 03:00")
        return TIME
    await update.message.reply_text("3/3 — Введи страну и город, например: Латвия, Рига")
    return LOCATION

async def save_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = [p.strip() for p in update.message.text.split(",")]
    if len(parts) < 2:
        await update.message.reply_text("Нужен формат: Страна, Город (пример: Латвия, Рига)")
        return LOCATION
    country, city = parts[0], ", ".join(parts[1:])

    tg_id = update.effective_user.id
    supabase.table("users").update({
        "birth_date": str(context.user_data["birth_date"]),
        "birth_time": context.user_data["birth_time"],
        "birth_country": country,
        "birth_city": city,
    }).eq("tg_id", tg_id).execute()

    menu = ReplyKeyboardMarkup([
        ["🔮 Натальный разбор"],
        ["🌙 Луна сегодня"],
        ["⚡ Энергия дня"],
        ["📜 Карта предназначения"],
    ], resize_keyboard=True)
    await update.message.reply_text(
        "Спасибо! Теперь выбери, что хочешь узнать:", reply_markup=menu
    )
    return ConversationHandler.END

# ─────────────────── destiny card flow ───────────────

async def destiny_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    description = (
        "Карта предназначения — это персональное астрологическое послание, раскрывающее самую суть твоего пути: миссию души, врождённые таланты и сферы, где усилия приносят наибольший рост и доход.\n"
        "За пару минут ты получишь ясный, вдохновляющий ориентир, который поможет принимать решения в гармонии с собой и обходить скрытые блоки."
    )
    await update.message.reply_text(description)
    await asyncio.sleep(5)
    cta_kb = InlineKeyboardMarkup([[InlineKeyboardButton("Получить карту", callback_data="get_destiny")]])
    await update.message.reply_text(
        "Готов открыть собственный маршрут к успеху и свободе? Тогда нажми «Получить карту» и узнай своё истинное предназначение уже сейчас.",
        reply_markup=cta_kb
    )

async def destiny_card_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    msg = await query.message.reply_text("⏳ Формируем карту… это займёт около минуты.")

    tg_id = query.from_user.id
    row = supabase.table("users").select("id,name,birth_date,birth_time,birth_country,birth_city").eq("tg_id", tg_id).execute().data[0]

    prompt = build_destiny_prompt(row)
    try:
        resp = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.9,
            max_tokens=1200,
        )
        text = resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error("OpenAI error: %s", e)
        await msg.edit_text("Не удалось сгенерировать ответ. Попробуй позже.")
        return

    # try PDF
    try:
        pdf_bytes = text_to_pdf(text)
        public_url = upload_pdf(row["id"], pdf_bytes)
        await query.message.reply_document(public_url, filename="Карта_предназначения.pdf", caption="🔮 Карта предназначения готова!")
    except Exception as e:
        logger.error("PDF error → fallback text: %s", e)
        await query.message.reply_text(f"🔮 Карта предназначения готова:\n\n{text}")

    await msg.delete()

# ─────────────────── init & handlers ─────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(TG_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            READY: [MessageHandler(filters.Regex("^

