import os
import random
import logging
import aiohttp
from datetime import datetime
from telegram import Update, Poll
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ChatMemberHandler,
)

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Token ───────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ─── Data ────────────────────────────────────────────────────────────────────
MOLDOVA_FACTS = [
    "🇲🇩 Молдова — одна из самых маленьких стран в Европе, площадью всего 33 846 км².",
    "🍷 Молдова входит в топ-10 мировых производителей вина. В стране более 100 000 га виноградников!",
    "🕳️ В Крикова находится один из крупнейших в мире подземных винных погребов — длина туннелей около 120 км.",
    "🌻 Молдова — один из крупнейших мировых экспортёров подсолнечного масла.",
    "🏛️ Кишинёв основан в 1436 году и является одной из самых зелёных столиц Европы.",
    "🎻 Молдавская народная музыка — дойна — признана нематериальным наследием ЮНЕСКО.",
    "🧀 Национальное блюдо Молдовы — мамалыга (кукурузная каша), которую едят с брынзой и сметаной.",
    "🌊 Молдова — одна из немногих стран Европы, не имеющих выхода к морю.",
    "🦅 На гербе Молдовы изображён орёл с щитом, на котором — бычья голова, традиционный символ страны.",
    "🥂 В Молдове проходит ежегодный Национальный День Вина — в первые выходные октября.",
    "🎭 В Кишинёве находится один из старейших театров Восточной Европы — Национальный театр им. Эминеску.",
    "🌿 Орхей — древнее поселение в Молдове возрастом более 2000 лет, высеченное прямо в скале.",
    "📚 Молдавский и румынский языки — фактически один и тот же язык, написанный латиницей.",
    "🚂 Молдова была частью Советского Союза с 1940 по 1991 год.",
    "🌾 Более 75% территории Молдовы — сельскохозяйственные угодья.",
]

ANEKDOTY = [
    "— Почему молдаване такие спокойные?\n— Потому что у них всегда есть вино! 🍷",
    "Молдавский фермер приходит в банк:\n— Хочу взять кредит.\n— На что?\n— На трактор.\n— А залог?\n— Вот, держите — ящик вина 1987 года.\n— Одобрено! 🚜🍷",
    "— Что молдаванин берёт на необитаемый остров?\n— Саженцы винограда. Остальное приложится. 🏝️",
    "Турист спрашивает кишинёвца:\n— Как пройти на центральную площадь?\n— А вы на машине или пешком?\n— Пешком.\n— Тогда сначала выпейте вина — путь покажется короче! 🗺️",
    "— Доктор, у меня к вам вопрос: можно ли пить вино каждый день?\n— Молодой человек, вы из Молдовы?\n— Да...\n— Тогда это не вопрос медицины, это вопрос традиций. 😄",
    "Встречаются два молдаванина:\n— Как дела?\n— Как виноград!\n— В смысле?\n— Когда солнце — хорошо, когда дождь — тоже пойдёт. 🌤️",
    "— Почему в Молдове так мало психологов?\n— Потому что у них есть мамалыга, вино и добрые соседи! 🫂",
    "Молдавская мудрость: *Лучше бутылка вина у соседа сегодня, чем бочка мёда одному завтра.* 🍯",
]

MAGIC_8_ANSWERS = [
    "✅ Бесспорно!",
    "✅ Даже не сомневайся!",
    "✅ Мой ответ — да!",
    "✅ Скорее всего, да.",
    "✅ Хороший знак.",
    "🔮 Лучше не рассказывать...",
    "🔮 Сосредоточься и спроси снова.",
    "🔮 Ответ туманен... попробуй позже.",
    "🔮 Трудно сказать сейчас.",
    "❌ Не рассчитывай на это.",
    "❌ Мой ответ — нет.",
    "❌ Весьма сомнительно.",
    "❌ Очень сомнительно.",
]

QUIZ_QUESTIONS = [
    {
        "question": "🍷 Какой город в Молдове известен своим огромным подземным винным погребом?",
        "options": ["Кишинёв", "Крикова", "Тирасполь", "Бельцы"],
        "answer": 1,
    },
    {
        "question": "🌍 Какова столица Молдовы?",
        "options": ["Одесса", "Бухарест", "Кишинёв", "Кагул"],
        "answer": 2,
    },
    {
        "question": "📅 В каком году Молдова получила независимость?",
        "options": ["1989", "1990", "1991", "1992"],
        "answer": 2,
    },
    {
        "question": "🍽️ Какое национальное блюдо Молдовы?",
        "options": ["Борщ", "Мамалыга", "Плацинда", "Зама"],
        "answer": 1,
    },
    {
        "question": "🏳️ Каковы цвета молдавского флага?",
        "options": [
            "Красный, жёлтый, зелёный",
            "Синий, жёлтый, красный",
            "Белый, синий, красный",
            "Зелёный, белый, красный",
        ],
        "answer": 1,
    },
    {
        "question": "🌊 Какая река является восточной границей Молдовы?",
        "options": ["Дунай", "Прут", "Реут", "Днестр"],
        "answer": 3,
    },
    {
        "question": "🍇 Когда в Молдове отмечают День Вина?",
        "options": [
            "Первые выходные августа",
            "Первые выходные октября",
            "Первые выходные сентября",
            "31 декабря",
        ],
        "answer": 1,
    },
]

