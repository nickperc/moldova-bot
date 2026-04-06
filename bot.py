import os
import re as _re
import random
import logging
import asyncio
import aiohttp
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, time as dtime
from bs4 import BeautifulSoup
from telegram import Update, Poll, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ChatMemberHandler,
)

from artemis import get_artemis_data, get_artemis_text
from artemis_viz import generate_position_map
# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Token ───────────────────────────────────────────────────────────────────
BOT_TOKEN       = os.getenv("BOT_TOKEN",       "YOUR_BOT_TOKEN_HERE")
GROQ_API_KEY    = os.getenv("GROQ_API_KEY",    "")
CMC_API_KEY     = os.getenv("CMC_API_KEY",     "")
XAI_API_KEY     = os.getenv("XAI_API_KEY",     "")
AIRLABS_API_KEY  = os.getenv("AIRLABS_API_KEY", "")
MORNING_CHAT_ID  = int(os.getenv("MORNING_CHAT_ID", "0"))

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
        "🌙 <b>Космос</b>\n"
        "/artemis — Лунная программа NASA: позиция, телеметрия, экипаж 🌙\n\n"
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
    from zoneinfo import ZoneInfo
    chisinau_tz = ZoneInfo("Europe/Chisinau")
    chisinau_time = datetime.now(chisinau_tz)
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


def _wmo_icon(code: int) -> str:
    """Конвертирует WMO weather code в emoji."""
    if code == 0:                        return "☀️"
    if code in (1, 2):                   return "🌤️"
    if code == 3:                        return "☁️"
    if code in (45, 48):                 return "🌫️"
    if code in (51, 53, 55):             return "🌦️"
    if code in (61, 63, 65):             return "🌧️"
    if code in (71, 73, 75, 77):         return "❄️"
    if code in (80, 81, 82):             return "🌧️"
    if code in (85, 86):                 return "🌨️"
    if code in (95, 96, 99):             return "⛈️"
    return "🌡️"

def _wmo_desc(code: int) -> str:
    """WMO code → описание на русском."""
    descriptions = {
        0: "Ясно", 1: "Преимущественно ясно", 2: "Переменная облачность",
        3: "Пасмурно", 45: "Туман", 48: "Изморозь",
        51: "Лёгкая морось", 53: "Морось", 55: "Сильная морось",
        61: "Небольшой дождь", 63: "Дождь", 65: "Сильный дождь",
        71: "Небольшой снег", 73: "Снег", 75: "Сильный снег", 77: "Снежная крупа",
        80: "Ливень", 81: "Сильный ливень", 82: "Очень сильный ливень",
        85: "Небольшой снегопад", 86: "Сильный снегопад",
        95: "Гроза", 96: "Гроза с градом", 99: "Гроза с сильным градом",
    }
    return descriptions.get(code, "Неизвестно")

def _wind_dir(deg: float) -> str:
    """Градусы → направление ветра."""
    dirs = ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"]
    return dirs[round(deg / 45) % 8]

def _uv_label(uv: float) -> str:
    if uv < 3:   return "Низкий"
    if uv < 6:   return "Умеренный"
    if uv < 8:   return "Высокий"
    if uv < 11:  return "Очень высокий"
    return "Экстремальный"


async def _geocode(session: aiohttp.ClientSession, city: str) -> tuple[float, float, str]:
    """Nominatim: название города → (lat, lon, display_name)."""
    params = {"q": city, "format": "json", "limit": 1, "accept-language": "ru"}
    headers = {"User-Agent": "MoldovaBot/1.0 (telegram bot)"}
    async with session.get(
        "https://nominatim.openstreetmap.org/search",
        params=params, headers=headers,
        timeout=aiohttp.ClientTimeout(total=8),
    ) as r:
        results = await r.json()
    if not results:
        raise ValueError(f"Город «{city}» не найден")
    r0 = results[0]
    name = r0.get("display_name", city).split(",")[0].strip()
    return float(r0["lat"]), float(r0["lon"]), name


