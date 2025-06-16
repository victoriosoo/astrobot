import os
import stripe

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
PRICE_ID = os.getenv("STRIPE_PRICE_ID")  # Лучше вынести Price ID в .env

stripe.api_key = STRIPE_SECRET_KEY

def create_checkout_session(tg_id: int, product_type: str, success_url: str, cancel_url: str) -> str:
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price": PRICE_ID,
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
