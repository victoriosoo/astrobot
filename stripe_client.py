import os
import stripe

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
PRICE_IDS = {
    "destiny": os.getenv("STRIPE_PRICE_ID_DESTINY"),
    "solyar": os.getenv("STRIPE_PRICE_ID_SOLYAR"),
    "income": os.getenv("STRIPE_PRICE_ID_INCOME"),
    "compatibility": os.getenv("STRIPE_PRICE_ID_COMPAT"),
    # Добавишь другие продукты по аналогии
}

stripe.api_key = STRIPE_SECRET_KEY

def create_checkout_session(tg_id: int, product_type: str, success_url: str, cancel_url: str) -> str:
    price_id = PRICE_IDS.get(product_type)
    if not price_id:
        raise Exception(f"No price_id for product_type: {product_type}")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price": price_id,
            "quantity": 1,
        }],
        mode="payment",
        success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}&tg_id={tg_id}",
        cancel_url=cancel_url,
        metadata={
            "tg_id": tg_id,
            "product_type": product_type
        },
    )
    return session.url
