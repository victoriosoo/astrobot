import logging
import os
from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

from handlers import (
    start,
    ask_birth,
    ask_time,
    ask_location,
    save_profile,
    cancel,
    destiny_product,
    destiny_card_callback,
    DATE,
    TIME,
    LOCATION,
)

load_dotenv()
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main() -> None:
    """Entry point for the bot."""
    app = ApplicationBuilder().token(TG_TOKEN).build()

    # /start only greets the user and shows the inline "Ready" button.
    app.add_handler(CommandHandler("start", start))

    # Conversation that begins after the user presses the "Ready" button.
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_birth, pattern="^ready$")],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_time)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_location)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_profile)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv_handler)

    # Additional inline‑button callbacks that are not part of the main conversation.
    app.add_handler(CallbackQueryHandler(destiny_product, pattern="^product_destiny$"))
    app.add_handler(CallbackQueryHandler(destiny_card_callback, pattern="^destiny_card$"))

    logger.info("Bot started and polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
