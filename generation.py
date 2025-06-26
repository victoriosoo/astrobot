# generation.py
from pdf_generator import text_to_pdf, upload_pdf_to_storage
from prompts import build_destiny_prompt_part1, build_destiny_prompt_part2
from openai_client import ask_gpt
from supabase_client import get_user
from telegram.constants import ParseMode
from datetime import datetime

async def generate_and_send_destiny(application, tg_id):
    # Получаем пользователя
    user_list = get_user(tg_id)
    if not user_list:
        return
    user = user_list[0]
    
    # Подготовка промпта
    prompt_args = dict(
        name=user.get("name", "Друг"),
        date=datetime.strptime(user["birth_date"], "%Y-%m-%d").strftime("%d.%m.%Y"),
        time_str=user["birth_time"],
        city=user["birth_city"],
        country=user["birth_country"],
    )
    try:
        messages1 = build_destiny_prompt_part1(**prompt_args)
        report_part1 = ask_gpt(
            messages1,
            model="gpt-4-turbo",
            max_tokens=2500,
            temperature=0.9,
        )
        messages2 = build_destiny_prompt_part2(**prompt_args)
        report_part2 = ask_gpt(
            messages2,
            model="gpt-4-turbo",
            max_tokens=2500,
            temperature=0.9,
        )
        report_text = report_part1.strip() + "\n\n" + report_part2.strip()
    except Exception as e:
        print("GPT error:", e)
        return

    # Генерим PDF
    try:
        pdf_bytes = text_to_pdf(report_text)
        public_url = upload_pdf_to_storage(user["id"], pdf_bytes)
    except Exception as e:
        print("PDF/upload error:", e)
        public_url = None

    # Отправляем текст "мяу приступаю к разгадыванию..." + PDF
    try:
        await application.bot.send_message(
            chat_id=tg_id,
            text=(
                "Мяу! Приступаю к разгадыванию твоей звёздной судьбы — буду колдовать над натальной картой лично, лапой на сердце!\n"
                "Это не очередной шаблон с балкона — всё строго по твоим данным, как и полагается уважающему себя коту-астрологу.\n"
                "Наберись терпения, займёт пару минут... А пока налей себе молока (или, на крайний случай, чаю), расслабь хвост и помурлыкай о чём-нибудь хорошем. Скоро вернусь с результатами!"
            ),
        )
        if public_url:
            await application.bot.send_document(
                chat_id=tg_id,
                document=public_url,
                filename="Karta_Prednaznacheniya.pdf",
                caption=(
                    "Мяу, миссия выполнена! Вот твоя личная натальная карта — не сырая копия из интернета, а настоящий кото-разбор с характером.\n"
                    "Здесь ты найдёшь подсказки, куда стоит направить свои когти, в чём твои сильные стороны и каких ловушек судьбы лучше избегать.\n\n"
                    "Изучи внимательно, мурлыкни благодарность звёздам и помни — даже самая мудрая кошка иногда промахивается, но всегда падает на лапы. Вперёд к своему предназначению!"
                ),
            )
        else:
            await application.bot.send_message(
                chat_id=tg_id,
                text="Карта готова, но файл не прикрепился 😔. Вот текст:\n\n" + report_text,
            )
    except Exception as e:
        print("Telegram send error:", e)