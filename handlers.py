from telegram import (
    Update, ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ContextTypes, ConversationHandler
)
from datetime import datetime
import asyncio
import os

from stripe_client import create_checkout_session

from pdf_generator import text_to_pdf, upload_pdf_to_storage
from prompts import build_destiny_prompt_part1, build_destiny_prompt_part2, build_solyar_prompt_part1, build_solyar_prompt_part2, build_income_prompt_part1, build_income_prompt_part2, build_compatibility_prompt_part1, build_compatibility_prompt_part2
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

    static_path = os.path.join(os.path.dirname(__file__), "static")
    animation_path = os.path.join(static_path, "cat_intro.mp4")
    await update.message.reply_animation(
        animation=open(animation_path, "rb"),
        caption=(
            "Мяу, ты на территории звёзд и котов! Я — АстроКот, твой персональный проводник по созвездиям и жизненным зигзагам. 🐾\n"
            "Не просто кот, а чёрный, как забытый пакетик валерьянки на антресолях. И да, умею читать натальные карты лучше, чем меню в рыбном ресторане.\n"
            "Готов раскрывать твои скрытые таланты, указывать, где свернуть на мягкий плед, а где проявить когти. Доверься мне — хуже уже не будет!"
        )
)

    await asyncio.sleep(2)
    await update.message.reply_text(
        "Чтобы творить магию — мне нужны твои координаты: когда, где и во сколько ты появился(ась) на свет. Без этих данных даже кот не превратит тебя в звезду!\n"
        "Ну что, готов(а) выдать тайны рождения? 👇\n\n"
        "_Если кнопка ниже не появилась — просто напиши «Готов(а)» вручную._",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🐾 Готов(а)")]], resize_keyboard=True, is_persistent=True),
        parse_mode="Markdown"
    )
    return READY

async def ask_birth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip().lower().replace("🐾", "").strip() not in ["готов", "готова", "готов(а)"]:
        return READY
    await update.message.reply_text(
    "1/3 — Раскроем первую тайну: когда ты родился(ась)? Введи дату рождения (ДД.ММ.ГГГГ):\n"
    "(Да, коту нужна не только дата для паспорта — иначе потом будешь винить меня, а не звёзды, за все свои промахи!)",
    reply_markup=ReplyKeyboardRemove()
    )
    return DATE

async def ask_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        birth_date = datetime.strptime(update.message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        await update.message.reply_text("Хвостом чую, что-то не так с датой рождения. Напиши, пожалуйста, в формате ДД.ММ.ГГГГ (например, 02.03.1998).\nОбещаю, никому не скажу, если перепутаешь ещё раз — даже мышам!")
        return DATE
    context.user_data["birth_date"] = birth_date
    await update.message.reply_text(
    "2/3 — Теперь выкладывай время появления на свет (ЧЧ:ММ), пожалуйста.\n"
    "Тут не обманешь: астрокоты отличают утро от ночи лучше любого будильника! Даже если всю ночь провёл в поисках смысла жизни под холодильником."
    )
    return TIME

async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        birth_time = datetime.strptime(update.message.text.strip(), "%H:%M").time()
    except ValueError:
        await update.message.reply_text("Что-то ты напутал с форматом! Давай попробуем ещё раз — напиши время рождения в формате 03:00.\n"
        "Не переживай, даже у котов бывают ошибки с будильником.")
        return TIME
    context.user_data["birth_time"] = birth_time
    await update.message.reply_text(
    "3/3 — Финальный штрих: страна и город, где твой звездный путь начался (например: Латвия, Рига):\n"
    "Где родился — там и пригодился. А может, и не пригодился, но коту всё равно надо знать!"
    )
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
        "Ловлю твои данные усами! Мяу — будет интересно, скучно точно не будет. Не люблю шаблоны: чувствую, что ты не из тех, кто просто идёт по следу. \n"
        "Есть у тебя врождённая тяга залезть туда, где уютно только котам. Ну что, покажем этим звёздам, кто здесь мурлыкает?"
    )
    await asyncio.sleep(2)
    await main_menu(update, context)
    return ConversationHandler.END