async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Погода через Open-Meteo (бесплатно, без ключа).
    /weather              → текущая погода в Кишинёве
    /weather <город>      → текущая погода в любом городе
    /weather forecast     → прогноз на 3 дня для Кишинёва
    /weather <город> forecast → прогноз на 3 дня для города
    """
    args = context.args or []

    # Разбираем аргументы
    if "forecast" in [a.lower() for a in args]:
        show_forecast = True
        city_parts = [a for a in args if a.lower() != "forecast"]
    else:
        show_forecast = False
        city_parts = args

    city_query = " ".join(city_parts) if city_parts else "Кишинёв"

    try:
        async with aiohttp.ClientSession() as session:
            # ── Геокодинг ─────────────────────────────────────────────────────
            lat, lon, city_name = await _geocode(session, city_query)

            # ── Open-Meteo запрос ─────────────────────────────────────────────
            params = {
                "latitude":            lat,
                "longitude":           lon,
                "current":             "temperature_2m,apparent_temperature,relative_humidity_2m,"
                                       "wind_speed_10m,wind_direction_10m,weather_code,"
                                       "uv_index,precipitation,surface_pressure",
                "daily":               "weather_code,temperature_2m_max,temperature_2m_min,"
                                       "precipitation_sum,wind_speed_10m_max,"
                                       "sunrise,sunset,uv_index_max",
                "timezone":            "auto",
                "forecast_days":       4,
                "wind_speed_unit":     "kmh",
            }
            async with session.get(
                "https://api.open-meteo.com/v1/forecast",
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    raise ValueError(f"Open-Meteo HTTP {resp.status}")
                om = await resp.json()

        cur = om["current"]
        daily = om["daily"]

        temp      = cur["temperature_2m"]
        feels     = cur["apparent_temperature"]
        humidity  = cur["relative_humidity_2m"]
        wind_spd  = cur["wind_speed_10m"]
        wind_deg  = cur["wind_direction_10m"]
        wcode     = cur["weather_code"]
        uv        = cur.get("uv_index") or 0
        precip    = cur.get("precipitation") or 0
        pressure  = cur.get("surface_pressure") or 0

        icon = _wmo_icon(wcode)
        desc = _wmo_desc(wcode)
        wdir = _wind_dir(wind_deg)

        # Восход/закат — берём сегодня (индекс 0)
        sunrise = daily["sunrise"][0].split("T")[1] if daily.get("sunrise") else "—"
        sunset  = daily["sunset"][0].split("T")[1]  if daily.get("sunset")  else "—"

        # ── Текущая погода ────────────────────────────────────────────────────
        msg = (
            f"{icon} <b>Погода в {city_name}</b>\n\n"
            f"🌡️ Температура: <b>{temp:.0f}°C</b> (ощущается как {feels:.0f}°C)\n"
            f"☁️ Состояние: {desc}\n"
            f"💧 Влажность: {humidity}%\n"
            f"💨 Ветер: {wind_spd / 3.6:.1f} м/с {wdir}\n"
            f"🔵 Давление: {pressure:.0f} гПа\n"
            f"🌂 Осадки: {precip:.1f} мм\n"
            f"☀️ UV-индекс: {uv:.0f} ({_uv_label(uv)})\n"
            f"🌅 Восход: {sunrise}  🌇 Закат: {sunset}\n\n"
        )

        # ── Прогноз на 3 дня ─────────────────────────────────────────────────
        if show_forecast:
            day_names = ["Сегодня", "Завтра", "Послезавтра"]
            forecast_lines = "📅 <b>Прогноз на 3 дня:</b>\n"
            for i in range(3):
                d_code  = daily["weather_code"][i]
                d_max   = daily["temperature_2m_max"][i]
                d_min   = daily["temperature_2m_min"][i]
                d_prec  = daily.get("precipitation_sum", [0]*4)[i] or 0
                d_wind  = daily.get("wind_speed_10m_max", [0]*4)[i] or 0
                d_icon  = _wmo_icon(d_code)
                d_desc  = _wmo_desc(d_code)
                forecast_lines += (
                    f"\n{d_icon} <b>{day_names[i]}</b>\n"
                    f"   🌡️ {d_min:.0f}°C … {d_max:.0f}°C\n"
                    f"   ☁️ {d_desc}\n"
                    f"   🌂 {d_prec:.1f} мм  💨 {d_wind / 3.6:.1f} м/с\n"
                )
            msg += forecast_lines + "\n"
        else:
            msg += "<i>Прогноз на 3 дня: /weather forecast</i>\n"

        msg += "\n<i>Источник: Open-Meteo · OpenStreetMap</i>"

    except ValueError as e:
        msg = f"⚠️ {e}"
    except Exception as e:
        logger.warning(f"Weather error: {e}")
        msg = "⚠️ Не удалось получить погоду. Попробуй позже!"

    await update.message.reply_html(msg)


async def _fetch_bnm_rates() -> tuple[dict[str, float], str]:
    """
    Fetches official BNM (National Bank of Moldova) exchange rates via XML feed.
    Returns ({CharCode: mdl_per_1_unit}, date_str).
    Nominal is already divided out — all values are MDL per 1 unit.
    """
    today = datetime.now().strftime("%d.%m.%Y")
    url = f"https://www.bnm.md/en/official_exchange_rates?get_xml=1&date={today}"
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url,
            headers={"User-Agent": "MoldovaBot/1.0"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                raise ValueError(f"BNM HTTP {resp.status}")
            raw = await resp.read()

    root = ET.fromstring(raw)
    date_str = root.get("Date", "")  # BNM uses capital D
    rates: dict[str, float] = {}
    for v in root.findall("Valute"):
        code_el    = v.find("CharCode")
        nominal_el = v.find("Nominal")
        val_el     = v.find("Value")
        if code_el is None or val_el is None:
            continue
        code = (code_el.text or "").strip()
        mult = int(nominal_el.text) if nominal_el is not None and nominal_el.text else 1
        try:
            val = float((val_el.text or "").replace(",", "."))
            rates[code] = val / mult  # normalise to per 1 unit
        except ValueError:
            pass
    return rates, date_str


async def mdl_rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Официальный курс НБМ (Нацбанка Молдовы)."""
    try:
        rates, date_str = await _fetch_bnm_rates()

        def r(code: str, digits: int = 2) -> str:
            v = rates.get(code)
            return f"{v:.{digits}f}" if v else "—"

        # AED: if BNM has it use it; otherwise derive from USD peg (1 USD = 3.6725 AED)
        aed_mdl = rates.get("AED") or (rates["USD"] / 3.6725 if "USD" in rates else None)

        def cross(base: str, quote: str) -> str:
            """How many `quote` units per 1 `base` unit."""
            b = rates.get(base)
            q = rates.get(quote) or (rates.get("USD", 0) / 3.6725 if quote == "AED" else None)
            if b and q:
                return f"{b/q:.2f}"
            return "—"

        aed_line = f"🇦🇪 1 AED = <b>{aed_mdl:.2f} MDL</b>" if aed_mdl else ""
        rub10 = f"{rates['RUB'] * 10:.2f}" if "RUB" in rates else "—"
        uah10 = f"{rates['UAH'] * 10:.2f}" if "UAH" in rates else "—"

        msg = (
            f"💵 <b>Официальный курс НБМ</b> · <i>{date_str}</i>\n\n"
            f"🇺🇸 1 USD = <b>{r('USD')} MDL</b>  ·  {aed_line}\n"
            f"🇪🇺 1 EUR = <b>{r('EUR')} MDL</b>\n"
            f"🇬🇧 1 GBP = <b>{r('GBP')} MDL</b>  ·  🇨🇭 1 CHF = <b>{r('CHF')} MDL</b>\n"
            f"🇮🇱 1 ILS = <b>{r('ILS')} MDL</b>  ·  🇷🇴 1 RON = <b>{r('RON')} MDL</b>\n\n"
            f"🇷🇺 10 RUB = <b>{rub10} MDL</b>\n"
            f"🇺🇦 10 UAH = <b>{uah10} MDL</b>\n"
            f"🇹🇷 1 TRY = <b>{r('TRY')} MDL</b>\n\n"
            f"<i>Источник: bnm.md</i>"
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

        from zoneinfo import ZoneInfo
        fetched_at = datetime.now(ZoneInfo("Europe/Chisinau")).strftime("%d.%m.%Y %H:%M")

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
    """
    Индекс альтсезона по методологии blockchaincenter.net.
    Берём топ-50 монет из listings/latest, убираем BTC и стейблы,
    считаем сколько из них обогнали BTC за 90 дней.
    index = (outperformed / total) * 100
    Если ≥ 75% — альтсезон.
    """
    STABLECOINS = {
        "USDT", "USDC", "BUSD", "DAI", "TUSD", "USDP", "USDD",
        "FRAX", "LUSD", "GUSD", "FDUSD", "PYUSD", "USDE",
    }
    CMC_HEADERS = {"X-CMC_PRO_API_KEY": CMC_API_KEY}

    try:
        params = {
            "limit":   108,
            "convert": "USD",
            "sort":    "market_cap",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest",
                headers=CMC_HEADERS,
                params=params,
                timeout=aiohttp.ClientTimeout(total=12),
            ) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                data = await resp.json()

        listings = data.get("data", [])
        if not listings:
            raise ValueError("Пустой ответ от API")

        # ── BTC 90d % ─────────────────────────────────────────────────────────
        btc_entry = next((c for c in listings if c["symbol"] == "BTC"), None)
        if not btc_entry:
            raise ValueError("BTC не найден в listings")

        btc_90d = (
            btc_entry.get("quote", {})
            .get("USD", {})
            .get("percent_change_90d") or 0.0
        )
        btc_dominance = (
            btc_entry.get("quote", {})
            .get("USD", {})
            .get("market_cap_dominance") or 0.0
        )

        # ── Фильтруем альткоины ───────────────────────────────────────────────
        alts = [
            c for c in listings
            if c["symbol"] not in STABLECOINS | {"BTC"}
        ]

        # ── Считаем сколько обогнали BTC за 90д ──────────────────────────────
        alts_with_data = [
            c for c in alts
            if c.get("quote", {}).get("USD", {}).get("percent_change_90d") is not None
        ]
        outperformed = sum(
            1 for c in alts_with_data
            if c["quote"]["USD"]["percent_change_90d"] > btc_90d
        )
        total = len(alts_with_data)
        index = round((outperformed / total) * 100) if total else 0

        # ── Топ-3 самых сильных алта за 90д ──────────────────────────────────
        top_alts = sorted(
            alts_with_data,
            key=lambda c: c["quote"]["USD"]["percent_change_90d"],
            reverse=True,
        )[:3]
        top_lines = ""
        for c in top_alts:
            chg = c["quote"]["USD"]["percent_change_90d"]
            sign = "+" if chg >= 0 else ""
            top_lines += f"  • {c['symbol']}: {sign}{chg:.1f}%\n"

        # ── Статус ───────────────────────────────────────────────────────────
        if index >= 75:
            status      = "🚀 <b>АЛЬТСЕЗОН!</b>"
            description = "Более 75% топ-альтов обогнали Bitcoin за 90 дней."
            verdict     = "🔥 Альтсезон в разгаре — исторически лучшее время для альтов!"
        elif index >= 55:
            status      = "⚡ <b>Начало альтсезона</b>"
            description = "Больше половины альтов обгоняют BTC."
            verdict     = "📈 Рынок разогревается. Следи за альтами внимательно."
        elif index >= 40:
            status      = "😐 <b>Нейтральный рынок</b>"
            description = "Нет явного доминирования ни BTC, ни альтов."
            verdict     = "🤷 Жди чёткого сигнала — пока рынок в равновесии."
        elif index >= 25:
            status      = "🟡 <b>Сезон Bitcoin</b>"
            description = "BTC доминирует, большинство альтов отстают."
            verdict     = "⚠️ Альты под давлением — осторожно с покупками."
        else:
            status      = "🟠 <b>Глубокий сезон Bitcoin</b>"
            description = "BTC значительно обгоняет альты."
            verdict     = "🛑 Альты страдают. Лучше подождать разворота."

        # ── Визуальная шкала ─────────────────────────────────────────────────
        filled    = round(index / 10)
        bar       = "█" * filled + "░" * (10 - filled)
        btc_sign  = "+" if btc_90d >= 0 else ""
        btc_arrow = "🟢" if btc_90d >= 0 else "🔴"

        msg = (
            "🌡️ <b>Индекс Альтсезона</b>\n\n"
            f"{status}\n"
            f"<code>[{bar}] {index}/100</code>\n\n"
            f"📊 {outperformed} из {total} альтов обогнали BTC за 90 дней\n"
            f"₿  BTC за 90 дней: {btc_arrow} {btc_sign}{btc_90d:.1f}%\n"
            f"📉 BTC доминация: {btc_dominance:.2f}%\n\n"
            f"🏅 <b>Топ альты за 90д:</b>\n{top_lines}\n"
            f"ℹ️ {description}\n\n"
            f"{verdict}\n\n"
            "<i>Методология: blockchaincenter.net · Данные: CoinMarketCap</i>"
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


# ─── Рейсы KIV ───────────────────────────────────────────────────────────────

_AIRLABS_SCHEDULES_URL = "https://airlabs.co/api/v9/schedules"
_AIRLABS_FLIGHTS_URL   = "https://airlabs.co/api/v9/flights"


def _parse_hhmm(dt_str: str | None) -> str:
    """Extract HH:MM from 'YYYY-MM-DD HH:MM' string."""
    if not dt_str:
        return "—"
    try:
        return datetime.strptime(dt_str[:16], "%Y-%m-%d %H:%M").strftime("%H:%M")
    except ValueError:
        return dt_str[:5]


async def _airlabs_get(endpoint: str, params: dict) -> dict:
    """Fetch JSON from an AirLabs endpoint, injecting the API key."""
    params = {**params, "api_key": AIRLABS_API_KEY}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            endpoint,
            params=params,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                raise ValueError(f"HTTP {resp.status}")
            return await resp.json(content_type=None)


def _build_summary_board(flights_list: list[dict], is_arrival: bool, now_str: str) -> str:
    """Format flights into a grouped summary board (Option 3)."""
    time_field   = "arr_time"   if is_arrival else "dep_time"
    actual_field = "arr_actual" if is_arrival else "dep_actual"
    airport_key  = "dep_iata"   if is_arrival else "arr_iata"
    arrow        = "из"         if is_arrival else "→"

    in_air:    list[str] = []
    upcoming:  list[str] = []
    delayed:   list[str] = []
    cancelled: list[str] = []
    done:      list[str] = []

    flights_list.sort(key=lambda f: f.get(time_field) or "")

    for f in flights_list:
        no      = f.get("flight_iata") or f.get("flight_icao") or "—"
        airport = f.get(airport_key) or "—"
        status  = (f.get("status") or "").lower()
        delay   = f.get("delayed") or 0
        sched   = _parse_hhmm(f.get(time_field))
        actual  = _parse_hhmm(f.get(actual_field))
        t       = actual if actual != "—" else sched

        if status == "cancelled":
            cancelled.append(f"{no} {arrow} {airport}")
        elif status in ("en-route", "active"):
            label = "вылет" if not is_arrival else "вылет из"
            in_air.append(f"{no} {arrow} {airport} ({label} {t})")
        elif status == "landed":
            done.append(f"{no} {arrow} {airport} ({t})")
        else:
            if delay and int(delay) > 0:
                delayed.append(f"{no} {arrow} {airport}  {sched} <i>+{delay} мин</i>")
            else:
                upcoming.append(f"{no} {arrow} {airport}  {sched}")

    direction = "Прилёты" if is_arrival else "Вылеты"
    sections: list[str] = [f"✈️ <b>КИШ {direction}</b> · {now_str}"]

    if in_air:
        label = "🛬 Сейчас в воздухе:" if is_arrival else "✈️ Сейчас в воздухе:"
        sections.append(label + "\n" + "\n".join(f"  • {x}" for x in in_air))

    if upcoming:
        label = "🕐 Ближайшие прилёты:" if is_arrival else "🕐 Ближайшие вылеты:"
        body = "\n".join(f"  • {x}" for x in upcoming[:8])
        tail = f"\n  <i>...и ещё {len(upcoming) - 8}</i>" if len(upcoming) > 8 else ""
        sections.append(label + "\n" + body + tail)

    if delayed:
        sections.append("⏱ Задержаны:\n" + "\n".join(f"  • {x}" for x in delayed))

    if cancelled:
        sections.append("❌ Отменены: " + ",  ".join(cancelled))

    if done and not (in_air or upcoming or delayed or cancelled):
        body = "\n".join(f"  • {x}" for x in done[:5])
        sections.append("🛬 Уже приземлились:\n" + body)

    return "\n\n".join(sections)


async def flights(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/flights [arr] — сводное табло вылетов/прилётов KIV."""
    if not AIRLABS_API_KEY:
        await update.message.reply_text(
            "⚠️ Ключ AirLabs не задан. Установи AIRLABS_API_KEY."
        )
        return

    arg = (context.args[0].lower() if context.args else "dep")
    is_arrival = arg == "arr"
    param_key = "arr_iata" if is_arrival else "dep_iata"
    direction_label = "прилёты" if is_arrival else "вылеты"

    status_msg = await update.message.reply_text(f"✈️ Загружаю {direction_label} KIV...")

    try:
        from zoneinfo import ZoneInfo
        now_str = datetime.now(ZoneInfo("Europe/Chisinau")).strftime("%d.%m %H:%M")

        data = await _airlabs_get(_AIRLABS_SCHEDULES_URL, {param_key: "KIV"})
        flights_list: list[dict] = data.get("response", [])

        if not flights_list:
            await status_msg.edit_text(
                "😔 Нет данных о рейсах. Возможно, API временно недоступен."
            )
            return

        msg = _build_summary_board(flights_list, is_arrival, now_str)
        await status_msg.edit_text(msg, parse_mode="HTML")

    except Exception as e:
        logger.warning(f"AirLabs flights error: {e}")
        await status_msg.edit_text("⚠️ Не удалось получить данные о рейсах. Попробуй позже!")


async def kiv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/kiv <рейс> — детальная карточка конкретного рейса.

    /kiv TK276
    """
    if not AIRLABS_API_KEY:
        await update.message.reply_text(
            "⚠️ Ключ AirLabs не задан. Установи AIRLABS_API_KEY."
        )
        return

    if not context.args:
        await update.message.reply_text("✈️ Укажи номер рейса: /kiv TK276")
        return

    flight_no = context.args[0].upper()
    status_msg = await update.message.reply_text(f"🔍 Ищу рейс {flight_no}...")

    try:
        # Try real-time flights endpoint first (works for airborne flights)
        data = await _airlabs_get(_AIRLABS_FLIGHTS_URL, {"flight_iata": flight_no})
        result: list[dict] = data.get("response", [])

        # Fallback: search KIV schedules (covers pre-departure & landed)
        if not result:
            dep_data = await _airlabs_get(_AIRLABS_SCHEDULES_URL, {"dep_iata": "KIV"})
            arr_data = await _airlabs_get(_AIRLABS_SCHEDULES_URL, {"arr_iata": "KIV"})
            all_sched = dep_data.get("response", []) + arr_data.get("response", [])
            result = [f for f in all_sched if (f.get("flight_iata") or "").upper() == flight_no]

        if not result:
            await status_msg.edit_text(
                f"❓ Рейс <b>{flight_no}</b> не найден в расписании KIV.",
                parse_mode="HTML",
            )
            return

        f = result[0]

        dep_sched    = _parse_hhmm(f.get("dep_time"))
        arr_sched    = _parse_hhmm(f.get("arr_time"))
        dep_actual   = _parse_hhmm(f.get("dep_actual"))
        arr_actual   = _parse_hhmm(f.get("arr_actual"))
        dep_terminal = f.get("dep_terminal") or "—"
        dep_gate     = f.get("dep_gate") or "—"
        arr_terminal = f.get("arr_terminal") or "—"
        arr_gate     = f.get("arr_gate") or "—"
        status_raw   = (f.get("status") or "unknown").lower()
        delay        = f.get("delayed")

        date_raw = f.get("dep_time") or f.get("arr_time") or ""
        try:
            date_str = datetime.strptime(date_raw[:10], "%Y-%m-%d").strftime("%d %b")
        except ValueError:
            date_str = date_raw[:10] or "—"

        status_icons = {
            "scheduled": "🟢 По расписанию",
            "en-route":  "✈️ В воздухе",
            "active":    "✈️ В воздухе",
            "landed":    "🛬 Приземлился",
            "cancelled": "🔴 Отменён",
            "diverted":  "↩️ Перенаправлен",
            "incident":  "⚠️ Инцидент",
        }
        status_str = status_icons.get(status_raw, f"❓ {status_raw}")
        delay_line = f"\n⏱ <b>+{delay} мин задержки</b>" if delay and int(delay) > 0 else ""

        dep_actual_str = f"  <i>(факт: {dep_actual})</i>" if dep_actual != "—" else ""
        arr_actual_str = f"  <i>(факт: {arr_actual})</i>" if arr_actual != "—" else ""

        msg = (
            f"✈️ <b>{f.get('flight_iata') or flight_no}</b> · {f.get('airline_iata') or '—'}\n"
            f"🛫 {f.get('dep_iata') or '—'} → {f.get('arr_iata') or '—'}\n"
            f"📅 {date_str}\n\n"
            f"🛫 Вылет:   <b>{dep_sched}</b>{dep_actual_str}\n"
            f"🛬 Прилёт:  <b>{arr_sched}</b>{arr_actual_str}\n\n"
            f"🚪 Терм. вылета:  {dep_terminal} · Выход: {dep_gate}\n"
            f"🚪 Терм. прилёта: {arr_terminal} · Выход: {arr_gate}\n\n"
            f"{status_str}{delay_line}"
        )
        await status_msg.edit_text(msg, parse_mode="HTML")

    except Exception as e:
        logger.warning(f"AirLabs kiv error: {e}")
        await status_msg.edit_text("⚠️ Не удалось получить данные о рейсе. Попробуй позже!")




# ─── Кино (Cineplex) ─────────────────────────────────────────────────────────
# APIs used:
#   GET /api/getEventsForDate/{YYYY-MM-DD}/{cinema_id}  → today's schedule
#   GET /api/getFilterDates                             → available dates
#   GET /api/getEventRoomForCinema/{event_id}/{cinema_id} → seat prices
# Cinema IDs: 1 = Cineplex Loteanu, 2 = Cineplex Mall

_CINEPLEX_CINEMAS = {
    "mall":    (2, "Cineplex Mall"),
    "loteanu": (1, "Cineplex Loteanu"),
}

_MONTHS_RU = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]

_WEEKDAYS_RO_RU = {
    "luni": "Пн", "marți": "Вт", "miercuri": "Ср",
    "joi": "Чт", "vineri": "Пт", "sâmbătă": "Сб", "duminică": "Вс",
}

_LANG_LABELS = {"RU": "🇷🇺 рус.", "RO": "🇷🇴 рум.", "EN": "🇬🇧 англ."}

_WEEKDAYS_RU_FULL = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def _fmt_duration(minutes_str: str) -> str:
    """'197' → '3 ч 17 мин'  |  '90' → '1 ч 30 мин'  |  '' → ''"""
    try:
        m = int(minutes_str)
    except (ValueError, TypeError):
        return ""
    h, mins = divmod(m, 60)
    if h and mins:
        return f"{h} ч {mins} мин"
    if h:
        return f"{h} ч"
    return f"{mins} мин"

_CINEPLEX_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
}


async def _fetch_cinema_events(cinema_id: int, date: str) -> list[dict]:
    url = f"https://cineplex.md/api/getEventsForDate/{date}/{cinema_id}"
    async with aiohttp.ClientSession(headers=_CINEPLEX_HEADERS) as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    return data.get("events", [])


async def _fetch_available_dates() -> list[dict]:
    async with aiohttp.ClientSession(headers=_CINEPLEX_HEADERS) as session:
        async with session.get(
            "https://cineplex.md/api/getFilterDates",
            timeout=aiohttp.ClientTimeout(total=8),
        ) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)


