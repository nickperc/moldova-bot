import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def log_usage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Middleware: логирует каждое использование бота — кто, где, что."""
    if not update.message and not update.callback_query:
        return

    user = update.effective_user
    chat = update.effective_chat

    if not user:
        return

    user_info = f"@{user.username}" if user.username else f"id={user.id}"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "N/A"

    chat_types = {
        "private":    "💬 Личка",
        "group":      "👥 Группа",
        "supergroup": "👥 Супергруппа",
        "channel":    "📢 Канал",
    }
    chat_type_label = chat_types.get(chat.type, chat.type)
    chat_name = chat.title if chat.title else "—"
    chat_id_val = chat.id

    if update.message and update.message.text:
        text = update.message.text[:60]
        action = f"text: {text!r}"
    elif update.message and update.message.new_chat_members:
        action = "new_member_joined"
    else:
        action = "other_update"

    logger.info(
        f"📥 USAGE | {chat_type_label} | "
        f"user={user_info} ({full_name}, id={user.id}) | "
        f"chat={chat_name!r} (id={chat_id_val}) | "
        f"{action}"
    )