async def main_menu(update, context):
    await update.message.reply_text(
        "Мяу. Опять работа? А я думал, ты просто пришла меня погладить... Ну ладно, погнали звёзды поразбираем.",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["📜 Карта предназначения"],["🗺️ Годовой путь"],
                ["💸 Карьера и доход"],["💞 Совместимость по дате рождения"]
            ],
            resize_keyboard=True,is_persistent=True
        ),
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Окей, если что — /start", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def destiny_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("CALLBACK TRIGGERED", flush=True)
    await update.message.reply_text(
        "Карта предназначения — это не просто бумажка с красивыми словами, а настоящий кото-компас по твоей судьбе!\n"
        "С ней ты узнаешь, какие таланты у тебя в лапах с рождения, где прячутся твои внутренние резервы и как выбраться из любой жизненной коробки, даже если она кажется слишком тесной.\n"
        "Эта карта — твой личный путеводитель: расскажет, куда стоит выпустить когти, а куда лучше идти, мягко ступая по мохнатой дорожке.\n"
        "Ну что, готов(а) узнать, куда тебя зовут звёзды и кото-астролог?"
        "\n\nСтоимость разбора — 4.99€. Оплата будет предложена после подтверждения.",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["Получить карту"],
                ["В главное меню"]            
            ], resize_keyboard=True,is_persistent=True
        ),
    )

async def solyar_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🗺️ Годовой путь  — твой персональный астропрогноз на ближайший год!\n"
        "Путь покажет:\n"
        "• Главную тему и задачу года\n"
        "• В каких сферах тебя ждёт рост, а где — вызовы\n"
        "• Предупреждения, кризисы и лучшие месяцы для действий\n"
        "• Когда лучше начинать важные проекты, а когда отдыхать и набираться сил\n"
        "• Энергетические спады и точки перезагрузки\n\n"
        "Это как подробная карта, где отмечены главные дороги, повороты и даже кошачьи тропки, ведущие к успеху! 🐾\n\n"
        "Готов(а) узнать свой путь на год вперёд?"
        "\n\nСтоимость разбора — 4.99€. Оплата будет предложена после подтверждения.",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["Получить годовой разбор"],
                ["В главное меню"]
            ],
            resize_keyboard=True,is_persistent=True
        ),
    )
async def income_product(update, context):
    await update.message.reply_text(
        "💸 Карьера и доход — астрологический разбор твоих финансовых талантов, блоков и перспектив!\n"
        "Что внутри:\n"
        "• Общий потенциал по деньгам и карьере\n"
        "• Финансовые установки и денежное мышление\n"
        "• Оптимальный стиль работы: фриланс, найм, бизнес\n"
        "• Карьерный вектор: куда идти, где поддержка\n"
        "• Лучшие месяцы для изменений, повышения, запусков\n"
        "• Главные блоки — что мешает расти\n"
        "• Персональные рекомендации и мини-чеклист\n\n"
        "Почувствуй, что контролируешь свой доход и карьеру, а не просто плывёшь по течению. Мяу!\n\n"
        "Готов(а) узнать разбор своей денежной карты?"
        "\n\nСтоимость разбора — 4.99€. Оплата будет предложена после подтверждения.",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["Получить разбор карьеры"],
                ["В главное меню"]
            ],
            resize_keyboard=True,is_persistent=True
        ),
    )
async def compatibility_product(update, context):
    await update.message.reply_text(
        "Совместимость по дате рождения — это не просто штамп «подходите или нет», а кото-раскладка на ваши отношения, где каждая полоска шерсти имеет значение!\n"
        "Этот разбор покажет, какие эмоции у вас в лапах, кто мурлычет от заботы, а кто иногда шипит от недопонимания. Я изучу ваши звёздные астропрофили: найду, где искра притяжения, а где можно запутаться в клубке противоречий.\n"
        "Вы узнаете, как гармонично вместе обустроить свой кошачий уют, что может быть камнем преткновения, и как вместе обойти лужи недопонимания.\n"
        "Разбор даст не только картину ваших характеров, но и конкретные подсказки: когда погладить друг друга против шерсти, а когда вместе прыгать за одной мечтой. Мяу!\n\n"
        "Ну что, готов(а) узнать, что на самом деле связывает ваши звёзды и куда кото-астролог советует направить свои усы?"
        "\n\nСтоимость разбора — 4.99€. Оплата будет предложена после подтверждения.",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["Проверить совместимость"],
                ["В главное меню"]
            ],
            resize_keyboard=True,is_persistent=True
        ),
    )

