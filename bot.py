import os
import io
import logging
import asyncio
import time
from datetime import datetime
from textwrap import wrap

from dotenv import load_dotenv
from telegram import (
    Update,
    ReplyKeyboardRemove,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
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

# ────────── после import-ов, ПЕРЕД create_client ──────────
import pprint, os
pprint.pprint({k: v for k, v in os.environ.items() if k.startswith("SUPABASE")})
# ──────────────────────────────────────────────────────────
from supabase import create_client, Client
from openai import OpenAI

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_PATH = os.path.join(os.path.dirname(__file__), "DejaVuSans.ttf")
pdfmetrics.registerFont(TTFont("DejaVuSans", FONT_PATH))

# ──────────────── env / logger ────────────────
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = (
    os.getenv("SUPABASE_KEY") or
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ──────────────── conversation states ────────────────
READY, DATE, TIME, LOCATION = range(4)

# ──────────────── helpers ────────────────
def text_to_pdf(text: str) -> bytes:
    buf = io.BytesIO()

    # создаём PDF-документ
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=50, bottomMargin=50)

    # подключаем стиль со шрифтом
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='Body',
        fontName='DejaVuSans',
        fontSize=12,
        leading=16,
        spaceAfter=10,
        alignment=TA_LEFT
    ))

    story = []

    # разбиваем по двойным переносам (абзацы)
    for block in text.strip().split('\n\n'):
        story.append(Paragraph(block.replace("\n", "<br/>"), styles["Body"]))
        story.append(Spacer(1, 8))

    doc.build(story)
    return buf.getvalue()
def upload_pdf_to_storage(user_id: str, pdf_bytes: bytes) -> str:
    bucket = supabase.storage.from_("destiny-reports")
    fname = f"{user_id}_{int(time.time())}.pdf"
    bucket.upload(fname, pdf_bytes)
    return bucket.get_public_url(fname)

def build_destiny_prompt(name, date, time_str, city, country) -> list[dict]:
    """Return messages payload for chat completions."""
    sys = (
        "Ты — опытный астропсихолог. Объясняй понятно, дружелюбно, на «ты». "
        "Не упоминай ограничения модели и что ты ИИ."
    )
    user = f"""Данные для натального анализа:
Имя: {name}
Дата рождения: {date}
Время рождения: {time_str}
Место рождения: {city}, {country}

Составь «Карту предназначения» (650–800 слов).

Структура:
1. 🎯 Миссия души – 5-7 предложений.
2. 💎 Врождённые таланты – маркированный список 4-5 пунктов.
3. 💼 Профессия и деньги – 5-7 предложений.
4. ⚠️ Возможные блоки – 4-5 пунктов с коротким советом.
5. 🛠 Рекомендации – 3 конкретных шага.

Заверши последним советом + добавь финальный абзац «Как применять знания на практике».
"""
    return [{"role": "system", "content": sys}, {"role": "user", "content": user}]

# ──────────────── /start flow ────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    name = user.first_name

    # ensure user row exists
    if not supabase.table("users").select("id").eq("tg_id", tg_id).execute().data:
        supabase.table("users").insert({"tg_id": tg_id, "name": name}).execute()

    await update.message.reply_text(
        "Привет! Я CosmoAstro — твой астрологический навигатор 🌌\n\n"
        "Здесь ты можешь:\n"
        "✨ Получить натальную карту\n"
        "🌙 Узнать влияние луны\n"
        "🪐 Понять дни действия и отдыха\n\n"
        "Всё, что нужно — ответить на 3 вопроса."
    )
    await asyncio.sleep(5)

    await update.message.reply_text(
        "Готов узнать о себе больше?\nНажми «Готов», и мы начнём.",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔮 Готов")]], resize_keyboard=True),
    )
    return READY

async def ask_birth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != "🔮 Готов":
        return READY
    await update.message.reply_text("1/3 — Введи дату рождения (ДД.ММ.ГГГГ):", reply_markup=ReplyKeyboardRemove())
    return DATE

