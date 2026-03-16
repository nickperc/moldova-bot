import os
import random
import logging
import aiohttp
import xml.etree.ElementTree as ET
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
BOT_TOKEN    = os.getenv("BOT_TOKEN",    "YOUR_BOT_TOKEN_HERE")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

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
        "📰 <b>Новости</b>\n"
        "/news — Мировые новости\n"
        "/news md — 🇲🇩 Молдова\n"
        "/news crypto — 💎 Крипто\n"
        "/news tech — 💻 Технологии\n"
        "/news uae — 🇦🇪 ОАЭ\n\n"
        "🤖 <b>AI и разное</b>\n"
        "/ask &lt;вопрос&gt; — Спросить у ИИ (Groq)\n"
        "/joke — Случайная шутка 😂\n"
        "/advice — Случайный совет 💡\n\n"
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
    """Цены на топливо в реальном времени с ANRE API (api.ecarburanti.anre.md)."""

    ANRE_URL = "https://api.ecarburanti.anre.md/public"

    # Целевые сети и их emoji
    TARGET_STATIONS = {
        "ROMPETROL": "🟠",
        "VENTO":     "🟣",
        "PETROM":    "🟡",
        "LUKOIL":    "🔴",
        "NOW OIL":   "⚪️",
        "BEMOL":     "🟢",
        "AVANTE":    "🔵",
    }

    def _safe_price(val) -> float | None:
        """Возвращает float или None если значение нулевое/отсутствует."""
        try:
            f = float(val)
            return f if f > 0 else None
        except (TypeError, ValueError):
            return None

    def _price_str(val: float | None) -> str:
        return f"{val:.2f} MDL" if val is not None else "—"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                ANRE_URL,
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"User-Agent": "MoldovaBot/1.0"},
            ) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                raw: list = await resp.json(content_type=None)

        from datetime import timezone, timedelta
        month = datetime.now(timezone.utc).month
        md_offset = timedelta(hours=3 if 3 < month < 11 else 2)
        fetched_at = datetime.now(timezone(md_offset)).strftime("%d.%m.%Y %H:%M")

        # ── Группируем все записи по имени станции ────────────────────────────
        grouped: dict[str, list[dict]] = {target: [] for target in TARGET_STATIONS}

        for record in raw:
            name_raw: str = (record.get("station_name") or "").strip().upper()
            matched = next(
                (target for target in TARGET_STATIONS if target in name_raw),
                None,
            )
            if matched:
                grouped[matched].append(record)

        # ── Для каждой сети ищем лучшее значение по каждому виду топлива ─────
        # Если в первом рекорде null — перебираем остальные до первого не-null
        def _best_fuel(records: list[dict], field: str) -> float | None:
            for rec in records:
                val = _safe_price(rec.get(field))
                if val is not None:
                    return val
            return None  # все рекорды null или список пуст

        stations: list[dict] = []
        not_found: list[str] = []

        for target, emoji in TARGET_STATIONS.items():
            records = grouped[target]
            if not records:
                not_found.append(target)
                continue
            stations.append({
                "name":     target,
                "emoji":    emoji,
                "gasoline": _best_fuel(records, "gasoline"),
                "diesel":   _best_fuel(records, "diesel"),
                "gpl":      _best_fuel(records, "gpl"),
            })

        if not stations:
            raise ValueError("Нет данных от API")

        # ── Сортируем по gasoline (None в конец) ─────────────────────────────
        stations.sort(key=lambda s: s["gasoline"] if s["gasoline"] is not None else 999)

        # ── Находим минимумы по каждому типу топлива ─────────────────────────
        def _cheapest(fuel: str) -> tuple[str, float] | None:
            valid = [(s["name"], s[fuel]) for s in stations if s[fuel] is not None]
            return min(valid, key=lambda x: x[1]) if valid else None

        best_gasoline = _cheapest("gasoline")
        best_diesel   = _cheapest("diesel")
        best_gpl      = _cheapest("gpl")

        # ── Строим таблицу ────────────────────────────────────────────────────
        rows = ""
        for i, s in enumerate(stations, 1):
            g_tag = " 🏆" if best_gasoline and s["name"] == best_gasoline[0] else ""
            d_tag = " 🏆" if best_diesel   and s["name"] == best_diesel[0]   else ""
            p_tag = " 🏆" if best_gpl      and s["name"] == best_gpl[0]      else ""

            rows += (
                f"{s['emoji']} <b>{s['name']}</b>\n"
                f"   🚗 Бензин-95: <b>{_price_str(s['gasoline'])}</b>{g_tag}\n"
                f"   🚛 Дизель: <b>{_price_str(s['diesel'])}</b>{d_tag}\n"
                f"   🚕 Газ:    <b>{_price_str(s['gpl'])}</b>{p_tag}\n\n"
            )

        # ── Блок лучших цен ───────────────────────────────────────────────────
        best_lines = ""
        if best_gasoline:
            best_lines += f"🚗 Бензин-95:  <b>{best_gasoline[0]}</b> — {best_gasoline[1]:.2f} MDL\n"
        if best_diesel:
            best_lines += f"🚛 Дизель:  <b>{best_diesel[0]}</b> — {best_diesel[1]:.2f} MDL\n"
        if best_gpl:
            best_lines += f"🚕 Газ:     <b>{best_gpl[0]}</b> — {best_gpl[1]:.2f} MDL\n"

        # ── Предупреждение если сеть не найдена в API ─────────────────────────
        not_found_line = ""
        if not_found:
            not_found_line = (
                f"\n⚠️ <i>Не найдено в API: {', '.join(not_found)}</i>\n"
            )

        msg = (
            "⛽ <b>Цены на топливо в Молдове</b>\n"
            f"<i>🕐 Данные от: {fetched_at} | Источник: ANRE</i>\n\n"
            f"{rows}"
            "─────────────────────────\n"
            f"🏆 <b>Лучшие цены:</b>\n"
            f"{best_lines}"
            f"{not_found_line}\n"
        )

    except Exception as e:
        logger.warning(f"Fuel API error: {e}")
        msg = "⚠️ Не удалось получить цены на топливо. Попробуй позже!"

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