async def destiny_card_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from prompts import build_destiny_prompt_part1, build_destiny_prompt_part2
    from supabase_client import update_user

    # Определяем тип события
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

    user_list = get_user(tg_id)
    if not user_list:
        await message.reply_text("Не найден профиль. Пройди /start.")
        return

    user = user_list[0]

    # --- ЕСЛИ ПРОДУКТ ОПЛАЧЕН ---
    if user.get("paid_destiny"):
        # Если есть сохранённая ссылка на PDF — присылаем тот же файл!
        if user.get("destiny_pdf_url"):
            await message.reply_document(
                document=user["destiny_pdf_url"],
                filename="Karta_Prednaznacheniya.pdf",
                caption=(
                    "Мяу, миссия выполнена! Вот твоя личная натальная карта — не сырая копия из интернета, а настоящий кото-разбор с характером.\n"
                    "Изучи внимательно, мурлыкни благодарность звёздам и помни — даже самая мудрая кошка иногда промахивается, но всегда падает на лапы. Вперёд к своему предназначению!"
                ),
            )
            await asyncio.sleep(2)
            await message.reply_text(
                "Захочешь посмотреть другие кото-разборы — возвращайся в главное меню. Я тут, если что, не сплю!",
                reply_markup=ReplyKeyboardMarkup([["В главное меню"]], resize_keyboard=True,is_persistent=True)
            )
            return

        # Если оплачен, но файла нет (старые юзеры, миграция) — генерим PDF и сохраняем ссылку
        await message.reply_text(
            "Мяу! Приступаю к разгадыванию твоей звёздной судьбы — буду колдовать над натальной картой лично, лапой на сердце!\n"
            "Это не очередной шаблон с балкона — всё строго по твоим данным, как и полагается уважающему себя коту-астрологу.\n"
            "Наберись терпения, займёт пару минут... А пока налей себе молока (или, на крайний случай, чаю), расслабь хвост и помурлыкай о чём-нибудь хорошем. Скоро вернусь с результатами!"
        )
        loading_msg = await message.reply_animation(
            animation=open("static/loading_cat2.gif", "rb"),
            caption="⏳ Готовлю твой годовой путь... Сейчас будет волшебство!"
)

        prompt_args = dict(
            name=user.get("name", "Друг"),
            date=datetime.strptime(user["birth_date"], "%Y-%m-%d").strftime("%d.%m.%Y"),
            time_str=user["birth_time"],
            city=user["birth_city"],
            country=user["birth_country"],
        )
        try:
            messages1 = build_destiny_prompt_part1(**prompt_args)
            report_part1 = ask_gpt(messages1, model="gpt-4-turbo", max_tokens=2500, temperature=0.9)
            messages2 = build_destiny_prompt_part2(**prompt_args)
            report_part2 = ask_gpt(messages2, model="gpt-4-turbo", max_tokens=2500, temperature=0.9)
            report_text = report_part1.strip() + "\n\n" + report_part2.strip()
        except Exception as e:
            print("GPT error:", e)
            await loading_msg.delete()
            await message.reply_text("Ошибка генерации. Попробуй позже.")
            return

        try:
            pdf_bytes = text_to_pdf(report_text)
            public_url = upload_pdf_to_storage(user["id"], pdf_bytes)
            # Сохраняем ссылку в базе
            update_user(user["tg_id"], destiny_pdf_url=public_url)
            await loading_msg.delete()
            await message.reply_document(
                document=public_url,
                filename="Karta_Prednaznacheniya.pdf",
                caption=(
                    "Мяу, миссия выполнена! Вот твоя личная натальная карта — не сырая копия из интернета, а настоящий кото-разбор с характером.\n"
                    "Изучи внимательно, мурлыкни благодарность звёздам и помни — даже самая мудрая кошка иногда промахивается, но всегда падает на лапы. Вперёд к своему предназначению!"
                ),
            )
            await asyncio.sleep(2)
            await message.reply_text(
                "Захочешь посмотреть другие кото-разборы — возвращайся в главное меню. Я тут, если что, не сплю!",
                reply_markup=ReplyKeyboardMarkup([["В главное меню"]], resize_keyboard=True,is_persistent=True)
            )
        except Exception as e:
            print("PDF/upload error:", e)
            await loading_msg.delete()
            from io import BytesIO
            text_io = BytesIO(report_text.encode("utf-8"))
            text_io.name = "destiny.txt"
            text_io.seek(0)
            await message.reply_document(
                document=text_io,
                filename="destiny.txt",
                caption="Карта готова, но PDF не прикрепился. Вот текст:"
            )
        return

    # --- ЕСЛИ ПРОДУКТ НЕ ОПЛАЧЕН ---
    success_url = "https://t.me/CosmoAstrologyBot"
    cancel_url = "https://t.me/CosmoAstrologyBot"
    checkout_url = create_checkout_session(tg_id, "destiny", success_url, cancel_url)

    await message.reply_text(
        "Стоимость: 4.99€. Чтобы увидеть свой звёздный путь — поддержи кота-астролога парой монет на консерву! Ссылка для оплаты ниже 👇",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("💳 Оплатить в Stripe", url=checkout_url)
        ]])
    )
    await message.reply_text(
        "⚡️ После оплаты возвращайся в этот чат и снова жми «Получить карту» — я уже буду мурлыкать в ожидании!\n"
        "Платёж под защитой, как кот под пледом. Обычно обработка занимает пару минут (успеешь налить себе молока).\n"
        "Спасибо, что поддерживаешь АстроКотского! Мяу 🐾"
    )

