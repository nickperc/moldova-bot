import random

from telegram import Update
from telegram.ext import ContextTypes

from ..data import MOLDOVA_FACTS


async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветствовать новых участников группы."""
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        name = member.first_name
        msg = (
            f"🎉 Добро пожаловать в чат, <b>{name}</b>!\n\n"
            "🇲🇩 Мы рады видеть тебя здесь!\n"
            f"Кстати, знаешь ли ты, что: {random.choice(MOLDOVA_FACTS)}\n\n"
            "Напиши /help чтобы узнать, что умею я — <b>МолдовБот</b>! 🤖"
        )
        await update.message.reply_html(msg)


async def keyword_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Реагировать на ключевые слова в сообщениях."""
    text = update.message.text.lower() if update.message.text else ""

    if "вино" in text or "wine" in text:
        responses = [
            "🍷 Вино сказал? Молдова одобряет!",
            "🍇 А у нас в Крикова есть 120 км винных туннелей — это ли не счастье?",
            "🥂 Вино — это поэзия в бутылке, как говорят у нас в Молдове!",
        ]
        await update.message.reply_text(random.choice(responses))

    elif "мамалыга" in text:
        await update.message.reply_text(
            "🍽️ Мамалыга — это не просто каша, это душа Молдовы! "
            "С брынзой и сметаной — объедение! 😋"
        )

    elif "кишинёв" in text or "кишинев" in text or "chisinau" in text:
        await update.message.reply_text(
            "🏛️ Кишинёв — одна из самых зелёных столиц Европы! "
            "Основан в 1436 году. Красивый город! 🌿"
        )

    elif "молдова" in text or "молдавия" in text or "moldova" in text:
        await update.message.reply_text(
            f"🇲🇩 А вот и факт о Молдове:\n{random.choice(MOLDOVA_FACTS)}"
        )