def _fmt_price(price: float) -> str:
    """Форматирует цену монеты в читаемый вид."""
    if price >= 1_000:
        return f"${price:,.0f}"
    elif price >= 1:
        return f"${price:,.2f}"
    elif price >= 0.01:
        return f"${price:.4f}"
    else:
        return f"${price:.6f}"


def _fmt_mcap(mcap: float) -> str:
    """Форматирует капитализацию: T / B / M."""
    if mcap >= 1_000_000_000_000:
        return f"${mcap / 1_000_000_000_000:.2f}T"
    elif mcap >= 1_000_000_000:
        return f"${mcap / 1_000_000_000:.1f}B"
    else:
        return f"${mcap / 1_000_000:.0f}M"


def _fmt_change(change: float) -> str:
    """Форматирует % изменение с нужным emoji и знаком."""
    if change is None:
        return "➡️  0.0%"
    elif abs(change) < 0.05:          # практически ноль
        return f"➡️  0.0%"
    elif change > 0:
        return f"📈 +{change:.1f}%"
    else:
        return f"📉 {change:.1f}%"


async def crypto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Топ-10 криптовалют по капитализации через CoinGecko."""
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        "?vs_currency=usd&order=market_cap_desc&per_page=10&page=1"
        "&sparkline=false&price_change_percentage=24h"
    )
    HEADERS = {"User-Agent": "MoldovaBot/1.0"}
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                coins = await resp.json()

        # Собираем строки таблицы в моноширинном блоке для выравнивания
        lines = []
        for i, c in enumerate(coins, 1):
            symbol    = c["symbol"].upper()
            price     = c.get("current_price") or 0.0
            change    = c.get("price_change_percentage_24h")
            mcap      = c.get("market_cap") or 0

            price_str  = _fmt_price(price).ljust(12)
            change_str = _fmt_change(change).ljust(14)
            mcap_str   = _fmt_mcap(mcap)

            lines.append(f"{i:>2}. {symbol:<6} {price_str} {change_str} {mcap_str}")

        table = "\n".join(lines)

        msg = (
            "💎 <b>Топ-10 криптовалют</b>\n\n"
            "<code>"
            " #  Монета  Цена           24ч             Капа\n"
            "─────────────────────────────────────────────\n"
            f"{table}"
            "</code>\n\n"
            "<i>Источник: CoinGecko</i>"
        )
    except Exception as e:
        logger.warning(f"Crypto error: {e}")
        msg = "⚠️ Не удалось получить данные о криптовалютах. Попробуй позже!"

    await update.message.reply_html(msg)


async def alt_season(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Индекс альтсезона на основе доминации BTC. altseasonIndex = 100 - btc_dominance."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.coingecko.com/api/v3/global",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                data = await resp.json()

        btc_dominance = data["data"]["market_cap_percentage"]["btc"]
        index = round(100 - btc_dominance)
        index = max(0, min(100, index))  # зажимаем в [0, 100]

        # ── Статус ───────────────────────────────────────────────────────────
        if btc_dominance < 40:
            status      = "🚀 <b>АЛЬТСЕЗОН!</b>"
            description = "BTC доминация ниже 40% — альты правят рынком!"
            verdict     = "🔥 Исторически лучшее время для альткоинов!"
        elif btc_dominance < 50:
            status      = "⚡ <b>Начало альтсезона</b>"
            description = "BTC теряет долю рынка — альты набирают силу."
            verdict     = "📈 Следи за альтами внимательно, рынок разогревается."
        elif btc_dominance < 55:
            status      = "😐 <b>Нейтральный рынок</b>"
            description = "Нет явного доминирования ни BTC, ни альтов."
            verdict     = "🤷 Жди чёткого сигнала — пока рынок в равновесии."
        elif btc_dominance < 60:
            status      = "🟡 <b>Сезон Bitcoin</b>"
            description = "BTC доминирует, альты под давлением."
            verdict     = "⚠️ Осторожно с покупкой альтов — BTC сильнее."
        else:
            status      = "🟠 <b>Глубокий сезон Bitcoin</b>"
            description = "BTC значительно доминирует на рынке."
            verdict     = "🛑 Альты страдают. Лучше подождать разворота."

        # ── Визуальная шкала ─────────────────────────────────────────────────
        filled = round(index / 10)
        bar    = "█" * filled + "░" * (10 - filled)

        msg = (
            "🌡️ <b>Индекс Альтсезона</b>\n\n"
            f"{status}\n"
            f"<code>[{bar}] {index}/100</code>\n\n"
            f"📊 BTC доминация: <b>{btc_dominance:.2f}%</b>\n"
            f"🔢 Формула: 100 - {btc_dominance:.2f}% = <b>{index}</b>\n\n"
            f"ℹ️ {description}\n\n"
            f"{verdict}\n\n"
            "<i>Данные: CoinGecko /global</i>"
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


# ─── Новости ──────────────────────────────────────────────────────────────────

# RSS источники по категориям
NEWS_SOURCES = {
    "md": {
        "label":   "🇲🇩 Новости Молдовы",
        "sources": [
            ("Point.md",    "https://point.md/rss"),
            ("Noi.md",      "https://www.noi.md/rss"),
            ("Moldova.org", "https://moldova.org/feed/"),
        ],
    },
    "world": {
        "label":   "🌍 Мировые новости",
        "sources": [
            ("BBC Русский",  "https://feeds.bbci.co.uk/russian/rss.xml"),
            ("РИА Новости",  "https://rsshub.app/ria/news"),
            ("Reuters",      "https://feeds.reuters.com/reuters/topNews"),
        ],
    },
    "crypto": {
        "label":   "💎 Крипто-новости",
        "sources": [
            ("CoinDesk",     "https://www.coindesk.com/arc/outboundfeeds/rss/"),
            ("CoinTelegraph","https://cointelegraph.com/rss"),
            ("Decrypt",      "https://decrypt.co/feed"),
        ],
    },
    "tech": {
        "label":   "💻 Технологии",
        "sources": [
            ("TechCrunch",   "https://techcrunch.com/feed/"),
            ("The Verge",    "https://www.theverge.com/rss/index.xml"),
            ("Hacker News",  "https://hnrss.org/frontpage"),
        ],
    },
    "uae": {
        "label":   "🇦🇪 Новости ОАЭ",
        "sources": [
            ("Gulf News",       "https://gulfnews.com/rss"),
            ("The National",    "https://www.thenationalnews.com/rss"),
            ("Khaleej Times",   "https://www.khaleejtimes.com/rss"),
        ],
    },
}

NEWS_HELP = (
    "📰 Использование: /news [категория]\n\n"
    "Доступные категории:\n"
    "  /news md      — 🇲🇩 Молдова\n"
    "  /news world   — 🌍 Мировые\n"
    "  /news crypto  — 💎 Крипто\n"
    "  /news tech    — 💻 Технологии\n"
    "  /news uae     — 🇦🇪 ОАЭ\n\n"
    "<i>По умолчанию: /news world</i>"
)


async def _fetch_rss(session: aiohttp.ClientSession, url: str, limit: int = 5) -> list[dict]:
    """Парсит RSS-ленту и возвращает список {title, link, date}."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status != 200:
                return []
            raw = await resp.read()

        root = ET.fromstring(raw)
        # Поддержка RSS 2.0 и Atom
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)

        results = []
        for item in items[:limit]:
            # Заголовок
            title_el = item.find("title")
            title = ""
            if title_el is not None:
                title = (title_el.text or "").strip()
                # Убираем CDATA и лишние пробелы
                title = title.replace("<![CDATA[", "").replace("]]>", "").strip()

            # Ссылка
            link_el = item.find("link")
            link = ""
            if link_el is not None:
                link = (link_el.text or "").strip()
            if not link:
                # Atom-стиль: <link href="..."/>
                link_el = item.find("atom:link", ns)
                if link_el is not None:
                    link = link_el.get("href", "")

            if title and link:
                results.append({"title": title, "link": link})

        return results
    except Exception as e:
        logger.debug(f"RSS fetch error for {url}: {e}")
        return []


