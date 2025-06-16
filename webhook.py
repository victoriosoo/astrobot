# webhook.py
import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request
import stripe
import requests
from datetime import datetime

from supabase_client import update_user, get_user
from prompts import build_destiny_prompt
from openai_client import ask_gpt
from pdf_generator import text_to_pdf, upload_pdf_to_storage

app = Flask(__name__)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Названия для разных продуктов (ключ -> поле в Supabase)
PRODUCTS = {
    "destiny": "paid_destiny",
    "solar": "paid_solar",
    "career": "paid_career",
    # добавь новые продукты по аналогии
}

def send_start_message(tg_id, product_type):
    names = {
        "destiny": "Карта предназначения",
        "solar": "Годовой путь (соляр)",
        "career": "Доход/карьера",
        # и так далее
    }
    prod_name = names.get(product_type, "Ваш PDF-продукт")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    text = (
        f"Оплата за продукт «{prod_name}» получена! Я начинаю расчёт и подготовку файла 🌌\n"
        "Это займёт несколько минут. Как только всё будет готово, пришлю PDF прямо сюда!"
    )
    requests.post(url, data={"chat_id": tg_id, "text": text})

def send_pdf_to_user(tg_id, product_type):
    user_list = get_user(tg_id)
    if not user_list:
        return
    u = user_list[0]

    # Определи промпт и генерацию под нужный продукт
    if product_type == "destiny":
        # build prompt & call GPT для destiny
        try:
            messages = build_destiny_prompt(
                name=u.get("name", "Друг"),
                date=datetime.strptime(u["birth_date"], "%Y-%m-%d").strftime("%d.%m.%Y"),
                time_str=u["birth_time"],
                city=u["birth_city"],
                country=u["birth_country"],
            )
            report_text = ask_gpt(
                messages,
                model="gpt-4-turbo",
                max_tokens=2500,
                temperature=0.9,
            )
        except Exception as e:
            print(f"GPT error: {e}")
            return

        try:
            pdf_bytes = text_to_pdf(report_text)
            public_url = upload_pdf_to_storage(u["id"], pdf_bytes)
            user_name = u.get("name", "user").replace(" ", "_")
            birth_date = u.get("birth_date", "")
            nice_filename = f"Karta_Prednaznacheniya_{user_name}_{birth_date}.pdf"

            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
            caption = (
                "Готово! Я собрала твою натальную карту 🔮\n"
                "Вот твоя Карта Предназначения — с подсказками о том, где твои сильные стороны, "
                "на чём стоит строить реализацию и чего лучше избегать.\n\n"
                "Вперёд к лучшей версии себя!"
            )
            data = {
                "chat_id": tg_id,
                "document": public_url,
                "caption": caption,
                "filename": nice_filename
            }
            requests.post(url, data=data)
        except Exception as e:
            print(f"PDF/upload error: {e}")

    elif product_type == "solar":
        # Логика генерации для "соляр" — вставь свою генерацию
        pass

    elif product_type == "career":
        # Логика генерации для "карьера" — вставь свою генерацию
        pass

    else:
        print(f"Неизвестный тип продукта: {product_type}")

@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except Exception as e:
        print("Webhook signature error:", e)
        return str(e), 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        tg_id = session["metadata"]["tg_id"]
        product_type = session["metadata"].get("product_type", "destiny")
        paid_field = PRODUCTS.get(product_type, "paid_destiny")
        update_user(tg_id, **{paid_field: True})
        send_start_message(tg_id, product_type)
        send_pdf_to_user(tg_id, product_type)
    return "", 200

if __name__ == "__main__":
    app.run(port=5000)