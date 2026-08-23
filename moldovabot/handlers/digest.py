import asyncio
import logging

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

from ..config import CMC_API_KEY, MORNING_CHAT_ID
from .crypto import STABLECOINS, _fmt_price
from .currency import _fetch_bnm_rates
from .fuel import TARGET_STATIONS
from .news import _fetch_rss
from .weather import _geocode, _wind_dir, _wmo_icon
from ..timeutil import now_chisinau

logger = logging.getLogger(__name__)

_DAY_NAMES_RU   = ["Понедельник","Вторник","Среда","Четверг","Пятница","Суббота","Воскресенье"]
_MONTH_NAMES_RU = ["января","февраля","марта","апреля","мая","июня",
                   "июля","августа","сентября","октября","ноября","декабря"]


# Pre-known coordinates to avoid Nominatim rate-limit when both cities geocode in parallel
_DIGEST_CITY_COORDS: dict[str, tuple[float, float, str]] = {
    "Кишинёв":   (47.0105, 28.8638, "Кишинёв"),
    "Antalya":   (36.8969, 30.7133, "Анталия"),
    "Abu Dhabi": (24.4539, 54.3773, "Abu Dhabi"),
}


async def _digest_weather(city: str) -> str:
    """Compact weather block (current + tomorrow) for the digest."""
    known = _DIGEST_CITY_COORDS.get(city)
    if known:
        lat, lon, city_name = known
    else:
        async with aiohttp.ClientSession() as _s:
            lat, lon, city_name = await _geocode(_s, city)

    params = {
        "latitude": lat, "longitude": lon,
        "current": ("temperature_2m,apparent_temperature,relative_humidity_2m,"
                    "wind_speed_10m,wind_direction_10m,weather_code,uv_index"),
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto", "forecast_days": 2, "wind_speed_unit": "kmh",
    }

    last_exc: Exception = RuntimeError("no attempts made")
    for attempt in range(3):
        if attempt:
            await asyncio.sleep(5 * attempt)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params=params, timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    if resp.status != 200:
                        raise ValueError(f"HTTP {resp.status}: {await resp.text()}")
                    om = await resp.json()
            if om.get("error"):
                raise ValueError(f"Open-Meteo error: {om.get('reason')}")

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
            last_exc = e
            logger.warning(f"Digest weather attempt {attempt+1}/3 ({city}): {type(e).__name__}: {e}")

    return f"📍 <b>{city}</b>: ⚠️ нет данных"


async def _digest_fuel() -> str:
    """Compact best-prices block for the digest."""
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
            matched = next((t for t in TARGET_STATIONS if t in name), None)
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
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true"
    )
    try:
        async with aiohttp.ClientSession(headers={"User-Agent": "MoldovaBot/1.0"}) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                if resp.status == 429:
                    raise ValueError("CoinGecko rate limit")
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                data = await resp.json()

        LABELS = {"bitcoin": "₿ BTC", "ethereum": "Ξ ETH"}
        parts = []
        for coin_id, label in LABELS.items():
            info  = data.get(coin_id, {})
            price = info.get("usd") or 0
            chg   = info.get("usd_24h_change") or 0
            if not price:
                continue
            arrow = f"📈 +{chg:.1f}%" if chg >= 0 else f"📉 {chg:.1f}%"
            parts.append(f"{label} {_fmt_price(price)} {arrow}")
        return "  ·  ".join(parts) if parts else "⚠️ нет данных"
    except Exception as e:
        logger.warning(f"Digest crypto error: {e}")
        return "⚠️ нет данных"


async def _digest_altseason() -> str:
    """Compact altseason index line. Returns '' if no CMC key."""
    if not CMC_API_KEY:
        return ""
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
            if c["symbol"] not in STABLECOINS | {"BTC"}
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
    now      = now_chisinau()
    day_name = _DAY_NAMES_RU[now.weekday()]
    date_str = f"{now.day} {_MONTH_NAMES_RU[now.month - 1]} {now.year}"

    # ── Запрашиваем всё параллельно ─────────────────────────────────────────
    results = await asyncio.gather(
        _digest_weather("Кишинёв"),
        _digest_weather("Antalya"),
        _digest_weather("Abu Dhabi"),
        _digest_fuel(),
        _digest_rates(),
        _digest_crypto(),
        _digest_altseason(),
        _digest_world_news(),
        return_exceptions=True,
    )

    def _safe(val, fallback):
        return val if not isinstance(val, Exception) else fallback

    weather_kiv  = _safe(results[0], "📍 Кишинёв: ⚠️ нет данных")
    weather_ant  = _safe(results[1], "📍 Анталия: ⚠️ нет данных")
    weather_auh  = _safe(results[2], "📍 Абу-Даби: ⚠️ нет данных")
    fuel_str     = _safe(results[3], "⚠️ нет данных")
    rates_str    = _safe(results[4], "⚠️ нет данных")
    crypto_str   = _safe(results[5], "⚠️ нет данных")
    alt_str      = _safe(results[6], "")
    world_news   = _safe(results[7], "⚠️ нет данных")

    # ── Сборка сообщения ─────────────────────────────────────────────────────
    crypto_block = crypto_str + (f"\n{alt_str}" if alt_str else "")

    msg = "\n\n".join([
        f"🌅 <b>Доброе утро!</b>\n{day_name}, {date_str}",
        f"🌤 <b>ПОГОДА</b>\n{weather_kiv}\n{weather_ant}\n{weather_auh}",
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
