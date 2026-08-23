import logging

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

from ..timeutil import now_chisinau

logger = logging.getLogger(__name__)

ANRE_URL = "https://api.ecarburanti.anre.md/public"

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


async def fuel_prices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Цены на топливо в реальном времени с ANRE API (api.ecarburanti.anre.md)."""
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

        fetched_at = now_chisinau().strftime("%d.%m.%Y %H:%M")

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
