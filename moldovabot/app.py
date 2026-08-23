import logging
from datetime import time as dtime

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from .config import BOT_TOKEN, MORNING_CHAT_ID
from .handlers import (
    ask,
    basic,
    beer,
    cinema,
    crypto,
    currency,
    digest,
    flights,
    fuel,
    holiday,
    joke,
    news,
    social,
    weather,
)
from .logging_setup import configure_logging
from .middleware import log_usage
from .timeutil import CHISINAU_TZ

configure_logging()
logger = logging.getLogger(__name__)


def main() -> None:
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Установи токен! Задай переменную окружения BOT_TOKEN или вставь его в код.")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Логирование — запускается первым для каждого обновления
    app.add_handler(
        MessageHandler(filters.ALL, log_usage),
        group=-1,
    )

    # Команды
    app.add_handler(CommandHandler("start", basic.start))
    app.add_handler(CommandHandler("help", basic.help_command))
    app.add_handler(CommandHandler("fact", basic.fact))
    app.add_handler(CommandHandler("anekdot", basic.anekdot))
    app.add_handler(CommandHandler("roll", basic.roll))
    app.add_handler(CommandHandler("flip", basic.flip))
    app.add_handler(CommandHandler("8ball", basic.magic_8ball))
    app.add_handler(CommandHandler("choice", basic.choice_cmd))
    app.add_handler(CommandHandler("time", basic.time_cmd))
    app.add_handler(CommandHandler("id", basic.chat_id))
    app.add_handler(CommandHandler("weather", weather.weather))
    app.add_handler(CommandHandler("mdl", currency.mdl_rate))
    app.add_handler(CommandHandler("fuel", fuel.fuel_prices))
    app.add_handler(CommandHandler("quiz", basic.quiz))
    app.add_handler(CommandHandler("crypto", crypto.crypto))
    app.add_handler(CommandHandler("altSeason", crypto.alt_season))
    app.add_handler(CommandHandler("news",      news.news))
    app.add_handler(CommandHandler("joke",      joke.joke))
    app.add_handler(CommandHandler("ask",       ask.ask))
    app.add_handler(CommandHandler("beer",      beer.beer))
    app.add_handler(CommandHandler("flights",   flights.flights))
    app.add_handler(CommandHandler("kiv",       flights.kiv))
    app.add_handler(CommandHandler("cinema",    cinema.cinema))
    app.add_handler(CallbackQueryHandler(cinema.cinema_callback, pattern=r"^cinema:"))
    app.add_handler(CommandHandler("digest",    digest.digest_cmd))
    app.add_handler(CommandHandler("holiday",   holiday.holiday))

    # ── Утренний дайджест (ежедневно в 08:00 по Кишинёву) ────────────────────
    if MORNING_CHAT_ID:
        app.job_queue.run_daily(
            digest.morning_digest,
            time=dtime(8, 0, 0, tzinfo=CHISINAU_TZ),
            chat_id=MORNING_CHAT_ID,
            name="morning_digest",
        )
        logger.info(f"📬 Morning digest scheduled at 08:00 Chisinau → chat {MORNING_CHAT_ID}")
    else:
        logger.info("📬 Morning digest disabled (MORNING_CHAT_ID not set). Use /digest manually.")

    # Новые участники
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, social.welcome_new_member))

    # Ключевые слова (только в группах)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
            social.keyword_reply,
        )
    )

    logger.info("🤖 МолдовБот запущен! Нажми Ctrl+C для остановки.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
