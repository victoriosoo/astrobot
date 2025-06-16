from telegram import (
    Update, ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ContextTypes, ConversationHandler
)
from datetime import datetime
import asyncio

from pdf_generator import text_to_pdf, upload_pdf_to_storage
from prompts import build_destiny_prompt

from openai_client import ask_gpt
from supabase_client import get_user, create_user, update_user

READY, DATE, TIME, LOCATION = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    name = user.first_name

    # ensure user row exists
    if not context.application.supabase.table("users").select("id").eq("tg_id", tg_id).execute().data:
        context.application.supabase.table("users").insert({"tg_id": tg_id, "name": name}).execute()

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
    context.application.supabase.table("users").update(
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
        "Готова узнать о себе больше?",
        reply_markup=ReplyKeyboardMarkup(
            [["📜 Карта предназначения"]], resize_keyboard=True
        ),
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Окей, если что — /start", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def destiny_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Карта предназначения — персональное послание о твоей миссии, талантах "
        "и сферах роста. Поможет принимать решения в гармонии с собой."       
    )
    await asyncio.sleep(3)
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
    await query.message.reply_text(
        "Отлично! Я начинаю расчёт твоей натальной карты 🌌\n"
        "Это не шаблон и не copy paste — я смотрю на твои реальные данные и составляю разбор вручную, чтобы он был точным и полезным именно для тебя.\n"
        "🕰 Это займёт несколько минут. Как только карта будет готова, я пришлю её сюда.\n\n"
        "Пока можешь налить себе чай ☕️\n"
        "А я займусь тем, чтобы твоя карта стала настоящим проводником."
    )

    tg_id = query.from_user.id
    user_res = context.application.supabase.table("users").select("*").eq("tg_id", tg_id).execute()
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
        resp = context.application.OPENAI.chat.completions.create(
            model="gpt-4-turbo",
            messages=messages,
            max_tokens=2500,
            temperature=0.9,
        )
        report_text = resp.choices[0].message.content.strip()
    except Exception as e:
        context.application.logger.error("GPT error: %s", e)
        await query.message.reply_text("Ошибка генерации. Попробуй позже.")
        return

    # generate PDF -> upload -> send
    try:
        pdf_bytes = text_to_pdf(report_text)
        public_url = upload_pdf_to_storage(u["id"], pdf_bytes)
        await query.message.reply_document(
            document=public_url,
            filename="Karta_Prednaznacheniya.pdf",
            caption=(
                "Готово! Я собрала твою натальную карту 🔮\n"
                "Вот твоя Карта Предназначения — с подсказками о том, где твои сильные стороны, "
                "на чём стоит строить реализацию и чего лучше избегать.\n\n"
                "Вперёд к лучшей версии себя!"
            ),
        )
    except Exception as e:
        context.application.logger.error("PDF/upload error: %s", e)
        await query.message.reply_text(
            "Карта готова, но файл не прикрепился 😔. Вот текст:\n\n" + report_text
        )

# Список handlers для регистрации в bot.py будет:
# start, ask_birth, ask_time, ask_location, save_profile, cancel, destiny_product, destiny_card_callback

