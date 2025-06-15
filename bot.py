import os
import io
import logging
import asyncio
import time
import re
import qrcode
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
from reportlab.platypus import HRFlowable
from reportlab.platypus import Image
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


FONT_PATH = os.path.join(os.path.dirname(__file__), "DejaVuSans.ttf")
FONT_BOLD_PATH = os.path.join(os.path.dirname(__file__), "DejaVuSans-Bold.ttf")
pdfmetrics.registerFont(TTFont("DejaVuSans", FONT_PATH))
pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", FONT_BOLD_PATH))

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
def draw_watermark(canvas, doc):
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")  # Имя файла логотипа
    page_width, page_height = A4
    logo_width = 250
    logo_height = 250
    x = (page_width - logo_width) / 2
    y = (page_height - logo_height) / 2
    canvas.saveState()
    try:
        canvas.setFillAlpha(0.1)  # 10% opacity
    except AttributeError:
        pass  # Для старых версий ReportLab fallback
    canvas.drawImage(logo_path, x, y, width=logo_width, height=logo_height, mask='auto')
    canvas.restoreState()
def text_to_pdf(text: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=50, bottomMargin=50
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='Body',
        fontName='DejaVuSans',
        fontSize=12,
        leading=16,
        spaceAfter=6,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name='Header',
        fontName='DejaVuSans-Bold',
        fontSize=14,
        leading=18,
        spaceBefore=14,
        spaceAfter=6,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#7C3AED"),
    ))
    styles.add(ParagraphStyle(
        name='BigTitle',
        fontName='DejaVuSans-Bold',
        fontSize=24,
        textColor=colors.HexColor("#7C3AED"),  # фирменный фиолетовый CosmoAstro
        leading=28,
        alignment=TA_LEFT,
        spaceAfter=20,
    ))

    story = []

    story.append(Paragraph("Карта предназначения — CosmoAstro", styles["BigTitle"]))
    story.append(Spacer(1, 24))

    for block in text.strip().split('\n\n'):
        block = block.strip()
        # Если блок начинается с одного или нескольких "#", это точно заголовок
        if re.match(r"^#+\s*", block):
            clean = re.sub(r"^#+\s*", "", block)
            story.append(Paragraph(clean, styles["Header"]))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#7C3AED"), spaceBefore=4, spaceAfter=10))
        # Либо короткая строка без спецсимволов (как до этого)
        elif (
            len(block) < 40
            and not any(ch in block for ch in "-*:;")
            and not re.match(r"^[-•]", block)
            and block != ""
        ):
            story.append(Paragraph(block, styles["Header"]))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#7C3AED"), spaceBefore=4, spaceAfter=10))
        else:
            for line in block.split('\n'):
                line = line.strip()
                if not line:
                    continue
                line = line.replace("**", "").replace("_", "")
                story.append(Paragraph(line, styles["Body"]))
                story.append(Spacer(1, 4))
        story.append(Spacer(1, 10))
    
    qr_img = qrcode.make("https://t.me/CosmoAstrologyBot")
    buf_qr = io.BytesIO()
    qr_img.save(buf_qr, format='PNG')
    buf_qr.seek(0)
    qr_image = Image(buf_qr, width=30*mm, height=30*mm)
    story.append(Spacer(1, 40))
    story.append(qr_image)

    story.append(Spacer(1, 4))
    story.append(Paragraph('<font size=10 color="#7C3AED">https://t.me/CosmoAstrologyBot</font>', styles["Body"]))

    doc.build(
        story,
        onFirstPage=draw_watermark,
        onLaterPages=draw_watermark
    )
    return buf.getvalue()

def upload_pdf_to_storage(user_id: str, pdf_bytes: bytes) -> str:
    bucket = supabase.storage.from_("destiny-reports")
    fname = f"{user_id}_{int(time.time())}.pdf"
    bucket.upload(fname, pdf_bytes)
    return bucket.get_public_url(fname)

def build_destiny_prompt(name, date, time_str, city, country) -> list[dict]:
    sys = (
        "Ты — опытный астропсихолог-женщина, всегда общаешься только в женском роде, будто ты подруга для пользователя. "
        "Пиши исключительно в женском роде, используй подходящие обращения, примеры и слова для девушек. "
        "Объясняй понятно, дружелюбно, на «ты». Не упоминай ограничения модели и что ты ИИ."
    )
    user = f"""Данные для натального анализа:
Имя: {name}
Дата рождения: {date}
Время рождения: {time_str}
Место рождения: {city}, {country}

Составь «Карту предназначения» объёмом 900–1400 слов.

❗ ВАЖНО:
— Каждый раздел должен быть ОЧЕНЬ подробно раскрыт: опиши с примерами, пояснениями, рассуждениями, чтобы каждый блок содержал не менее 150–250 слов.
— НЕ используй нумерацию и маркировку (никаких «1.», «2.», «-»).
— Каждый раздел начинай с отдельной строки с заголовком БЕЗ цифр, просто: «Миссия души», «Врождённые таланты», «Профессия и деньги», «Возможные блоки», «Рекомендации».
— После заголовка ставь два перевода строки, чтобы текст шёл отдельным абзацем.
— Не используй markdown (никаких # или **).

Пример:
Миссия души

(Абзац…)

Врождённые таланты

(Абзац или раскрытые пункты — каждый подробно объяснен и расписан.)

…

В самом конце добавь раздел:
Как применять на практике

(Конкретный абзац-инструкция, как внедрить эти советы в жизнь.)
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
    "Привет! Я CosmoAstro — твой личный астролог 🌙\n"
    "Используя твою натальную карту, я помогу тебе понять, какие сильные стороны ты не используешь, "
    "в какой сфере тебя ждёт рост, и где зарыт твой внутренний ресурс.\n\n"
    "🪐 Твоя натальная карта — это как навигатор, который подсказывает:\n"
    "– в чём твоя сила и как её раскрыть,\n"
    "– какие сферы принесут тебе рост, деньги и удовольствие,\n"
    "– и не менее важно — куда НЕ стоит лезть, даже если сейчас кажется, что «надо»."
    )
    await asyncio.sleep(3)
    await update.message.reply_text(
    "Чтобы всё это рассчитать — мне нужно знать, когда, где и во сколько ты родилась ✨\n"
    "Готова? 👇",
    reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔮 Готова")]], resize_keyboard=True)
    )
    return READY

async def ask_birth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != "🔮 Готова":
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
    "Отлично! Я получила твои данные и скажу честно: твоя карта очень нестандартная.\n"
    "🪐 Уже с первого взгляда видно: ты не из тех, кто должен «просто жить, как все». У тебя есть внутренний вектор, и когда ты идёшь против него, энергия уходит в пустоту.\n\n"
    "Готова узнать о себе больше?"
    ,
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
            max_tokens=2500,
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


