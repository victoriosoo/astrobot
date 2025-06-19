import logging
import os
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters

from handlers import (
    start, ask_birth, ask_time, ask_location, save_profile,
    cancel, destiny_product, destiny_card_callback,
    READY, DATE, TIME, LOCATION
)

load_dotenv()
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TG_TOKEN).build()

    conv_handler = ConversationHandler(
    # 1️⃣  Два entry-point’а: /start И нажатие «ready»
    entry_points=[
        CommandHandler("start", start),
        CallbackQueryHandler(ask_birth, pattern="^ready$"),
    ],
    states={
        DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_time)],
        TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_location)],
        LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_profile)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

    app.add_handler(CallbackQueryHandler(destiny_product, pattern="^product_destiny$"))
    app.add_handler(CallbackQueryHandler(destiny_card_callback, pattern="^destiny_card$"))
    app.add_handler(conv_handler)

    logger.info("Bot started")
    app.run_polling()
