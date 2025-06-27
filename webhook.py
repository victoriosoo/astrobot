import os
import stripe
from flask import Flask, request

from supabase_client import update_user  # Импортируй свою функцию для обновления пользователя

# Маппинг типов продуктов в нужное поле Supabase
PRODUCTS = {
    "destiny": "paid_destiny",
    "solyar": "paid_solyar",
    "blocks": "paid_blocks",
    "income": "paid_income",
    # Добавь другие продукты при необходимости
}

WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

app = Flask(__name__)

@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except Exception as e:
        print("Webhook signature error:", e)
        return str(e), 400

    try:
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            tg_id = session["metadata"]["tg_id"]
            product_type = session["metadata"].get("product_type", "destiny")
            paid_field = PRODUCTS.get(product_type, "paid_destiny")

            print(f"[WEBHOOK] Received payment: tg_id={tg_id}, product_type={product_type} (set {paid_field}=True)")
            update_user(tg_id, **{paid_field: True})
            # Никакой отправки PDF, никаких Telegram API вызовов!
    except Exception as e:
        import traceback
        print("Webhook handling error:", e)
        traceback.print_exc()
        # Всё равно всегда возвращай 200, чтобы Stripe не спамил повторно!
        return "", 200

    return "", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
