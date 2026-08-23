import logging
from datetime import datetime

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

from ..config import AIRLABS_API_KEY
from ..timeutil import now_chisinau

logger = logging.getLogger(__name__)

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
        now_str = now_chisinau().strftime("%d.%m %H:%M")

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
