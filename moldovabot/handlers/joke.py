import logging

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Случайная шутка через JokeAPI (без ключа)."""
    # safe=true исключает тёмные/расистские шутки
    url = (
        "https://v2.jokeapi.dev/joke/Programming,Misc,Pun"
        "?lang=en&safe-mode&type=twopart,single"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                data = await resp.json()

        if data.get("type") == "twopart":
            msg = (
                f"😂 <b>Шутка:</b>\n\n"
                f"{data['setup']}\n\n"
                f"<tg-spoiler>👉 {data['delivery']}</tg-spoiler>"
            )
        else:
            msg = f"😂 <b>Шутка:</b>\n\n{data.get('joke', '...')}"

        category = data.get("category", "")
        if category:
            msg += f"\n\n<i>Категория: {category}</i>"

    except Exception as e:
        logger.warning(f"JokeAPI error: {e}")
        msg = "⚠️ Не удалось получить шутку. Попробуй позже!"

    await update.message.reply_html(msg)
