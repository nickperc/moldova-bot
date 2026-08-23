import asyncio
import logging
from datetime import datetime, timedelta

import aiohttp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..timeutil import now_chisinau

logger = logging.getLogger(__name__)

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

_CINEPLEX_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
}


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
    today    = now_chisinau().strftime("%Y-%m-%d")
    tomorrow = (now_chisinau() + timedelta(days=1)).strftime("%Y-%m-%d")

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
        today = now_chisinau().strftime("%Y-%m-%d")
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