async def solyar_card_callback(update, context):
    from prompts import build_solyar_prompt_part1, build_solyar_prompt_part2
    from supabase_client import update_user

    if update.callback_query is not None:
        query = update.callback_query
        await query.answer()
        tg_id = query.from_user.id
        message = query.message
    else:
        query = None
        tg_id = update.effective_user.id
        message = update.message

    user_list = get_user(tg_id)
    if not user_list:
        await message.reply_text("Не найден профиль. Пройди /start.")
        return

    user = user_list[0]

    # Если куплен и есть ссылка — сразу отдаём PDF
    if user.get("paid_solyar") and user.get("solyar_pdf_url"):
        await message.reply_document(
            document=user["solyar_pdf_url"],
            filename="Solyar_Report.pdf",
            caption=(
                "Мяу, всё готово! Вот твой личный прогноз на год — разбор от АстроКотского. Изучи внимательно, найди сильные и сложные периоды, и помни: твой год — это территория для свершений.\n"
                "Если тебе вдруг станет скучно — можешь перечитать этот разбор. Хотя, между нами, я бы лучше поспал."
            ),
        )
        await asyncio.sleep(2)
        await message.reply_text(
            "Захочешь посмотреть другие кото-разборы — возвращайся в главное меню. Я тут, если что, не сплю!",
            reply_markup=ReplyKeyboardMarkup([["В главное меню"]], resize_keyboard=True,is_persistent=True)
        )
        return

    if user.get("paid_solyar"):
        await message.reply_text(
            "Мяу! Я начинаю собирать твой годовой путь — это не просто прогноз, а твой личный астрологический навигатор на ближайший год. Хвостиком чувствую: получится что-то особенное!"
        )
        
        loading_msg = await message.reply_video(
            video=open("static/loading_cat.mp4", "rb"),
            caption="⏳ Обрабатываю твой годовой путь... Подожди минутку, кот-астролог колдует над звёздами!"
        )

        prompt_args = dict(
            name=user.get("name", "Друг"),
            date=datetime.strptime(user["birth_date"], "%Y-%m-%d").strftime("%d.%m.%Y"),
            time_str=user["birth_time"],
            city=user["birth_city"],
            country=user["birth_country"],
        )

        try:
            messages1 = build_solyar_prompt_part1(**prompt_args)
            report_part1 = ask_gpt(messages1, model="gpt-4-turbo", max_tokens=2500, temperature=0.9)
            messages2 = build_solyar_prompt_part2(**prompt_args)
            report_part2 = ask_gpt(messages2, model="gpt-4-turbo", max_tokens=2500, temperature=0.9)
            report_text = report_part1.strip() + "\n\n" + report_part2.strip()
        except Exception as e:
            print("GPT error:", e)
            await loading_msg.delete()
            await message.reply_text("Ошибка генерации. Попробуй позже.")
            return

        try:
            pdf_bytes = text_to_pdf(report_text, product_type="solyar")
            public_url = upload_pdf_to_storage(user["id"], pdf_bytes)
            update_user(user["tg_id"], solyar_pdf_url=public_url)
            await loading_msg.delete()
            await message.reply_document(
                document=public_url,
                filename="Solyar_Report.pdf",
                caption="Мяу, всё готово! Вот твой личный прогноз на год — разбор от АстроКотского. Изучи внимательно, найди сильные и сложные периоды, и помни: твой год — это территория для свершений."
            )
            await asyncio.sleep(2)
            await message.reply_text(
                "Захочешь посмотреть другие кото-разборы — возвращайся в главное меню. Я тут, если что, не сплю!",
                reply_markup=ReplyKeyboardMarkup([["В главное меню"]], resize_keyboard=True,is_persistent=True)
            )
        except Exception as e:
            print("PDF/upload error:", e)
            await loading_msg.delete()
            from io import BytesIO
            text_io = BytesIO(report_text.encode("utf-8"))
            text_io.name = "solyar.txt"
            text_io.seek(0)
            await message.reply_document(
                document=text_io,
                filename="solyar.txt",
                caption="Разбор готов, но PDF не прикрепился. Вот текст:"
            )
        return

    # Если не оплачен — предлагай оплатить
    success_url = "https://t.me/CosmoAstrologyBot"
    cancel_url = "https://t.me/CosmoAstrologyBot"
    checkout_url = create_checkout_session(tg_id, "solyar", success_url, cancel_url)

    await message.reply_text(
        "Годовой путь — Стоимость: 4.99€. Поддержи кота-астролога парой монет и получи персональный навигатор по твоему году. Оплата ниже 👇",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💳 Оплатить в Stripe", url=checkout_url)]])
    )
    await message.reply_text(
        "⚡️ После оплаты возвращайся и снова жми «Получить годовой разбор». Всё сделаю быстро и по-честному. Мяу 🐾"
    )