# ─── Цены на топливо ─────────────────────────────────────────────────────────
# Обновляй цены вручную здесь (в MDL за литр).
# Дата последнего обновления меняется автоматически при запуске бота,
# но цифры нужно обновлять руками при изменении цен на АЗС.

FUEL_LAST_UPDATED = "15.03.2025"   # ← меняй дату при обновлении цен

FUEL_PRICES = [
    # (название АЗС, логотип-emoji, цена А-95, цена дизель)
    ("Bemol",        "🔵", 24.69, 22.49),
    ("Petrom",       "🟠", 24.79, 22.59),
    ("Lukoil",       "🔴", 24.75, 22.55),
    ("Rompetrol",    "🟡", 24.85, 22.65),
    ("Tirex-Petrol", "🟢", 24.59, 22.39),
    ("Nefis",        "⚪", 24.49, 22.29),
]


# ─── Команды ─────────────────────────────────────────────────────────────────

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
        "/weather — Погода в Кишинёве\n"
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
    from datetime import timezone, timedelta
    # Молдова: зимой UTC+2, летом UTC+3
    now_utc = datetime.now(timezone.utc)
    month = now_utc.month
    offset = 3 if 3 < month < 11 else 2  # приблизительно летнее/зимнее время
    chisinau_time = now_utc + timedelta(hours=offset)
    formatted = chisinau_time.strftime("%H:%M:%S, %d.%m.%Y")
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


async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Погода в Кишинёве через wttr.in."""
    city = "Chisinau"
    url = f"https://wttr.in/{city}?format=j1&lang=ru"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    raise ValueError("bad status")
                data = await resp.json()

        current = data["current_condition"][0]
        temp_c = current["temp_C"]
        feels_c = current["FeelsLikeC"]
        humidity = current["humidity"]
        wind_kmph = current["windspeedKmph"]
        desc = current["lang_ru"][0]["value"]

        # Emoji по описанию
        desc_lower = desc.lower()
        if "ясн" in desc_lower or "солнц" in desc_lower:
            icon = "☀️"
        elif "облач" in desc_lower or "пасмурн" in desc_lower:
            icon = "☁️"
        elif "дождь" in desc_lower or "морос" in desc_lower:
            icon = "🌧️"
        elif "снег" in desc_lower:
            icon = "❄️"
        elif "гроз" in desc_lower:
            icon = "⛈️"
        elif "туман" in desc_lower:
            icon = "🌫️"
        else:
            icon = "🌤️"

        msg = (
            f"{icon} <b>Погода в Кишинёве</b>\n\n"
            f"🌡️ Температура: <b>{temp_c}°C</b> (ощущается как {feels_c}°C)\n"
            f"💧 Влажность: {humidity}%\n"
            f"💨 Ветер: {wind_kmph} км/ч\n"
            f"☁️ Состояние: {desc}"
        )
    except Exception as e:
        logger.warning(f"Weather error: {e}")
        msg = "⚠️ Не удалось получить погоду. Попробуй позже!"

    await update.message.reply_html(msg)


async def mdl_rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Курс молдавского лея (MDL) через exchangerate-api."""
    url = "https://open.er-api.com/v6/latest/MDL"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    raise ValueError("bad status")
                data = await resp.json()

        rates = data.get("rates", {})
        usd = rates.get("USD", 0)
        eur = rates.get("EUR", 0)
        rub = rates.get("RUB", 0)
        ron = rates.get("RON", 0)
        uah = rates.get("UAH", 0)

        usd_inv = round(1 / usd, 2) if usd else "N/A"
        eur_inv = round(1 / eur, 2) if eur else "N/A"

        msg = (
            "💵 <b>Курс молдавского лея (MDL)</b>\n\n"
            f"🇺🇸 1 USD = <b>{usd_inv} MDL</b>\n"
            f"🇪🇺 1 EUR = <b>{eur_inv} MDL</b>\n"
            f"🇷🇺 100 RUB = <b>{round(100 * rub, 2)} MDL</b>\n"
            f"🇷🇴 1 RON = <b>{round(ron, 4)} MDL</b>\n"
            f"🇺🇦 100 UAH = <b>{round(100 * uah, 2)} MDL</b>\n\n"
            "<i>Источник: open.er-api.com</i>"
        )
    except Exception as e:
        logger.warning(f"MDL rate error: {e}")
        msg = "⚠️ Не удалось получить курс. Попробуй позже!"

    await update.message.reply_html(msg)


