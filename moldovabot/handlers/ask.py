import logging

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

from ..config import XAI_API_KEY

logger = logging.getLogger(__name__)

GROQ_SYSTEM_PROMPT = (  # можно оставить то же имя переменной
    "Ты — ассистент в Telegram-группе о жизни, общении и lifestyle. "
    "Помогаешь участникам: отвечаешь на вопросы, ищешь актуальную информацию, поддерживаешь беседу. "
    "СТИЛЬ: только русский язык, дружелюбный тон, максимум 3-4 предложения. "
    "Никакого markdown — только обычный текст. Списки через дефис или цифры с точкой. "
    "Не более 1 эмодзи в сообщении. "
    "АКТУАЛЬНЫЕ ДАННЫЕ: при вопросах о новостях, погоде, ценах, событиях — используй поиск. "
    "Отвечай конкретно: факт + источник одним словом. Не придумывай данные. "
    "МОДЕРАЦИЯ: "
    "Это закрытая группа друзей — можно общаться жёстко и с юмором. "
    "На токсичность отвечай токсичностью — остроумно, с сарказмом, не стесняйся. "
    "Можешь подколоть в ответ, но без перехода на личные оскорбления вне контекста шутки. "
    "Спам и реальные ссылки на рекламу всё равно игнорируй. "
)


async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not XAI_API_KEY:
        await update.message.reply_text("⚠️ XAI_API_KEY не настроен.")
        return

    if not context.args:
        await update.message.reply_text("🤖 Пример: /ask Что случилось в ОАЭ сегодня?")
        return

    question = " ".join(context.args)
    user = update.effective_user
    thinking_msg = await update.message.reply_text("🤔 Ищу информацию, это может занять до 30 сек...")

    try:
        payload = {
            "model": "grok-4-1-fast-non-reasoning",
            "input": [
                {"role": "system", "content": GROQ_SYSTEM_PROMPT},
                {"role": "user",   "content": question},
            ],
            "max_output_tokens": 512,
            "temperature": 0.7,
            "tools": [
                {"type": "web_search"},
                {"type": "x_search"},
            ],
        }
        headers = {
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type":  "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.x.ai/v1/responses",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}: {(await resp.text())[:150]}")
                data = await resp.json()

        answer = ""
        for block in data.get("output", []):
            if block.get("type") == "message":
                for part in block.get("content", []):
                    if part.get("type") == "output_text":
                        answer += part.get("text", "")

        answer = answer.strip()
        if not answer:
            raise ValueError("Пустой ответ от Grok")

        logger.info(f"Grok /ask | user={user.id} | q={question[:50]!r}")

        await thinking_msg.edit_text(
            f"🤖 <b>Вопрос:</b> {question}\n\n{answer}",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.warning(f"Grok error: {type(e).__name__}: {e}")
        await thinking_msg.edit_text("⚠️ Не удалось получить ответ. Попробуй позже!")