async def _fetch_room_prices(events: list[dict], cinema_id: int) -> dict[str, str]:
    """Fetch ticket price for each unique room in parallel. Returns {id_room: price}."""
    room_to_event: dict[str, str] = {}
    for ev in events:
        rid = ev.get("id_room", "")
        if rid and rid not in room_to_event:
            room_to_event[rid] = ev["id_event"]

    async def _one(session: aiohttp.ClientSession, room_id: str, event_id: str) -> tuple[str, str]:
        try:
            url = f"https://cineplex.md/api/getEventRoomForCinema/{event_id}/{cinema_id}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json(content_type=None)
            for row in data.get("room", {}).get("seats", {}).values():
                for seat in row.values():
                    p = seat.get("price")
                    if p:
                        return room_id, str(int(float(p)))
        except Exception:
            pass
        return room_id, "?"

    async with aiohttp.ClientSession(headers=_CINEPLEX_HEADERS) as session:
        results = await asyncio.gather(*[
            _one(session, rid, eid) for rid, eid in room_to_event.items()
        ])
    return dict(results)


def _cinema_keyboard(dates: list[dict], selected: str, cinema_key: str) -> InlineKeyboardMarkup:
    from zoneinfo import ZoneInfo
    today    = datetime.now(ZoneInfo("Europe/Chisinau")).strftime("%Y-%m-%d")
    tomorrow = (datetime.now(ZoneInfo("Europe/Chisinau")) + timedelta(days=1)).strftime("%Y-%m-%d")

    buttons = []
    for d in dates:
        val  = d["date"]
        day  = d["day"][:2]
        wday = _WEEKDAYS_RO_RU.get(d["week"].lower(), d["week"][:2])
        if val == today:
            label = "Сегодня"
        elif val == tomorrow:
            label = "Завтра"
        else:
            label = f"{wday} {day}"
        if val == selected:
            label = f"· {label} ·"
        buttons.append(InlineKeyboardButton(label, callback_data=f"cinema:{cinema_key}:{val}"))

    rows = [buttons[i:i + 4] for i in range(0, len(buttons), 4)]
    return InlineKeyboardMarkup(rows)