async def income_card_callback(update, context):
    from prompts import build_income_prompt_part1, build_income_prompt_part2
    from supabase_client import update_user

    if update.callback_query is not None:
        query = update.callback_query
        await query.answer()
        tg_id = query.from_user.id
        message = query.message
    else:
        query = None
        tg_id = update.effective_user.id
        message = update.message

    user_list = get_user(tg_id)
    if not user_list:
        await message.reply_text("Не найден профиль. Пройди /start.")
        return

    user = user_list[0]

    # Если куплен и есть ссылка — сразу отдаём PDF
    if user.get("paid_income") and user.get("income_pdf_url"):
        await message.reply_document(
            document=user["income_pdf_url"],
            filename="Income_Report.pdf",
            caption="Вот твой астрологический разбор по деньгам и карьере! Тут написано всё, что нужно. Если что не так — кидай валерьянку, буду думать ещё."
        )
        await asyncio.sleep(2)
        await message.reply_text(
            "Захочешь посмотреть другие кото-разборы — возвращайся в главное меню. Я тут, если что, не сплю!",
            reply_markup=ReplyKeyboardMarkup([["В главное меню"]], resize_keyboard=True,is_persistent=True)
        )
        return

    if user.get("paid_income"):
        await message.reply_text(
            "Мяу! Делаю разбор по деньгам и карьере. Хвостом чую: сейчас тебе откроются новые горизонты!"
        )
        loading_msg = await message.reply_animation(
            animation=open("static/loading_cat2.gif", "rb"),
            caption="⏳ Готовлю твой годовой путь... Сейчас будет волшебство!"
            )

        prompt_args = dict(
            name=user.get("name", "Друг"),
            date=datetime.strptime(user["birth_date"], "%Y-%m-%d").strftime("%d.%m.%Y"),
            time_str=user["birth_time"],
            city=user["birth_city"],
            country=user["birth_country"],
        )

        try:
            messages1 = build_income_prompt_part1(**prompt_args)
            report_part1 = ask_gpt(messages1, model="gpt-4-turbo", max_tokens=2500, temperature=0.9)
            messages2 = build_income_prompt_part2(**prompt_args)
            report_part2 = ask_gpt(messages2, model="gpt-4-turbo", max_tokens=2500, temperature=0.9)
            report_text = report_part1.strip() + "\n\n" + report_part2.strip()
        except Exception as e:
            print("GPT error:", e)
            await loading_msg.delete()
            await message.reply_text("Ошибка генерации. Попробуй позже.")
            return

        try:
            pdf_bytes = text_to_pdf(report_text, product_type="income")
            public_url = upload_pdf_to_storage(user["id"], pdf_bytes)
            update_user(user["tg_id"], income_pdf_url=public_url)
            await loading_msg.delete()
            await message.reply_document(
                document=public_url,
                filename="Income_Report.pdf",
                caption="Вот твой астрологический разбор по деньгам и карьере! Тут написано всё, что нужно. Если что не так — кидай валерьянку, буду думать ещё."
            )
            await asyncio.sleep(2)
            await message.reply_text(
                "Захочешь посмотреть другие кото-разборы — возвращайся в главное меню. Я тут, если что, не сплю!",
                reply_markup=ReplyKeyboardMarkup([["В главное меню"]], resize_keyboard=True,is_persistent=True)
            )
        except Exception as e:
            print("PDF/upload error:", e)
            await loading_msg.delete()
            from io import BytesIO
            text_io = BytesIO(report_text.encode("utf-8"))
            text_io.name = "income.txt"
            text_io.seek(0)
            await message.reply_document(
                document=text_io,
                filename="income.txt",
                caption="Разбор готов, но PDF не прикрепился. Вот текст:"
            )
        return

    # Если не оплачен — предлагай оплатить
    success_url = "https://t.me/CosmoAstrologyBot"
    cancel_url = "https://t.me/CosmoAstrologyBot"
    checkout_url = create_checkout_session(tg_id, "income", success_url, cancel_url)

    await message.reply_text(
        "Карьерный разбор — Стоимость: 4.99€. Поддержи кота-астролога и получи свой персональный денежный разбор! Оплата ниже 👇",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💳 Оплатить в Stripe", url=checkout_url)]]),
    )
    await message.reply_text(
        "⚡️ После оплаты возвращайся и снова жми «Получить разбор карьеры». Всё сделаю быстро и по-честному. Мяу 🐾"
    )
