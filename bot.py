import logging
import os
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters

from handlers import (
    start, ask_birth, ask_time, ask_location, save_profile, main_menu,
    cancel, destiny_product, solyar_product, destiny_card_callback, solyar_card_callback,
    income_product, income_card_callback,
    compatibility_product, compatibility_product_callback,
    start_compatibility, get_partner_name, get_partner_date, get_partner_time, get_partner_location,
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
    compat_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^Проверить совместимость$"), start_compatibility)],
        states={
            COMPAT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_partner_name)],
            COMPAT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_partner_date)],
            COMPAT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_partner_time)],
            COMPAT_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_partner_location)],
        },
        fallbacks=[MessageHandler(filters.Regex(r"^В главное меню$"), main_menu)],
    )
    app.add_handler(compat_conv_handler)
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Regex(r"^В главное меню$"), main_menu))
    app.add_handler(CommandHandler("menu", main_menu))
    app.add_handler(MessageHandler(filters.Regex(r"^📜 Карта предназначения$"), destiny_product))
    app.add_handler(MessageHandler(filters.Regex(r"^Получить карту$"), destiny_card_callback))
    app.add_handler(CallbackQueryHandler(destiny_card_callback, pattern=r"^destiny_card$"))
    app.add_handler(MessageHandler(filters.Regex(r"^🗺️ Годовой путь \(Соляр\)$"), solyar_product))
    app.add_handler(MessageHandler(filters.Regex(r"^Получить соляр$"), solyar_card_callback))
    app.add_handler(CallbackQueryHandler(solyar_card_callback, pattern=r"^solyar_card$"))
    app.add_handler(MessageHandler(filters.Regex(r"^💸 Карьера и доход$"), income_product))
    app.add_handler(MessageHandler(filters.Regex(r"^Получить разбор карьеры$"), income_card_callback))
    app.add_handler(CallbackQueryHandler(income_card_callback, pattern=r"^income_card$"))
    app.add_handler(MessageHandler(filters.Regex(r"^💞 Совместимость по дате рождения$"), compatibility_product))
    app.add_handler(MessageHandler(filters.Regex(r"^Проверить совместимость$"), start_compatibility))

    logger.info("Bot started")
    app.run_polling()