def _format_cinema_schedule(
    events: list[dict],
    prices: dict[str, str],
    cinema_name: str,
    date: str,
) -> str:
    if not events:
        return "📭 Сеансов на выбранную дату не найдено."

    # ── Header ────────────────────────────────────────────────────────────────
    try:
        d = datetime.strptime(date, "%Y-%m-%d")
        wday = _WEEKDAYS_RU_FULL[d.weekday()]
        date_display = f"{d.day} {_MONTHS_RU[d.month - 1]}, {wday}"
    except ValueError:
        date_display = date

    # ── Group events by movie (insertion order = chronological) ───────────────
    movies: dict[str, dict] = {}
    for ev in events:
        mid = ev.get("id_movie", "")
        if mid not in movies:
            movies[mid] = {
                "title":    ev.get("title_ru") or ev.get("title") or "—",
                "length":   ev.get("length", ""),
                "formats":  set(),
                "langs":    set(),
                "sessions": [],     # [(time, price, booking_url)]
            }
        movies[mid]["formats"].add((ev.get("format") or "").strip().rstrip("."))
        movies[mid]["langs"].add(ev.get("language", ""))

        dt_raw = ev.get("date", "")
        try:
            t = datetime.strptime(dt_raw, "%Y-%m-%d %H:%M:%S").strftime("%H:%M")
        except ValueError:
            t = dt_raw[11:16] if len(dt_raw) >= 16 else "??"

        price = prices.get(ev.get("id_room", ""), "?")
        url = (
            f"https://cineplex.md/movie/{ev.get('id_movie')}"
            f"/{ev.get('id_cinema')}/{ev.get('id_event')}/0/"
        )
        movies[mid]["sessions"].append((t, price, url))

    # ── Build message ─────────────────────────────────────────────────────────
    # Format:
    #   🎬 Cineplex Mall · 1 апреля, Ср
    #
    #   🎥 Название фильма
    #   3D · рус. · 3 ч 17 мин
    #   🎟 85 MDL: 10:40 · 14:30
    #   🎟 110 MDL: 18:00 · 21:30
    #
    #   🎥 Другой фильм
    #   ...

    parts = [f"🎬 <b>{cinema_name}</b> · {date_display}"]

    for m in movies.values():
        fmt_str  = "/".join(sorted(f for f in m["formats"] if f))
        lang_str = " · ".join(_LANG_LABELS.get(l, l) for l in sorted(m["langs"]) if l)
        dur_str  = _fmt_duration(m["length"])
        meta     = " · ".join(x for x in [fmt_str, lang_str, dur_str] if x)

        # Group sessions by price tier, preserving time order
        by_price: dict[str, list[tuple[str, str]]] = {}
        for t, price, url in m["sessions"]:
            by_price.setdefault(price, []).append((t, url))

        session_lines = []
        for price, sessions in by_price.items():
            times = "  ".join(f'<a href="{url}">{t}</a>' for t, url in sessions)
            session_lines.append(f"🎟 {price} MDL:  {times}")

        block = f"🎥 <b>{m['title']}</b>"
        if meta:
            block += f"\n<i>{meta}</i>"
        block += "\n" + "\n".join(session_lines)

        parts.append(block)

    return "\n\n".join(parts)