COMPAT_NAME, COMPAT_DATE, COMPAT_TIME, COMPAT_LOCATION = range(100, 104)  # значения для новой цепочки

async def start_compatibility(update, context):
    await update.message.reply_text(
        "Введи имя или пометку для второго человека (например, «Виктор» или «Партнёр»):",
        reply_markup=ReplyKeyboardRemove()
    )
    return COMPAT_NAME

async def get_partner_name(update, context):
    context.user_data["partner_name"] = update.message.text.strip()
    await update.message.reply_text("Теперь введи дату рождения партнёра (ДД.ММ.ГГГГ):")
    return COMPAT_DATE

async def get_partner_date(update, context):
    try:
        context.user_data["partner_birth_date"] = datetime.strptime(update.message.text.strip(), "%d.%m.%Y").date()
        await update.message.reply_text("Время рождения партнёра (ЧЧ:ММ) или напиши «не знаю»:")
        return COMPAT_TIME
    except Exception:
        await update.message.reply_text("Формат даты не распознан. Пример: 15.01.1992")
        return COMPAT_DATE

async def get_partner_time(update, context):
    t = update.message.text.strip()
    if t.lower() == "не знаю":
        context.user_data["partner_birth_time"] = None
    else:
        try:
            context.user_data["partner_birth_time"] = datetime.strptime(t, "%H:%M").time()
        except Exception:
            await update.message.reply_text("Формат времени не распознан. Пример: 08:30 или напиши «не знаю»")
            return COMPAT_TIME
    await update.message.reply_text("Страна и город рождения партнёра (например: Россия, Москва) или «не знаю»:")
    return COMPAT_LOCATION

async def get_partner_location(update, context):
    text = update.message.text.strip()
    if text.lower() == "не знаю":
        context.user_data["partner_country"] = None
        context.user_data["partner_city"] = None
    else:
        parts = [p.strip() for p in text.split(",")]
        context.user_data["partner_country"] = parts[0] if len(parts) > 0 else None
        context.user_data["partner_city"] = parts[1] if len(parts) > 1 else None
    # Дальше — сразу генерация PDF!
    await generate_compatibility_pdf(update, context)
    return ConversationHandler.END