async def fuel_prices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Цены на топливо по заправкам Молдовы."""

    # Найти мин/макс по А-95 и дизелю
    prices_95  = [(name, p95)  for name, _, p95, _    in FUEL_PRICES]
    prices_dsl = [(name, pdsl) for name, _, _,   pdsl in FUEL_PRICES]

    cheapest_95  = min(prices_95,  key=lambda x: x[1])
    cheapest_dsl = min(prices_dsl, key=lambda x: x[1])
    priciest_95  = max(prices_95,  key=lambda x: x[1])
    priciest_dsl = max(prices_dsl, key=lambda x: x[1])

    # Таблица цен
    rows = ""
    for name, emoji, p95, pdsl in FUEL_PRICES:
        # Метки «дешевле всего»
        tag_95  = " 🏆" if name == cheapest_95[0]  else ""
        tag_dsl = " 🏆" if name == cheapest_dsl[0] else ""
        rows += (
            f"{emoji} <b>{name}</b>\n"
            f"   ⛽ А-95: <b>{p95:.2f} MDL</b>{tag_95}   "
            f"🚛 ДТ: <b>{pdsl:.2f} MDL</b>{tag_dsl}\n"
        )

    spread_95  = round(priciest_95[1]  - cheapest_95[1],  2)
    spread_dsl = round(priciest_dsl[1] - cheapest_dsl[1], 2)

    msg = (
        "⛽ <b>Цены на топливо в Молдове</b>\n"
        f"<i>Обновлено: {FUEL_LAST_UPDATED}</i>\n\n"
        f"{rows}\n"
        "─────────────────────\n"
        f"🏆 <b>Дешевле всего А-95:</b> {cheapest_95[0]} — {cheapest_95[1]:.2f} MDL\n"
        f"🏆 <b>Дешевле всего ДТ:</b>   {cheapest_dsl[0]} — {cheapest_dsl[1]:.2f} MDL\n\n"
        f"📊 Разброс А-95: {spread_95} MDL  |  ДТ: {spread_dsl} MDL\n\n"
        "<i>⚠️ Цены обновляются вручную. Уточняй актуальные на АЗС.</i>"
    )
    await update.message.reply_html(msg)


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




# ─── Крипто ──────────────────────────────────────────────────────────────────

async def crypto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Топ-10 криптовалют по капитализации через CoinGecko (бесплатный API)."""
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        "?vs_currency=usd&order=market_cap_desc&per_page=10&page=1"
        "&sparkline=false&price_change_percentage=24h"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                coins = await resp.json()

        rows = ""
        for i, c in enumerate(coins, 1):
            name      = c["name"]
            symbol    = c["symbol"].upper()
            price     = c["current_price"]
            change    = c.get("price_change_percentage_24h") or 0.0
            mcap      = c["market_cap"]
            arrow     = "🟢" if change >= 0 else "🔴"
            sign      = "+" if change >= 0 else ""

            # Форматируем цену красиво
            if price >= 1:
                price_str = f"${price:,.2f}"
            elif price >= 0.01:
                price_str = f"${price:.4f}"
            else:
                price_str = f"${price:.8f}"

            # Форматируем капу: $1.23T / $456.7B / $12.3M
            if mcap >= 1_000_000_000_000:
                mcap_str = f"${mcap/1_000_000_000_000:.2f}T"
            elif mcap >= 1_000_000_000:
                mcap_str = f"${mcap/1_000_000_000:.1f}B"
            else:
                mcap_str = f"${mcap/1_000_000:.0f}M"

            rows += (
                f"{i}. {arrow} <b>{name}</b> ({symbol})\n"
                f"   💵 {price_str}  {sign}{change:.1f}%  🏦 {mcap_str}\n"
            )

        msg = (
            "💎 <b>Топ-10 криптовалют</b>\n"
            "<i>Цена · Изменение за 24ч · Капитализация</i>\n\n"
            f"{rows}\n"
            "<i>Источник: CoinGecko</i>"
        )
    except Exception as e:
        logger.warning(f"Crypto error: {e}")
        msg = "⚠️ Не удалось получить данные о криптовалютах. Попробуй позже!"

    await update.message.reply_html(msg)


