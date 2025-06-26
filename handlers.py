from generation import generate_and_send_destiny
from telegram import (
    Update, ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ContextTypes, ConversationHandler
)
from datetime import datetime
import asyncio

from stripe_client import create_checkout_session

from pdf_generator import text_to_pdf, upload_pdf_to_storage
from prompts import build_destiny_prompt_part1, build_destiny_prompt_part2
from openai_client import ask_gpt
from supabase_client import get_user, create_user, update_user

READY, DATE, TIME, LOCATION = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    name = user.first_name

    # ensure user row exists
    if not get_user(tg_id):
        create_user(tg_id, name)

    await update.message.reply_text(
        "Привет! Я АстроКотский — твой личный проводник по звёздам 🐾\n"
        "Я не просто кот, я черный как сама космическая ночь, а ещё умею читать натальные карты.\n"
        "Мяу! Готов раскрыть твои сильные стороны, таланты и пути к успеху. Считай меня своим звездным советником.\n\n"
        "Используя твою натальную карту, помогу понять:\n"
        "– в чём твоя уникальность (да-да, даже если ты не умеешь мурчать),\n"
        "– как реализовать себя,\n"
        "– и что мешает двигаться вперёд. Ну что, готов(а) начать? 😼"
    )
    await asyncio.sleep(2)
    await update.message.reply_text(
        "Чтобы всё это рассчитать — мне нужно знать, когда, где и во сколько ты родилась ✨\n"
        "Готова? 👇",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔮 Готова")]], resize_keyboard=True)
    )
    return READY

async def ask_birth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != "🔮 Готова":
        return READY
    await update.message.reply_text("1/3 — Давай узнаем, когда же ты появился(ась) на свет! Введи дату рождения (ДД.ММ.ГГГГ):\n"
    "(Да-да, точная дата нужна не только на паспорт, но и чтобы кот-астролог не ошибся в расчётах!)", reply_markup=ReplyKeyboardRemove())
    return DATE

async def ask_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        birth_date = datetime.strptime(update.message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        await update.message.reply_text("Хвостом чую, что-то не так с датой рождения. Напиши, пожалуйста, в формате ДД.ММ.ГГГГ (например, 02.03.1998).\nОбещаю, никому не скажу, если перепутаешь ещё раз — даже мышам!")
        return DATE
    context.user_data["birth_date"] = birth_date
    await update.message.reply_text("2/3 — А теперь время рождения (ЧЧ:ММ), пожалуйста.\n"
    "Тут уж не обманешь: для астрологического кота разница между «утром» и «ночью» — как между свежим и вчерашним кормом!")
    return TIME

async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        birth_time = datetime.strptime(update.message.text.strip(), "%H:%M").time()
    except ValueError:
        await update.message.reply_text("Что-то ты напутал с форматом! Давай попробуем ещё раз — напиши время рождения в формате 03:00.\n"
        "Не переживай, даже у котов бывают ошибки с будильником.")
        return TIME
    context.user_data["birth_time"] = birth_time
    await update.message.reply_text("3/3 — Ну и последнее! Напиши страну и город, где тебя впервые увидели звёзды (например: Латвия, Рига):\n"
    "Вдруг место рождения — секретный источник твоей кошачьей харизмы?")
    return LOCATION

async def save_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = [p.strip() for p in update.message.text.split(",")]
    if len(parts) < 2:
        await update.message.reply_text("Формат: Страна, Город. Пример: Латвия, Рига")
        return LOCATION

    country, city = parts[0], parts[1]
    user = update.effective_user
    update_user(
        user.id,
        birth_date=str(context.user_data["birth_date"]),
        birth_time=context.user_data["birth_time"].strftime("%H:%M"),
        birth_country=country,
        birth_city=city,
    )

    await update.message.reply_text(
        "Ловлю твои данные усами! Мяу — карта интересная, тут не пахнет скукой. Звёзды подсказывают, что ты явно не из тех, кто просто ходит строем за всеми.\n"
        "Если в последнее время чувствуешь, что хочешь свернуть не туда, где все топчутся, а туда, где можно вдоволь порыбачить на солнышке — всё логично, твоя энергетика не для стандартных маршрутов.\n\n"
        "Готов(а) узнать, что коты звёздного уровня увидели в твоей судьбе?",
        reply_markup=ReplyKeyboardMarkup(
            [["📜 Карта предназначения"]], resize_keyboard=True
        ),
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Окей, если что — /start", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def destiny_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("CALLBACK TRIGGERED", flush=True)
    await update.message.reply_text(
        "Карта предназначения — персональное послание о твоей миссии, талантах и сферах роста. Поможет принимать решения в гармонии с собой.",
        reply_markup=ReplyKeyboardMarkup(
            [["Получить карту"]], resize_keyboard=True
        ),
    )

async def destiny_card_callback(update, context):
    # Определяем, откуда пришёл запрос
    if update.callback_query is not None:
        query = update.callback_query
        await query.answer()
        tg_id = query.from_user.id
        message = query.message
    else:
        tg_id = update.effective_user.id
        message = update.message

    # Получаем пользователя из базы
    user_list = get_user(tg_id)
    if not user_list:
        await message.reply_text("Не найден профиль. Пройди /start.")
        return

    user = user_list[0]

    if user.get("paid_destiny"):
        # Если уже оплачено — вызываем функцию генерации и отправки карты
        application = context.application  # PTB v20+
        await generate_and_send_destiny(application, tg_id)
        return

    # Если оплата не прошла — предлагаем оплатить
    success_url = "https://t.me/CosmoAstrologyBot"
    cancel_url = "https://t.me/CosmoAstrologyBot"
    checkout_url = create_checkout_session(tg_id, "destiny", success_url, cancel_url)

    await message.reply_text(
        "Чтобы увидеть свой звёздный путь — поддержи кота-астролога парой монет на консерву! Ссылка для оплаты ниже 👇",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💳 Оплатить в Stripe", url=checkout_url)]])
    )
    await message.reply_text(
        "⚡️ После оплаты возвращайся в этот чат — PDF будет отправлен автоматически!\n"
        "Платёж под защитой, как кот под пледом. Обычно обработка занимает пару минут (успеешь налить себе молока).\n"
        "Спасибо, что поддерживаешь АстроКотского! Мяу 🐾"
    )