async def _cinema_render(cinema_key: str, date: str) -> tuple[str, InlineKeyboardMarkup]:
    cinema_id, cinema_name = _CINEPLEX_CINEMAS[cinema_key]
    events, dates = await asyncio.gather(
        _fetch_cinema_events(cinema_id, date),
        _fetch_available_dates(),
    )
    prices = await _fetch_room_prices(events, cinema_id) if events else {}
    text     = _format_cinema_schedule(events, prices, cinema_name, date)
    keyboard = _cinema_keyboard(dates, date, cinema_key)
    return text, keyboard


async def cinema(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/cinema [loteanu] — расписание Cineplex с выбором дня.

    /cinema         → Cineplex Mall
    /cinema loteanu → Cineplex Loteanu
    """
    arg = (context.args[0].lower() if context.args else "mall")
    if arg not in _CINEPLEX_CINEMAS:
        await update.message.reply_text(
            "❓ Неизвестный кинотеатр. Используй: /cinema или /cinema loteanu"
        )
        return

    status_msg = await update.message.reply_text("⏳ Загружаю расписание...")
    try:
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("Europe/Chisinau")).strftime("%Y-%m-%d")
        text, keyboard = await _cinema_render(arg, today)
        await status_msg.edit_text(
            text, parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
    except aiohttp.ClientError as e:
        logger.warning(f"Cinema network error: {e}")
        await status_msg.edit_text("❌ Не удалось загрузить расписание. Попробуй позже.")
    except Exception as e:
        logger.warning(f"Cinema error: {e}")
        await status_msg.edit_text("❌ Не удалось загрузить расписание. Попробуй позже.")


async def cinema_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inline button: cinema:{mall|loteanu}:{YYYY-MM-DD}"""
    query = update.callback_query
    await query.answer()

    try:
        _, cinema_key, date = query.data.split(":")
    except ValueError:
        return
    if cinema_key not in _CINEPLEX_CINEMAS:
        return

    await query.edit_message_text("⏳ Загружаю расписание...", parse_mode="HTML")
    try:
        text, keyboard = await _cinema_render(cinema_key, date)
        await query.edit_message_text(
            text, parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.warning(f"Cinema callback error: {e}")
        await query.edit_message_text("❌ Не удалось загрузить расписание. Попробуй позже.")


# ─── Groq LLM ────────────────────────────────────────────────────────────────

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


# ─── /beer — Linella пиво со скидкой ─────────────────────────────────────────

_LINELLA_BEER_BASE  = "https://linella.md"
_LINELLA_BEER_PROMO = "https://linella.md/en/catalog/beer?filter%5Bp%5D=on"

_BEER_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
}


def _beer_volume_ml(name: str) -> float | None:
    """Extract volume in ml from product name. Returns None if not found."""
    text = name.lower()
    m = _re.search(r'(\d+(?:[.,]\d+)?)\s*ml\b', text)
    if m:
        return float(m.group(1).replace(",", "."))
    m = _re.search(r'(\d+(?:[.,]\d+)?)\s*l\b', text)
    if m:
        return float(m.group(1).replace(",", ".")) * 1000
    return None


def _beer_price(text: str) -> float | None:
    m = _re.search(r'(\d+[.,]\d+)', text.replace(" ", ""))
    return float(m.group(1).replace(",", ".")) if m else None


def _parse_beer_page(html: str) -> tuple[list[dict], int]:
    """Returns (qualifying_products, total_cards_on_page)."""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.products-catalog-content__item")
    products = []
    for card in cards:
        try:
            name_el = card.select_one("a.products-catalog-content__name")
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            href = name_el.get("href", "")
            url = (_LINELLA_BEER_BASE + href) if href.startswith("/") else href

            vol = _beer_volume_ml(name)
            if vol is None:
                logger.debug(f"Beer skip (no volume): {name!r}")
                continue
            if vol > 700:
                logger.debug(f"Beer skip (vol {vol}ml > 700): {name!r}")
                continue

            price_new = _beer_price(
                card.select_one("span.price-products-catalog-content__new").get_text()
            ) if card.select_one("span.price-products-catalog-content__new") else None
            price_old = _beer_price(
                card.select_one("span.price-products-catalog-content__old").get_text()
            ) if card.select_one("span.price-products-catalog-content__old") else None

            if price_new is None:
                logger.debug(f"Beer skip (no promo price): {name!r}")
                continue

            disc_el = card.select_one("div.price-products-catalog-content__discount")
            discount = 0.0
            if disc_el:
                dm = _re.search(r'(\d+)', disc_el.get_text())
                if dm:
                    discount = float(dm.group(1))
            elif price_old and price_old > price_new:
                discount = round((1 - price_new / price_old) * 100, 1)

            if discount <= 0:
                logger.debug(f"Beer skip (no discount): {name!r}")
                continue

            products.append({
                "name":      name,
                "url":       url,
                "volume_ml": vol,
                "price_new": price_new,
                "price_old": price_old or round(price_new / (1 - discount / 100), 2),
                "discount":  discount,
            })
        except Exception as e:
            logger.debug(f"Beer card parse error: {e}")
    logger.info(f"Linella beer page: {len(cards)} cards → {len(products)} kept")
    return products, len(cards)


async def _scrape_linella_beer(session: aiohttp.ClientSession) -> list[dict]:
    # Prime request to establish ci_session cookie
    try:
        async with session.get(
            "https://linella.md/en/catalog/beer",
            headers=_BEER_HEADERS,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            logger.info(f"Linella beer prime: HTTP {resp.status}")
    except Exception as e:
        logger.warning(f"Linella beer prime failed: {e}")

    all_products: list[dict] = []
    for page in range(1, 20):
        url = _LINELLA_BEER_PROMO if page == 1 else f"{_LINELLA_BEER_PROMO}&page={page}"
        try:
            async with session.get(
                url, headers=_BEER_HEADERS,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Linella beer page {page}: HTTP {resp.status}")
                    break
                html = await resp.text()
        except Exception as e:
            logger.warning(f"Linella beer page {page} error: {e}")
            break

        page_products, card_count = _parse_beer_page(html)
        if card_count == 0:
            # No product cards at all — truly the last page
            break
        all_products.extend(page_products)

    return all_products


async def beer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    show_all = bool(context.args and context.args[0].lower() == "all")
    status_msg = await update.message.reply_text("🍺 Ищу скидки на пиво в Linella...")
    try:
        async with aiohttp.ClientSession() as session:
            products = await _scrape_linella_beer(session)

        if not products:
            await status_msg.edit_text(
                "😔 Не удалось найти пиво со скидкой.\n\n"
                f'🔗 Открой каталог вручную: <a href="{_LINELLA_BEER_PROMO}">Linella — акции на пиво</a>',
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return

        products.sort(key=lambda p: p["price_new"])
        display = products if show_all else products[:10]

        from zoneinfo import ZoneInfo
        updated = datetime.now(ZoneInfo("Europe/Chisinau")).strftime("%d.%m.%Y %H:%M")

        title = (
            f"🍺 <b>Все акции на пиво (≤700ml) — {len(display)} шт.</b>"
            if show_all else
            "🍺 <b>Топ-10 пива со скидкой (≤700ml)</b>"
        )
        header = f"{title}\n<i>Linella · {updated} · {len(products)} акций найдено</i>\n"

        medals = ["🥇", "🥈", "🥉"] + ["🍺"] * max(0, len(display) - 3)
        footer = "<i>Сортировка: от дешёвого · Цены актуальны на момент запроса</i>"

        # Build individual entry lines
        entry_lines = []
        for i, p in enumerate(display):
            vol = p["volume_ml"]
            vol_str = f"{int(vol)}ml" if vol < 1000 else f"{vol / 1000:.2g}L"
            name_link = f'<a href="{p["url"]}">{p["name"]}</a>'
            entry_lines.append(
                f"{medals[i]} {name_link} · {vol_str} · "
                f"<b>{p['price_new']:.2f}</b> MDL "
                f"(<s>{p['price_old']:.2f}</s>) "
                f"🔥 -{p['discount']:.0f}%"
            )

        # Split into messages respecting Telegram's 4096-char limit
        LIMIT = 4000
        messages = []
        current = header
        for line in entry_lines:
            candidate = current + "\n" + line
            if len(candidate) > LIMIT:
                messages.append(current)
                current = line
            else:
                current = candidate
        messages.append(current + "\n\n" + footer)

        await status_msg.edit_text(
            messages[0], parse_mode="HTML", disable_web_page_preview=True
        )
        for msg_text in messages[1:]:
            await update.message.reply_html(msg_text, disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Beer command error: {type(e).__name__}: {e}")
        await status_msg.edit_text("⚠️ Ошибка при загрузке данных. Попробуй позже!")


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


# ─── /artemis ────────────────────────────────────────────────────────────────

async def artemis(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    loading = await update.message.reply_text("🌙 Загружаю данные миссии Артемис...")
    try:
        data = await get_artemis_data()
        text = get_artemis_text(data)
        await loading.edit_text(text, parse_mode="HTML", disable_web_page_preview=True)

        buf = generate_position_map(data)
        await update.message.reply_photo(
            photo=buf,
            caption="🗺 Позиция корабля Orion | Artemis II",
        )
    except Exception as e:
        logger.warning(f"Artemis error: {e}")
        await loading.edit_text(
            "🌙 <b>Артемис</b>\n\nНе удалось загрузить данные миссии. "
            "Попробуйте позже.\n\n🔗 nasa.gov/artemis",
            parse_mode="HTML",
        )


# ─── Утренний дайджест ────────────────────────────────────────────────────────

_DAY_NAMES_RU   = ["Понедельник","Вторник","Среда","Четверг","Пятница","Суббота","Воскресенье"]
_MONTH_NAMES_RU = ["января","февраля","марта","апреля","мая","июня",
                   "июля","августа","сентября","октября","ноября","декабря"]


async def _digest_weather(city: str) -> str:
    """Compact weather block (current + tomorrow) for the digest."""
    try:
        async with aiohttp.ClientSession() as session:
            lat, lon, city_name = await _geocode(session, city)
            params = {
                "latitude": lat, "longitude": lon,
                "current": ("temperature_2m,apparent_temperature,relative_humidity_2m,"
                            "wind_speed_10m,wind_direction_10m,weather_code,uv_index"),
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "auto", "forecast_days": 2, "wind_speed_unit": "kmh",
            }
            async with session.get(
                "https://api.open-meteo.com/v1/forecast",
                params=params, timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                om = await resp.json()

        cur   = om["current"]
        daily = om["daily"]
        temp  = cur["temperature_2m"]
        feels = cur["apparent_temperature"]
        hum   = cur["relative_humidity_2m"]
        wspd  = cur["wind_speed_10m"]
        wdeg  = cur["wind_direction_10m"]
        wcode = cur["weather_code"]
        uv    = cur.get("uv_index") or 0

        today_max  = daily["temperature_2m_max"][0]
        today_min  = daily["temperature_2m_min"][0]
        t_code = daily["weather_code"][1]
        t_max  = daily["temperature_2m_max"][1]
        t_min  = daily["temperature_2m_min"][1]
        t_prec = ((daily.get("precipitation_sum") or [0, 0])[1]) or 0

        line1 = (f"📍 <b>{city_name}</b>: {_wmo_icon(wcode)} {temp:.0f}°C (ощ. {feels:.0f}°C) · "
                 f"📊 {today_min:.0f}…{today_max:.0f}°C · "
                 f"💨 {wspd/3.6:.0f} м/с {_wind_dir(wdeg)} · 💧 {hum}% · UV {uv:.0f}")
        line2 = (f"   ➡️ Завтра: {_wmo_icon(t_code)} {t_min:.0f}…{t_max:.0f}°C"
                 + (f" · 🌂 {t_prec:.1f} мм" if t_prec > 0.1 else ""))
        return f"{line1}\n{line2}"
    except Exception as e:
        logger.debug(f"Digest weather error ({city}): {e}")
        return f"📍 <b>{city}</b>: ⚠️ нет данных"


async def _digest_fuel() -> str:
    """Compact best-prices block for the digest."""
    TARGET = {"ROMPETROL", "VENTO", "PETROM", "LUKOIL", "NOW OIL", "BEMOL", "AVANTE"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.ecarburanti.anre.md/public",
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"User-Agent": "MoldovaBot/1.0"},
            ) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                raw = await resp.json(content_type=None)

        best: dict[str, tuple[str, float]] = {}
        for rec in raw:
            name = (rec.get("station_name") or "").strip().upper()
            matched = next((t for t in TARGET if t in name), None)
            if not matched:
                continue
            for fuel in ("gasoline", "diesel", "gpl"):
                try:
                    p = float(rec.get(fuel) or 0)
                    if p > 0 and (fuel not in best or p < best[fuel][1]):
                        best[fuel] = (matched, p)
                except (TypeError, ValueError):
                    pass

        spec = [
            ("gasoline", "🚗", "Бензин-95"),
            ("diesel",   "🚛", "Дизель"),
            ("gpl",      "🚕", "Газ"),
        ]
        lines = [
            f"{em} {name}: {best[f][0]} — {best[f][1]:.2f} MDL"
            for f, em, name in spec if f in best
        ]
        return "\n".join(lines) if lines else "⚠️ нет данных"
    except Exception as e:
        logger.debug(f"Digest fuel error: {e}")
        return "⚠️ нет данных"


async def _digest_rates() -> str:
    """Returns the currency block for the digest, sourced from BNM (plain text, / separators)."""
    try:
        rates, date_str = await _fetch_bnm_rates()

        usd  = rates.get("USD", 0)
        eur  = rates.get("EUR", 0)
        gbp  = rates.get("GBP", 0)
        chf  = rates.get("CHF", 0)
        ils  = rates.get("ILS", 0)
        ron  = rates.get("RON", 0)
        rub  = rates.get("RUB", 0)
        uah  = rates.get("UAH", 0)
        try_ = rates.get("TRY", 0)
        aed  = rates.get("AED") or (usd / 3.6725 if usd else 0)

        def _v(val: float, d: int = 2) -> str:
            return f"{val:.{d}f}" if val else "—"

        # Line 1: USD with cross-rates
        cross = []
        if aed:  cross.append(f"{usd/aed:.2f} AED")
        if rub:  cross.append(f"{round(usd/rub)} RUB")
        if uah:  cross.append(f"{round(usd/uah)} UAH")
        if try_: cross.append(f"{round(usd/try_)} TRY")
        usd_line = f"🇺🇸 1 USD = {_v(usd)} MDL" + (" / " + " / ".join(cross) if cross else "")

        # Line 2: EUR with AED cross
        eur_line = f"🇪🇺 1 EUR = {_v(eur)} MDL" + (f" / {eur/aed:.2f} AED" if aed and eur else "")

        # Line 3: GBP + CHF
        gbp_chf = "  ·  ".join(filter(None, [
            f"🇬🇧 1 GBP = {_v(gbp)} MDL" if gbp else "",
            f"🇨🇭 1 CHF = {_v(chf)} MDL" if chf else "",
        ]))

        # Line 4: ILS + RON + AED
        misc = "  ·  ".join(filter(None, [
            f"🇮🇱 1 ILS = {_v(ils)} MDL" if ils else "",
            f"🇷🇴 1 RON = {_v(ron)} MDL" if ron else "",
            f"🇦🇪 1 AED = {_v(aed)} MDL" if aed else "",
        ]))

        source = f"<i>Источник: bnm.md · {date_str}</i>"
        return "\n".join(filter(None, [usd_line, eur_line, gbp_chf, misc, source]))
    except Exception as e:
        logger.debug(f"Digest rates error: {e}")
        return "⚠️ нет данных"


async def _digest_crypto() -> str:
    """BTC + ETH prices from CoinGecko for the digest."""
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        "?vs_currency=usd&ids=bitcoin,ethereum&order=market_cap_desc"
        "&sparkline=false&price_change_percentage=24h"
    )
    try:
        async with aiohttp.ClientSession(headers={"User-Agent": "MoldovaBot/1.0"}) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                coins = await resp.json()

        syms = {"bitcoin": "₿ BTC", "ethereum": "Ξ ETH"}
        parts = []
        for c in coins:
            sym  = syms.get(c["id"], c["symbol"].upper())
            price = c.get("current_price") or 0
            chg   = c.get("price_change_percentage_24h") or 0
            arrow = f"📈 +{chg:.1f}%" if chg >= 0 else f"📉 {chg:.1f}%"
            parts.append(f"{sym} {_fmt_price(price)} {arrow}")
        return "  ·  ".join(parts) if parts else "⚠️ нет данных"
    except Exception as e:
        logger.debug(f"Digest crypto error: {e}")
        return "⚠️ нет данных"


async def _digest_altseason() -> str:
    """Compact altseason index line. Returns '' if no CMC key."""
    if not CMC_API_KEY:
        return ""
    STABLES = {
        "USDT","USDC","BUSD","DAI","TUSD","USDP","USDD",
        "FRAX","LUSD","GUSD","FDUSD","PYUSD","USDE",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest",
                headers={"X-CMC_PRO_API_KEY": CMC_API_KEY},
                params={"limit": 108, "convert": "USD", "sort": "market_cap"},
                timeout=aiohttp.ClientTimeout(total=12),
            ) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                data = await resp.json()

        listings = data.get("data", [])
        btc = next((c for c in listings if c["symbol"] == "BTC"), None)
        if not btc:
            raise ValueError("BTC not found")
        btc_90d = btc.get("quote", {}).get("USD", {}).get("percent_change_90d") or 0.0
        alts = [
            c for c in listings
            if c["symbol"] not in STABLES | {"BTC"}
            and c.get("quote", {}).get("USD", {}).get("percent_change_90d") is not None
        ]
        if not alts:
            raise ValueError("no alts")
        idx = round(sum(1 for c in alts if c["quote"]["USD"]["percent_change_90d"] > btc_90d)
                    / len(alts) * 100)
        if   idx >= 75: label = "🚀 Альтсезон!"
        elif idx >= 55: label = "⚡ Начало альтсезона"
        elif idx >= 40: label = "😐 Нейтральный рынок"
        elif idx >= 25: label = "🟡 Сезон Bitcoin"
        else:           label = "🟠 Доминация BTC"
        return f"🌡 Альтсезон: {idx}/100 · {label}"
    except Exception as e:
        logger.debug(f"Digest altseason error: {e}")
        return ""


async def _digest_news(sources: list[tuple[str, str]], limit: int = 3) -> list[dict]:
    """Fetches from sources list until one works. Returns items list."""
    async with aiohttp.ClientSession() as session:
        for _, url in sources:
            items = await _fetch_rss(session, url, limit=limit)
            if items:
                return items
    return []


def _fmt_news_block(items: list[dict]) -> str:
    if not items:
        return "⚠️ нет данных"
    lines = []
    for i, art in enumerate(items, 1):
        title = art["title"][:80] + "…" if len(art["title"]) > 80 else art["title"]
        lines.append(f'{i}. <a href="{art["link"]}">{title}</a>')
    return "\n".join(lines)


async def _digest_meme() -> tuple[str, str]:
    """
    Returns (image_url, title) of a recent Iran/Trump political meme from Reddit.
    Searches r/PoliticalHumor and r/dankmemes for relevant top posts of the week.
    Falls back to random political meme if no match found.
    """
    HEADERS = {"User-Agent": "MoldovaBot/1.0 telegram-bot (github.com/moldovabot)"}
    QUERIES = ["iran trump", "trump iran war", "iran war", "trump", "hormuz"]
    SUBS    = ["PoliticalHumor", "dankmemes", "worldpolitics"]
    IMG_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp")

    async with aiohttp.ClientSession() as session:
        for query in QUERIES:
            for sub in SUBS:
                try:
                    params = {
                        "q": query, "sort": "top", "t": "week",
                        "limit": 15, "restrict_sr": "1",
                    }
                    async with session.get(
                        f"https://www.reddit.com/r/{sub}/search.json",
                        headers=HEADERS, params=params,
                        timeout=aiohttp.ClientTimeout(total=8),
                    ) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()

                    for post in data.get("data", {}).get("children", []):
                        p = post.get("data", {})
                        if p.get("is_video") or p.get("over_18") or p.get("spoiler"):
                            continue
                        img = p.get("url", "")
                        if img.lower().endswith(IMG_EXT):
                            return img, p.get("title", "Мем дня")[:80]
                except Exception:
                    continue

        # Fallback: top post from r/PoliticalHumor (no query filter)
        try:
            async with session.get(
                "https://www.reddit.com/r/PoliticalHumor/top.json?limit=10&t=day",
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for post in data.get("data", {}).get("children", []):
                        p = post.get("data", {})
                        if p.get("is_video") or p.get("over_18"):
                            continue
                        img = p.get("url", "")
                        if img.lower().endswith(IMG_EXT):
                            return img, p.get("title", "Мем дня")[:80]
        except Exception:
            pass

    logger.debug("Digest meme: no suitable image found")
    return "", ""


async def _digest_world_news() -> str:
    """Top-5 world news headlines from Russian-language RSS for the digest."""
    items = await _digest_news([
        ("BBC Русский",  "https://feeds.bbci.co.uk/russian/rss.xml"),
        ("РИА Новости",  "https://rsshub.app/ria/news"),
        ("Reuters RU",   "https://feeds.reuters.com/reuters/topNews"),
    ], limit=5)
    return _fmt_news_block(items)


async def morning_digest(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled morning digest — sends to MORNING_CHAT_ID (or job.chat_id)."""
    from zoneinfo import ZoneInfo
    now      = datetime.now(ZoneInfo("Europe/Chisinau"))
    day_name = _DAY_NAMES_RU[now.weekday()]
    date_str = f"{now.day} {_MONTH_NAMES_RU[now.month - 1]} {now.year}"

    # ── Запрашиваем всё параллельно ─────────────────────────────────────────
    results = await asyncio.gather(
        _digest_weather("Кишинёв"),
        _digest_weather("Abu Dhabi"),
        _digest_fuel(),
        _digest_rates(),
        _digest_crypto(),
        _digest_altseason(),
        _digest_world_news(),
        _digest_meme(),
        return_exceptions=True,
    )

    def _safe(val, fallback):
        return val if not isinstance(val, Exception) else fallback

    weather_kiv  = _safe(results[0], "📍 Кишинёв: ⚠️ нет данных")
    weather_auh  = _safe(results[1], "📍 Абу-Даби: ⚠️ нет данных")
    fuel_str     = _safe(results[2], "⚠️ нет данных")
    rates_str    = _safe(results[3], "⚠️ нет данных")
    crypto_str   = _safe(results[4], "⚠️ нет данных")
    alt_str      = _safe(results[5], "")
    world_news   = _safe(results[6], "⚠️ нет данных")
    meme_result  = _safe(results[7], ("", ""))
    meme_url, meme_title = meme_result if isinstance(meme_result, tuple) else ("", "")

    # ── Сборка сообщения ─────────────────────────────────────────────────────
    crypto_block = crypto_str + (f"\n{alt_str}" if alt_str else "")

    msg = "\n\n".join([
        f"🌅 <b>Доброе утро!</b>\n{day_name}, {date_str}",
        f"🌤 <b>ПОГОДА</b>\n{weather_kiv}\n{weather_auh}",
        f"⛽️ <b>ТОПЛИВО</b> (лучшие цены)\n{fuel_str}",
        f"💵 <b>КУРС ВАЛЮТ</b>\n{rates_str}",
        f"💎 <b>КРИПТО</b>\n{crypto_block}",
        f"📰 <b>НОВОСТИ</b>\n{world_news}",
        "🤖 <i>МолдоваБот · /help</i>",
    ])

    chat_id = context.job.chat_id if context.job else MORNING_CHAT_ID
    await context.bot.send_message(
        chat_id=chat_id,
        text=msg,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

    # ── Мем дня — отдельным медиа ───────────────────────────────────────────
    if meme_url:
        caption = f"😂 <b>Мем дня:</b> {meme_title}"
        try:
            if meme_url.lower().endswith(".gif"):
                await context.bot.send_animation(
                    chat_id=chat_id, animation=meme_url,
                    caption=caption, parse_mode="HTML",
                )
            else:
                await context.bot.send_photo(
                    chat_id=chat_id, photo=meme_url,
                    caption=caption, parse_mode="HTML",
                )
        except Exception as e:
            logger.debug(f"Meme send failed: {e}")

    logger.info(f"📬 Morning digest sent to chat {chat_id}")


async def digest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/digest — ручной запуск утреннего дайджеста в текущем чате."""
    loading = await update.message.reply_text("⏳ Собираю дайджест, подождите...")

    class _MockJob:
        chat_id = update.effective_chat.id

    class _MockCtx:
        bot = context.bot
        job = _MockJob()

    try:
        await morning_digest(_MockCtx())
        await loading.delete()
    except Exception as e:
        logger.warning(f"Digest cmd error: {e}")
        await loading.edit_text(f"⚠️ Не удалось собрать дайджест: {e}")


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
    app.add_handler(CommandHandler("beer",      beer))
    app.add_handler(CommandHandler("flights",   flights))
    app.add_handler(CommandHandler("kiv",       kiv))
    app.add_handler(CommandHandler("cinema",    cinema))
    app.add_handler(CallbackQueryHandler(cinema_callback, pattern=r"^cinema:"))
    app.add_handler(CommandHandler("artemis",   artemis))
    app.add_handler(CommandHandler("digest",    digest_cmd))

    # ── Утренний дайджест (ежедневно в 08:00 по Кишинёву) ────────────────────
    if MORNING_CHAT_ID:
        from zoneinfo import ZoneInfo
        chisinau_tz = ZoneInfo("Europe/Chisinau")
        app.job_queue.run_daily(
            morning_digest,
            time=dtime(8, 0, 0, tzinfo=chisinau_tz),
            chat_id=MORNING_CHAT_ID,
            name="morning_digest",
        )
        # ── Тестовый режим (раскомментировать одну строку для проверки) ──────
        # app.job_queue.run_repeating(morning_digest, interval=60,  first=5, chat_id=MORNING_CHAT_ID, name="morning_digest_test")  # каждую минуту
        # app.job_queue.run_repeating(morning_digest, interval=10,  first=5, chat_id=MORNING_CHAT_ID, name="morning_digest_test")  # каждые 10 сек
        logger.info(f"📬 Morning digest scheduled at 08:00 Chisinau → chat {MORNING_CHAT_ID}")
    else:
        logger.info("📬 Morning digest disabled (MORNING_CHAT_ID not set). Use /digest manually.")

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