async def alt_season(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Индекс альтсезона.
    Логика: берём топ-50 монет (без BTC и стейблов), считаем сколько из них
    обогнали BTC за последние 90 дней. Если ≥75% — альтсезон. Официальная
    методология сайта blockchaincenter.net.
    """
    url_top50 = (
        "https://api.coingecko.com/api/v3/coins/markets"
        "?vs_currency=usd&order=market_cap_desc&per_page=50&page=1"
        "&sparkline=false&price_change_percentage=90d"
    )
    url_btc = (
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"
    )

    STABLECOINS = {"usdt", "usdc", "busd", "dai", "tusd", "usdp", "usdd",
                   "frax", "lusd", "gusd", "fdusd", "pyusd"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url_top50, timeout=aiohttp.ClientTimeout(total=12)) as r1:
                if r1.status != 200:
                    raise ValueError(f"HTTP {r1.status}")
                top50 = await r1.json()

            async with session.get(url_btc, timeout=aiohttp.ClientTimeout(total=8)) as r2:
                if r2.status != 200:
                    raise ValueError(f"HTTP {r2.status}")
                btc_data = await r2.json()

        # Изменение BTC за 90 дней — ищем в списке топ50
        btc_90d = next(
            (c.get("price_change_percentage_90d_in_currency") or 0.0
             for c in top50 if c["symbol"].lower() == "btc"),
            0.0
        )

        # Фильтруем: убираем BTC и стейблы
        alts = [
            c for c in top50
            if c["symbol"].lower() != "btc"
            and c["symbol"].lower() not in STABLECOINS
        ]

        # Считаем сколько алтов обогнали BTC за 90 дней
        total = len(alts)
        outperformed = sum(
            1 for c in alts
            if (c.get("price_change_percentage_90d_in_currency") or 0.0) > btc_90d
        )

        index = round((outperformed / total) * 100) if total else 0

        # Определяем статус
        if index >= 75:
            status      = "🚀 <b>АЛЬТСЕЗОН!</b>"
            description = "Альты рвут! Более 75% топ-50 монет обогнали Bitcoin за 90 дней."
            verdict     = "🔥 Альтсезон в разгаре — исторически лучшее время для алтов!"
        elif index >= 55:
            status      = "⚡ <b>Начало альтсезона</b>"
            description = "Альты набирают силу — больше половины обогнали BTC."
            verdict     = "📈 Рынок разогревается. Следи за альтами внимательно."
        elif index >= 40:
            status      = "😐 <b>Нейтральный рынок</b>"
            description = "Нет явного доминирования ни BTC, ни альтов."
            verdict     = "🤷 Жди чёткого сигнала — пока рынок в равновесии."
        elif index >= 25:
            status      = "🟡 <b>Сезон Bitcoin</b>"
            description = "BTC доминирует, большинство алтов отстают."
            verdict     = "⚠️ Алты под давлением — осторожно с покупками."
        else:
            status      = "🟠 <b>Глубокий сезон Bitcoin</b>"
            description = "BTC сильно обгоняет альты. Альтсезон далеко."
            verdict     = "🛑 Альты страдают. Лучше подождать разворота."

        # Визуальная шкала
        filled = round(index / 10)
        bar    = "█" * filled + "░" * (10 - filled)

        msg = (
            f"🌡️ <b>Индекс Альтсезона</b>\n\n"
            f"{status}\n"
            f"<code>[{bar}] {index}/100</code>\n\n"
            f"📊 {outperformed} из {total} топ-алтов обогнали BTC за 90 дней\n"
            f"₿  BTC за 90 дней: {'🟢 +' if btc_90d >= 0 else '🔴 '}{btc_90d:.1f}%\n\n"
            f"ℹ️ {description}\n\n"
            f"{verdict}\n\n"
            "<i>Методология: blockchaincenter.net · Данные: CoinGecko</i>"
        )
    except Exception as e:
        logger.warning(f"AltSeason error: {e}")
        msg = "⚠️ Не удалось получить данные. Попробуй позже!"

    await update.message.reply_html(msg)


# ─── Приветствие новых участников ─────────────────────────────────────────────

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


# ─── Ответы на ключевые слова ─────────────────────────────────────────────────

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


# ─── Запуск ───────────────────────────────────────────────────────────────────

def main() -> None:
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Установи токен! Задай переменную окружения BOT_TOKEN или вставь его в код.")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("fact", fact))
    app.add_handler(CommandHandler("anekdot", anekdot))
    app.add_handler(CommandHandler("roll", roll))
    app.add_handler(CommandHandler("flip", flip))
    app.add_handler(CommandHandler("8ball", magic_8ball))
    app.add_handler(CommandHandler("choice", choice_cmd))
    app.add_handler(CommandHandler("time", time_cmd))
    app.add_handler(CommandHandler("id", chat_id))
    app.add_handler(CommandHandler("weather", weather))
    app.add_handler(CommandHandler("mdl", mdl_rate))
    app.add_handler(CommandHandler("fuel", fuel_prices))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CommandHandler("crypto", crypto))
    app.add_handler(CommandHandler("altSeason", alt_season))

    # Новые участники
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))

    # Ключевые слова (только в группах)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
            keyword_reply,
        )
    )

    logger.info("🤖 МолдовБот запущен! Нажми Ctrl+C для остановки.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()