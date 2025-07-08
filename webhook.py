import os
import stripe
from flask import Flask, request
from supabase_client import get_user, update_user

PRODUCTS = {
    "destiny": "paid_destiny",
    "solyar": "paid_solyar",
    "blocks": "paid_blocks",
    "income": "paid_income",
    "compatibility": "paid_compatibility"
    # Добавь другие продукты при необходимости
}

WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

app = Flask(__name__)

@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("stripe-signature")
    print("=== STRIPE WEBHOOK RAW PAYLOAD ===")
    try:
        print(payload.decode())
    except Exception:
        print("[WEBHOOK] Could not decode payload as utf-8.")
    print("=== END EVENT ===")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except Exception as e:
        print("Webhook signature error:", e)
        return str(e), 400

    try:
        print(f"[WEBHOOK] Parsed event type: {event['type']}")
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            print(f"[WEBHOOK] session['metadata']: {session.get('metadata')}")
            # Защитно достаём tg_id
            tg_id_raw = session.get("metadata", {}).get("tg_id")
            if not tg_id_raw:
                print("[WEBHOOK] No tg_id in metadata! Cannot continue.")
                return "", 200
            try:
                tg_id = int(tg_id_raw)
            except Exception:
                print(f"[WEBHOOK] Can't cast tg_id ({tg_id_raw}) to int!")
                return "", 200

            product_type = session.get("metadata", {}).get("product_type", "destiny")
            paid_field = PRODUCTS.get(product_type, "paid_destiny")
            print(f"[WEBHOOK] Will update_user(tg_id={tg_id}, {paid_field}=True)")

            # Проверяем наличие пользователя
            user = get_user(tg_id)
            print(f"[WEBHOOK] Supabase user lookup for tg_id={tg_id}: {user}")
            if not user:
                print(f"[WEBHOOK] User with tg_id={tg_id} NOT FOUND in supabase. Update skipped!")
                return "", 200

            # Делаем апдейт
            try:
                result = update_user(tg_id, **{paid_field: True})
                print(f"[WEBHOOK] update_user result: {result}")
            except Exception as e:
                print(f"[WEBHOOK] update_user exception: {e}")

    except Exception as e:
        import traceback
        print("Webhook handling error:", e)
        traceback.print_exc()
        # Всегда возвращаем 200, чтобы Stripe не спамил повторно!
        return "", 200

    return "", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)