async def compatibility_card_callback(update, context):
    user_tg = update.effective_user
    user_db = get_user(user_tg.id)[0]

    # 1. Если оплачен и есть готовый PDF — сразу присылаем!
    if user_db.get("paid_compatibility") and user_db.get("compatibility_pdf_url"):
        await update.message.reply_document(
            document=user_db["compatibility_pdf_url"],
            filename="Compatibility_Report.pdf",
            caption="Всё предсказал, как мог. Остальное — к звёздам (или к психотерапевту)."
        )
        await asyncio.sleep(2)
        await main_menu(update, context)
        return ConversationHandler.END

    # 2. Если НЕ оплачено — предлагаем оплатить
    if not user_db.get("paid_compatibility"):
        success_url = "https://t.me/CosmoAstrologyBot"
        cancel_url = "https://t.me/CosmoAstrologyBot"
        checkout_url = create_checkout_session(user_tg.id, "compatibility", success_url, cancel_url)
        await update.message.reply_text(
            "Стоимость: 4.99€. Поддержи кота-астролога и получи разбор совместимости по дате рождения! Оплата ниже 👇",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💳 Оплатить в Stripe", url=checkout_url)]])
        )
        await update.message.reply_text(
            "После оплаты снова нажми «Проверить совместимость», чтобы ввести данные партнёра.",
            reply_markup=ReplyKeyboardMarkup(
                [["Проверить совместимость"], ["В главное меню"]],
                resize_keyboard=True,is_persistent=True
            )
        )
        return ConversationHandler.END

    # 3. Если оплачено, но PDF ещё не был сгенерен — запускаем сбор данных о партнёре
    await update.message.reply_text(
        "Введи имя или пометку для второго человека (например, «Виктор» или «Партнёр»):",
        reply_markup=ReplyKeyboardRemove()
    )
    return COMPAT_NAME

async def generate_compatibility_pdf(update, context):
    user_tg = update.effective_user
    user_db = get_user(user_tg.id)[0]

    user = {
        "name": user_db.get("name", "Клиент"),
        "birth_date": datetime.strptime(user_db["birth_date"], "%Y-%m-%d").strftime("%d.%m.%Y"),
        "birth_time": user_db.get("birth_time"),
        "birth_city": user_db.get("birth_city"),
        "birth_country": user_db.get("birth_country"),
    }
    partner = {
        "name": context.user_data.get("partner_name", "Партнёр"),
        "birth_date": context.user_data.get("partner_birth_date").strftime("%d.%m.%Y"),
        "birth_time": context.user_data.get("partner_birth_time"),
        "birth_city": context.user_data.get("partner_city"),
        "birth_country": context.user_data.get("partner_country"),
    }

    await update.message.reply_text(
        "Мяу! Начинаю разбор совместимости. Лапы чешутся узнать всё про ваши звёзды — жди подробный PDF!"
    )
    loading_msg = await update.message.reply_video(
        video=open("static/loading_cat.mp4", "rb"),
        caption="⏳ Обрабатываю твою совместимость с партнёром... Подожди минутку, кот-астролог колдует над звёздами!"
    )

    try:
        messages1 = build_compatibility_prompt_part1(user, partner)
        report_part1 = ask_gpt(messages1, model="gpt-4-turbo", max_tokens=2500, temperature=0.9)
        messages2 = build_compatibility_prompt_part2(user, partner)
        report_part2 = ask_gpt(messages2, model="gpt-4-turbo", max_tokens=2500, temperature=0.9)
        report_text = report_part1.strip() + "\n\n" + report_part2.strip()
    except Exception as e:
        print("GPT error:", e)
        await loading_msg.delete()
        await update.message.reply_text("Ошибка генерации. Попробуй позже.")
        return

    try:
        pdf_bytes = text_to_pdf(report_text, product_type="compatibility")
        public_url = upload_pdf_to_storage(user_db["id"], pdf_bytes)
        update_user(user_db["tg_id"], compatibility_pdf_url=public_url)
        await loading_msg.delete()
        await update.message.reply_document(
            document=public_url,
            filename="Compatibility_Report.pdf",
            caption="Всё предсказал, как мог. Остальное — к звёздам (или к психотерапевту)."
        )
        await asyncio.sleep(2)
        await update.message.reply_text(
            "Захочешь получить другие кото-разборы — возвращайся в главное меню. Я тут, если что, не сплю!",
            reply_markup=ReplyKeyboardMarkup([["В главное меню"]], resize_keyboard=True,is_persistent=True)
)
    except Exception as e:
        print("PDF/upload error:", e)
        await loading_msg.delete()
        from io import BytesIO
        text_io = BytesIO(report_text.encode("utf-8"))
        text_io.name = "compatibility.txt"
        text_io.seek(0)
        await update.message.reply_document(
            document=text_io,
            filename="compatibility.txt",
            caption="Совместимость готова, но PDF не прикрепился. Вот полный текст:"
        )