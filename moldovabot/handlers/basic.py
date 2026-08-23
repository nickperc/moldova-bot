import random

from telegram import Poll, Update
from telegram.ext import ContextTypes

from ..data import ANEKDOTY, MAGIC_8_ANSWERS, MOLDOVA_FACTS, QUIZ_QUESTIONS
from ..timeutil import now_chisinau


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветствие при старте."""
    user = update.effective_user
    text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Я — <b>МолдовБот</b> 🇲🇩🍷\n"
        "Готов развлекать и помогать вашей группе!\n\n"
        "Напиши /help чтобы увидеть все команды."
    )
    await update.message.reply_html(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Список команд."""
    text = (
        "📋 <b>Команды МолдовБота:</b>\n\n"
        "🇲🇩 <b>Молдова</b>\n"
        "/fact — Случайный факт о Молдове\n"
        "/quiz — Викторина о Молдове\n"
        "/holiday — Ближайшие праздники Молдовы 🗓️\n"
        "/weather — Погода в Кишинёве\n"
        "/weather &lt;город&gt; — Погода в любом городе 🌍\n"
        "/weather forecast — Прогноз на 3 дня\n"
        "/mdl — Курс молдавского лея\n"
        "/fuel — Цены на топливо по АЗС ⛽\n\n"
        "😄 <b>Развлечения</b>\n"
        "/anekdot — Молдавский анекдот\n"
        "/roll — Бросить кубик 🎲\n"
        "/8ball &lt;вопрос&gt; — Магический шар 🔮\n"
        "/flip — Орёл или решка 🪙\n"
        "/choice &lt;вар1|вар2|...&gt; — Выбор случайного варианта\n\n"
        "⚙️ <b>Группа</b>\n"
        "/time — Текущее время в Кишинёве\n"
        "/id — Показать ID чата\n"
        "/help — Эта справка\n\n"
        "💎 <b>Крипто</b>\n"
        "/crypto — Топ-10 криптовалют 📈\n"
        "/altSeason — Индекс альтсезона 🚀\n\n"
        "📰 <b>Новости</b>\n"
        "/news — Мировые новости\n"
        "/news md — 🇲🇩 Молдова\n"
        "/news crypto — 💎 Крипто\n"
        "/news tech — 💻 Технологии\n"
        "/news uae — 🇦🇪 ОАЭ\n\n"
        "✈️ <b>Рейсы KIV</b>\n"
        "/flights — Сводка вылетов из Кишинёва 🛫\n"
        "/flights arr — Сводка прилётов в Кишинёв 🛬\n"
        "/kiv &lt;рейс&gt; — Карточка конкретного рейса (напр. /kiv TK276)\n\n"
        "🎬 <b>Кино</b>\n"
        "/cinema — Расписание Cineplex Mall на сегодня\n"
        "/cinema loteanu — Расписание Cineplex Loteanu\n\n"
        "🍺 <b>Пиво</b>\n"
        "/beer — Топ-10 пива со скидкой в Linella\n"
        "/beer all — Все акции на пиво\n\n"
        "🤖 <b>AI и разное</b>\n"
        "/ask &lt;вопрос&gt; — Спросить у ИИ (Groq)\n"
        "/joke — Случайная шутка 😂\n\n"
        "<i>Бот говорит только по-русски 🇷🇺</i>"
    )
    await update.message.reply_html(text)


async def fact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Случайный факт о Молдове."""
    chosen = random.choice(MOLDOVA_FACTS)
    await update.message.reply_text(f"📖 <b>Факт о Молдове:</b>\n\n{chosen}", parse_mode="HTML")


async def anekdot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Молдавский анекдот."""
    chosen = random.choice(ANEKDOTY)
    await update.message.reply_text(f"😄 <b>Анекдот дня:</b>\n\n{chosen}", parse_mode="HTML")


async def roll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Бросить кубик."""
    user = update.effective_user
    result = random.randint(1, 6)
    faces = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}
    await update.message.reply_text(
        f"🎲 <b>{user.first_name}</b> бросил кубик и выпало: {faces[result]} <b>{result}</b>",
        parse_mode="HTML",
    )


async def flip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Орёл или решка."""
    user = update.effective_user
    result = random.choice([("🦅 Орёл!", "орёл"), ("💰 Решка!", "решка")])
    await update.message.reply_text(
        f"🪙 <b>{user.first_name}</b> подбросил монетку... <b>{result[0]}</b>",
        parse_mode="HTML",
    )


async def magic_8ball(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Магический шар 8."""
    if not context.args:
        await update.message.reply_text(
            "🔮 Задай мне вопрос!\nПример: /8ball Будет ли сегодня хорошая погода?"
        )
        return
    question = " ".join(context.args)
    answer = random.choice(MAGIC_8_ANSWERS)
    await update.message.reply_text(
        f"🔮 <b>Вопрос:</b> {question}\n\n<b>Магический шар говорит:</b> {answer}",
        parse_mode="HTML",
    )


async def choice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выбрать случайный вариант из списка."""
    if not context.args:
        await update.message.reply_text(
            "❓ Укажи варианты через | \nПример: /choice пицца|суши|мамалыга"
        )
        return
    raw = " ".join(context.args)
    options = [o.strip() for o in raw.split("|") if o.strip()]
    if len(options) < 2:
        await update.message.reply_text("⚠️ Нужно хотя бы 2 варианта, разделённых символом |")
        return
    chosen = random.choice(options)
    await update.message.reply_text(
        f"🎯 Я выбираю: <b>{chosen}</b>!", parse_mode="HTML"
    )


async def time_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Текущее время в Кишинёве (UTC+2/UTC+3)."""
    chisinau_time = now_chisinau()
    formatted = chisinau_time.strftime("%H:%M:%S, %d.%m.%Y")
    offset = chisinau_time.utcoffset().seconds // 3600
    zone_name = "EEST (UTC+3)" if offset == 3 else "EET (UTC+2)"
    await update.message.reply_text(
        f"🕐 <b>Время в Кишинёве:</b>\n{formatted}\n<i>Часовой пояс: {zone_name}</i>",
        parse_mode="HTML",
    )


async def chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать ID чата."""
    cid = update.effective_chat.id
    uid = update.effective_user.id
    await update.message.reply_text(
        f"🆔 <b>ID чата:</b> <code>{cid}</code>\n"
        f"👤 <b>Ваш ID:</b> <code>{uid}</code>",
        parse_mode="HTML",
    )


async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Викторина о Молдове через Telegram Poll."""
    q = random.choice(QUIZ_QUESTIONS)
    await update.message.reply_poll(
        question=q["question"],
        options=q["options"],
        type=Poll.QUIZ,
        correct_option_id=q["answer"],
        explanation="🇲🇩 Узнай больше о Молдове с командой /fact!",
        is_anonymous=False,
    )