async def ask_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        birth_date = datetime.strptime(update.message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        await update.message.reply_text("Неверный формат. Пример: 02.03.1998")
        return DATE
    context.user_data["birth_date"] = birth_date
    await update.message.reply_text("2/3 — Введи время рождения (ЧЧ:ММ):")
    return TIME

async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        birth_time = datetime.strptime(update.message.text.strip(), "%H:%M").time()
    except ValueError:
        await update.message.reply_text("Неверный формат времени. Пример: 03:00")
        return TIME
    context.user_data["birth_time"] = birth_time
    await update.message.reply_text("3/3 — Введи страну и город (например: Латвия, Рига):")
    return LOCATION

async def save_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = [p.strip() for p in update.message.text.split(",")]
    if len(parts) < 2:
        await update.message.reply_text("Формат: Страна, Город. Пример: Латвия, Рига")
        return LOCATION

    country, city = parts[0], parts[1]
    user = update.effective_user
    supabase.table("users").update(
        {
            "birth_date": str(context.user_data["birth_date"]),
            "birth_time": context.user_data["birth_time"].strftime("%H:%M"),
            "birth_country": country,
            "birth_city": city,
        }
    ).eq("tg_id", user.id).execute()

    await update.message.reply_text(
        "Спасибо! Данные сохранены.\nВыбери, что тебе интересно:",
        reply_markup=ReplyKeyboardMarkup(
            [["📜 Карта предназначения"]], resize_keyboard=True
        ),
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Окей, если что — /start", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ──────────────── destiny card flow ────────────────
async def destiny_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Карта предназначения — персональное послание о твоей миссии, талантах "
        "и сферах роста. Поможет принимать решения в гармонии с собой.\n\n"
        "Через 5 секунд появится кнопка, чтобы получить карту."
    )
    await asyncio.sleep(5)
    await update.message.reply_text(
        "Готов открыть свой маршрут к успеху и свободе?\n"
        "Нажми «Получить карту»!",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔮 Получить карту", callback_data="destiny_card")]]
        ),
    )

async def destiny_card_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("⏳ Формируем карту… это займёт около минуты.")

    tg_id = query.from_user.id
    user_res = supabase.table("users").select("*").eq("tg_id", tg_id).execute()
    if not user_res.data:
        await query.message.reply_text("Не найден профиль. Пройди /start.")
        return
    u = user_res.data[0]

    # build prompt & call GPT
    messages = build_destiny_prompt(
        name=u.get("name", "Друг"),
        date=datetime.strptime(u["birth_date"], "%Y-%m-%d").strftime("%d.%m.%Y"),
        time_str=u["birth_time"],
        city=u["birth_city"],
        country=u["birth_country"],
    )
    try:
        resp = OPENAI.chat.completions.create(
            model="gpt-4-turbo",
            messages=messages,
            max_tokens=1100,
            temperature=0.9,
        )
        report_text = resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error("GPT error: %s", e)
        await query.message.reply_text("Ошибка генерации. Попробуй позже.")
        return

    # generate PDF -> upload -> send
    try:
        pdf_bytes = text_to_pdf(report_text)
        public_url = upload_pdf_to_storage(u["id"], pdf_bytes)
        await query.message.reply_document(
            document=public_url,
            filename="Karta_Prednaznacheniya.pdf",
            caption="🔮 Карта предназначения готова!",
        )
    except Exception as e:
        logger.error("PDF/upload error: %s", e)
        await query.message.reply_text(
            "Карта готова, но файл не прикрепился 😔. Вот текст:\n\n" + report_text
        )

# ──────────────── launch ────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(TG_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            READY: [MessageHandler(filters.Regex(r"^🔮 Готов$"), ask_birth)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_time)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_location)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_profile)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Regex(r"^📜 Карта предназначения$"), destiny_product))
    app.add_handler(CallbackQueryHandler(destiny_card_callback, pattern=r"^destiny_card$"))

    logger.info("Bot started")
    app.run_polling()


