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
        entry_points=[CommandHandler("start", start)],
        states={
            READY: [MessageHandler(filters.Regex(r"^🔮 Готова$"), ask_birth)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_time)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_location)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_profile)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Regex(r"^📜 Карта предназначения$"), destiny_product))
    app.add_handler(MessageHandler(filters.Regex(r"^Получить карту$"), destiny_card_callback))
    app.add_handler(CallbackQueryHandler(destiny_card_callback, pattern=r"^destiny_card$"))

    logger.info("Bot started")
    app.run_polling()