async def news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать последние новости по категории из RSS-лент."""
    # Определяем категорию
    cat = context.args[0].lower() if context.args else "world"

    if cat in ("help", "?"):
        await update.message.reply_html(NEWS_HELP)
        return

    if cat not in NEWS_SOURCES:
        await update.message.reply_html(
            f"❓ Неизвестная категория <b>{cat}</b>\n\n{NEWS_HELP}"
        )
        return

    source_cfg = NEWS_SOURCES[cat]
    await update.message.reply_text("🔄 Загружаю новости...")

    articles = []
    source_used = None

    async with aiohttp.ClientSession() as session:
        for name, url in source_cfg["sources"]:
            items = await _fetch_rss(session, url, limit=5)
            if items:
                articles = items
                source_used = name
                break  # берём первый рабочий источник

    if not articles:
        await update.message.reply_text(
            "⚠️ Не удалось загрузить новости. Все источники недоступны, попробуй позже."
        )
        return

    # Форматируем вывод
    lines = []
    for i, art in enumerate(articles, 1):
        title = art["title"]
        # Обрезаем слишком длинные заголовки
        if len(title) > 120:
            title = title[:117] + "..."
        lines.append(f"{i}. <a href=\"{art['link']}\">{title}</a>")

    msg = (
        f"{source_cfg['label']}\n"
        f"<i>Источник: {source_used}</i>\n\n"
        + "\n\n".join(lines)
        + "\n\n<i>Нажми на заголовок чтобы открыть статью</i>"
    )

    await update.message.reply_html(
        msg,
        disable_web_page_preview=True,
    )



# ─── JokeAPI ─────────────────────────────────────────────────────────────────

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

        # Добавим категорию
        category = data.get("category", "")
        if category:
            msg += f"\n\n<i>Категория: {category}</i>"

    except Exception as e:
        logger.warning(f"JokeAPI error: {e}")
        msg = "⚠️ Не удалось получить шутку. Попробуй позже!"

    await update.message.reply_html(msg)


# ─── Advice Slip ─────────────────────────────────────────────────────────────

async def advice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Случайный совет через Advice Slip API (без ключа)."""
    url = "https://api.adviceslip.com/advice"
    try:
        async with aiohttp.ClientSession() as session:
            # API кэширует — cache-busting через timestamp
            async with session.get(
                url,
                params={"t": str(datetime.now().timestamp())},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                data = await resp.json(content_type=None)  # API возвращает text/html

        slip = data.get("slip", {})
        advice_text = slip.get("advice", "")
        slip_id     = slip.get("id", "")

        if not advice_text:
            raise ValueError("empty advice")

        msg = (
            f"💡 <b>Совет дня:</b>\n\n"
            f"<i>«{advice_text}»</i>\n\n"
            f"<code>#{slip_id}</code>"
        )
    except Exception as e:
        logger.warning(f"AdviceSlip error: {e}")
        msg = "⚠️ Не удалось получить совет. Попробуй позже!"

    await update.message.reply_html(msg)


# ─── Groq LLM ────────────────────────────────────────────────────────────────

GROQ_SYSTEM_PROMPT = (
    "Ты полезный ассистент в Telegram-группе. "
    "Отвечай коротко, по делу, на русском языке. "
    "Максимум 3-4 предложения если не просят подробнее. "
    "Не используй markdown — только обычный текст."
)


async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Задать вопрос LLM через Groq API (бесплатный тир)."""
    if not GROQ_API_KEY:
        await update.message.reply_text(
            "⚠️ Groq API ключ не настроен.\n"
            "Добавь GROQ_API_KEY в переменные окружения на Railway."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "🤖 Задай мне вопрос!\n"
            "Пример: /ask Почему небо голубое?"
        )
        return

    question = " ".join(context.args)
    user = update.effective_user
    thinking_msg = await update.message.reply_text("🤔 Думаю...")

    try:
        payload = {
            "model":       "llama-3.3-70b-versatile",   # актуальная модель Groq
            "messages":    [
                {"role": "system",  "content": GROQ_SYSTEM_PROMPT},
                {"role": "user",    "content": question},
            ],
            "max_tokens":  512,
            "temperature": 0.7,
        }
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type":  "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    raise ValueError(f"HTTP {resp.status}: {err[:100]}")
                data = await resp.json()

        answer = data["choices"][0]["message"]["content"].strip()
        logger.info(f"Groq /ask | user={user.id} | q={question[:50]!r}")

        msg = (
            f"🤖 <b>Вопрос:</b> {question}\n\n"
            f"{answer}"
        )
        await thinking_msg.edit_text(msg, parse_mode="HTML")

    except Exception as e:
        logger.warning(f"Groq error: {e}")
        await thinking_msg.edit_text(
            "⚠️ Не удалось получить ответ. Попробуй позже!"
        )


# ─── Логирование использования ────────────────────────────────────────────────

async def log_usage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Middleware: логирует каждое использование бота — кто, где, что."""
    if not update.message and not update.callback_query:
        return

    msg = update.message or (update.callback_query.message if update.callback_query else None)
    user = update.effective_user
    chat = update.effective_chat

    if not user:
        return

    # ── Кто ──────────────────────────────────────────────────────────────────
    user_info = f"@{user.username}" if user.username else f"id={user.id}"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "N/A"

    # ── Где ───────────────────────────────────────────────────────────────────
    chat_types = {
        "private":    "💬 Личка",
        "group":      "👥 Группа",
        "supergroup": "👥 Супергруппа",
        "channel":    "📢 Канал",
    }
    chat_type_label = chat_types.get(chat.type, chat.type)
    chat_name = chat.title if chat.title else "—"
    chat_id_val = chat.id

    # ── Что ───────────────────────────────────────────────────────────────────
    if update.message and update.message.text:
        text = update.message.text[:60]  # обрезаем длинные сообщения
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


# ─── Запуск ───────────────────────────────────────────────────────────────────

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
    app.add_handler(CommandHandler("news",      news))
    app.add_handler(CommandHandler("joke",      joke))
    app.add_handler(CommandHandler("advice",    advice))
    app.add_handler(CommandHandler("ask",       ask))

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