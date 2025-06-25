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
from prompts import build_destiny_prompt
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
        "Привет! Я Кот Астролог — твой личный проводник по звёздам 🐾\n"
        "Я не просто кот, я черный как сама космическая ночь, а ещё умею читать натальные карты.\n"
        "Мяу! Готов раскрыть твои сильные стороны, таланты и пути к успеху. Считай меня своим звездным советником.\n\n"
        "Используя твою натальную карту, помогу понять:\n"
        "– в чём твоя уникальность (да-да, даже если ты не умеешь мурчать),\n"
        "– как реализовать себя,\n"
        "– и что мешает двигаться вперёд. Ну что, готов(а) начать? 😼"
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
    update_user(
        user.id,
        birth_date=str(context.user_data["birth_date"]),
        birth_time=context.user_data["birth_time"].strftime("%H:%M"),
        birth_country=country,
        birth_city=city,
    )

    await update.message.reply_text(
        "Отлично! Я получил твои данные и скажу честно: твоя карта очень нестандартная.\n"
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
    print("CALLBACK TRIGGERED", flush=True)
    await update.message.reply_text(
        "Карта предназначения — персональное послание о твоей миссии, талантах и сферах роста. Поможет принимать решения в гармонии с собой.",
        reply_markup=ReplyKeyboardMarkup(
            [["Получить карту"]], resize_keyboard=True
        ),
    )

async def destiny_card_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем тип события — callback или обычное сообщение
    if update.callback_query is not None:
        query = update.callback_query
        await query.answer()
        tg_id = query.from_user.id
        message = query.message
    else:
        query = None
        tg_id = update.effective_user.id
        message = update.message

    print("CALLBACK TRIGGERED SECOND", flush=True)

    # Получаем пользователя из базы
    user_list = get_user(tg_id)
    if not user_list:
        await message.reply_text("Не найден профиль. Пройди /start.")
        return

    user = user_list[0]

    # Генерируем промпт для GPT
    if user.get("paid_destiny"):
        await message.reply_text(
        "Начинаю расчёт твоей натальной карты 🌌\n"
        "Это не шаблон — я использую твои реальные данные.\n"
        "🕰 Это займёт несколько минут. Как только карта будет готова, пришлю её сюда.\n\n"
        "Налей пока себе молока, ну или что там пьёшь ☕️"
        )

        messages = build_destiny_prompt(
        name=user.get("name", "Друг"),
        date=datetime.strptime(user["birth_date"], "%Y-%m-%d").strftime("%d.%m.%Y"),
        time_str=user["birth_time"],
        city=user["birth_city"],
        country=user["birth_country"],
        )
        try:
            report_text = ask_gpt(
            messages,
            model="gpt-4-turbo",
            max_tokens=4000,
            temperature=0.9,
        )
        except Exception as e:
            print("GPT error:", e)
            await message.reply_text("Ошибка генерации. Попробуй позже.")
            return

        # Генерируем PDF и отправляем
        try:
            pdf_bytes = text_to_pdf(report_text)
            public_url = upload_pdf_to_storage(user["id"], pdf_bytes)
            await message.reply_document(
            document=public_url,
            filename="Karta_Prednaznacheniya.pdf",
            caption=(
                "Готово! Я собрал твою натальную карту 🔮\n"
                "Вот твоя Карта Предназначения — с подсказками о том, где твои сильные стороны, "
                "на чём стоит строить реализацию и чего лучше избегать.\n\n"
                "Вперёд к лучшей версии себя!"
            ),
        )
        except Exception as e:
            print("PDF/upload error:", e)
            await message.reply_text(
            "Карта готова, но файл не прикрепился 😔. Вот текст:\n\n" + report_text
            )
        return

    # Если оплата не прошла — предлагаем оплатить
    success_url = "https://t.me/CosmoAstrologyBot"
    cancel_url = "https://t.me/CosmoAstrologyBot"
    checkout_url = create_checkout_session(tg_id, "destiny", success_url, cancel_url)

    await message.reply_text(
        "Чтобы получить персональный PDF-разбор, оплати продукт по ссылке ниже 👇",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("💳 Оплатить в Stripe", url=checkout_url)
        ]])
    )
    await message.reply_text(
        "⚡️ После оплаты вернись в этот чат и снова нажми кнопку «Получить карту».\n"
        "Платёж защищён. Обычно обработка занимает 1–2 минуты. "
        "Спасибо, что выбираешь CosmoAstro!"
    )


