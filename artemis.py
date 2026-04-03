import os
import time
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# ─── Hardcoded mission data ───────────────────────────────────────────────────

ARTEMIS_II_CREW = [
    {"name": "Reid Wiseman",    "role": "Командир",            "agency": "NASA", "flag": "🇺🇸"},
    {"name": "Victor Glover",   "role": "Пилот",               "agency": "NASA", "flag": "🇺🇸"},
    {"name": "Christina Koch",  "role": "Специалист миссии",   "agency": "NASA", "flag": "🇺🇸"},
    {"name": "Jeremy Hansen",   "role": "Специалист миссии",   "agency": "CSA",  "flag": "🇨🇦"},
]

ARTEMIS_MISSIONS = [
    {"name": "Artemis I",   "status": "✅", "desc": "Беспилотный облёт Луны",              "year": "2022"},
    {"name": "Artemis II",  "status": "🔄", "desc": "Первый пилотируемый облёт",           "year": "~2026"},
    {"name": "Artemis III", "status": "📅", "desc": "Первая посадка (женщина на Луне)",    "year": "~2027"},
    {"name": "Artemis IV",  "status": "📅", "desc": "Lunar Gateway — начало строительства","year": "~2028"},
]

EARTH_MOON_KM = 384_400

# ─── In-memory cache ──────────────────────────────────────────────────────────

_cache_data: dict | None = None
_cache_time: float = 0.0
CACHE_TTL = 30 * 60  # 30 minutes


# ─── Helpers ─────────────────────────────────────────────────────────────────

def progress_bar(percent: float, length: int = 16) -> str:
    filled = round(length * percent / 100)
    return "▓" * filled + "░" * (length - filled)


def _phase_from_elapsed(elapsed_hours: float) -> tuple[str, float, float, float, float]:
    """Return (phase_name, progress_pct, dist_from_earth_km, dist_to_moon_km, velocity_km_s)."""
    if elapsed_hours < 0:
        return "На стартовой площадке", 5.0, 0.0, EARTH_MOON_KM, 0.0
    elif elapsed_hours < 4:
        t = elapsed_hours / 4
        dist = t * 1_000
        vel = 7.8 + t * 2.2  # rough ascent → TLI
        return "Выход на траекторию к Луне", 50.0, dist, EARTH_MOON_KM - dist, vel
    elif elapsed_hours < 72:
        t = (elapsed_hours - 4) / 68
        dist = 1_000 + t * (320_000 - 1_000)
        vel = 10.0 - t * 8.9  # decelerating during coast
        return "Перелёт к Луне", 65.0, dist, EARTH_MOON_KM - dist, max(0.9, vel)
    elif elapsed_hours < 120:
        t = (elapsed_hours - 72) / 48
        dist_to_moon = 320_000 * (1 - t)
        dist = EARTH_MOON_KM - dist_to_moon
        return "Лунный облёт / окололунная орбита", 88.0, dist, dist_to_moon, 1.0
    elif elapsed_hours < 180:
        t = (elapsed_hours - 120) / 60
        dist = EARTH_MOON_KM - t * EARTH_MOON_KM
        vel = 0.9 + t * 10.0
        return "Возвращение на Землю", 93.0, dist, EARTH_MOON_KM - dist, vel
    else:
        return "Приводнение", 100.0, 0.0, EARTH_MOON_KM, 0.0


def _fmt_countdown(delta: timedelta) -> str:
    total_s = int(delta.total_seconds())
    if total_s <= 0:
        return "уже запущена"
    days = total_s // 86400
    hours = (total_s % 86400) // 3600
    mins = (total_s % 3600) // 60
    return f"{days}д {hours}ч {mins}м"


def _fmt_elapsed(delta: timedelta) -> str:
    total_s = int(delta.total_seconds())
    if total_s <= 0:
        return "0д 0ч 0м"
    days = total_s // 86400
    hours = (total_s % 86400) // 3600
    mins = (total_s % 3600) // 60
    return f"{days}д {hours}ч {mins}м"


# ─── Data sources ─────────────────────────────────────────────────────────────

async def _fetch_ll2(session: aiohttp.ClientSession) -> dict:
    """Launch Library 2 — upcoming + previous Artemis launches."""
    result = {"upcoming": [], "previous": []}
    headers = {"User-Agent": "МолдовБот/1.0 (Telegram bot)"}

    for endpoint, key in [
        ("upcoming/?search=artemis&limit=5&mode=detailed", "upcoming"),
        ("previous/?search=artemis&limit=3&mode=detailed", "previous"),
    ]:
        try:
            url = f"https://ll.thespacedevs.com/2.2.0/launch/{endpoint}"
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = await r.json()
                    result[key] = data.get("results", [])
        except Exception:
            pass

    return result


async def _fetch_jpl(session: aiohttp.ClientSession, now: datetime) -> dict | None:
    """JPL Horizons — live Orion trajectory (only works during active flight)."""
    try:
        start_str = now.strftime("%Y-%m-%d %H:%M")
        stop_dt = now + timedelta(hours=1)
        stop_str = stop_dt.strftime("%Y-%m-%d %H:%M")
        params = {
            "format": "json",
            "COMMAND": "'-5765'",
            "OBJ_DATA": "NO",
            "MAKE_EPHEM": "YES",
            "EPHEM_TYPE": "OBSERVER",
            "CENTER": "'500@399'",
            "START_TIME": f"'{start_str}'",
            "STOP_TIME": f"'{stop_str}'",
            "STEP_SIZE": "'1h'",
            "QUANTITIES": "'1,9,19,20'",
        }
        async with session.get(
            "https://ssd.jpl.nasa.gov/api/horizons.api",
            params=params,
            timeout=aiohttp.ClientTimeout(total=12),
        ) as r:
            if r.status != 200:
                return None
            data = await r.json()
            result_text = data.get("result", "")
            if not result_text or "$$SOE" not in result_text:
                return None

            # Parse range (delta) and range-rate (deldot) from table
            soe_idx = result_text.index("$$SOE")
            eoe_idx = result_text.index("$$EOE")
            table = result_text[soe_idx + 5:eoe_idx].strip()
            lines = [l.strip() for l in table.splitlines() if l.strip()]

            range_km = None
            range_rate = None
            for line in lines:
                parts = line.split()
                # Quantities 19,20 are delta (AU) and deldot (km/s)
                # Table columns vary; look for numeric tokens
                if len(parts) >= 5:
                    try:
                        range_km = float(parts[-2]) * 1.496e8  # AU → km
                        range_rate = float(parts[-1])
                        break
                    except ValueError:
                        pass

            if range_km is None:
                return None

            return {"range_km": range_km, "range_rate_km_s": range_rate}
    except Exception:
        return None


async def _fetch_nasa_snippet(session: aiohttp.ClientSession) -> str:
    """Scrape a short description snippet from NASA Artemis page."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; МолдовБот/1.0)"}
        async with session.get(
            "https://www.nasa.gov/humans-in-space/artemis/",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            if r.status != 200:
                return ""
            html = await r.text()
            soup = BeautifulSoup(html, "html.parser")
            for p in soup.find_all("p"):
                text = p.get_text(" ", strip=True)
                if len(text) > 80:
                    return text[:220].rstrip() + "…"
    except Exception:
        pass
    return ""


async def _fetch_apod(session: aiohttp.ClientSession) -> str:
    """NASA APOD — flavor text."""
    try:
        key = os.getenv("NASA_API_KEY", "DEMO_KEY")
        async with session.get(
            f"https://api.nasa.gov/planetary/apod?api_key={key}",
            timeout=aiohttp.ClientTimeout(total=8),
        ) as r:
            if r.status == 200:
                data = await r.json()
                title = data.get("title", "")
                expl = data.get("explanation", "")[:120]
                return f"{title}: {expl}…" if title else ""
    except Exception:
        pass
    return ""


# ─── Main data assembly ───────────────────────────────────────────────────────

async def get_artemis_data() -> dict:
    global _cache_data, _cache_time

    now = time.monotonic()
    if _cache_data is not None and (now - _cache_time) < CACHE_TTL:
        return _cache_data

    utcnow = datetime.now(timezone.utc)

    async with aiohttp.ClientSession() as session:
        ll2_task   = asyncio.create_task(_fetch_ll2(session))
        jpl_task   = asyncio.create_task(_fetch_jpl(session, utcnow))
        nasa_task  = asyncio.create_task(_fetch_nasa_snippet(session))
        apod_task  = asyncio.create_task(_fetch_apod(session))

        ll2_data, jpl_data, nasa_snippet, apod_text = await asyncio.gather(
            ll2_task, jpl_task, nasa_task, apod_task, return_exceptions=True
        )

    # Normalise gather results (may be exceptions)
    if isinstance(ll2_data, Exception):
        ll2_data = {"upcoming": [], "previous": []}
    if isinstance(jpl_data, Exception):
        jpl_data = None
    if isinstance(nasa_snippet, Exception):
        nasa_snippet = ""
    if isinstance(apod_text, Exception):
        apod_text = ""

    # Find next Artemis launch NET from LL2
    upcoming = ll2_data.get("upcoming", [])
    next_launch = upcoming[0] if upcoming else None
    next_net_dt: datetime | None = None
    if next_launch:
        try:
            net_str = next_launch.get("net", "")
            next_net_dt = datetime.fromisoformat(net_str.replace("Z", "+00:00"))
        except Exception:
            pass

    # Determine if mission is active (NET is in the past)
    is_active = False
    launch_dt: datetime | None = None
    elapsed: timedelta = timedelta(0)

    if next_net_dt and next_net_dt <= utcnow:
        is_active = True
        launch_dt = next_net_dt
        elapsed = utcnow - launch_dt
    else:
        # Check previous launches for an ongoing mission
        previous = ll2_data.get("previous", [])
        if previous:
            try:
                prev_net = previous[0].get("net", "")
                prev_dt = datetime.fromisoformat(prev_net.replace("Z", "+00:00"))
                elapsed = utcnow - prev_dt
                if elapsed.total_seconds() < 180 * 3600:  # within 180h mission window
                    is_active = True
                    launch_dt = prev_dt
            except Exception:
                pass

    elapsed_hours = elapsed.total_seconds() / 3600 if is_active else -1.0

    # Telemetry
    jpl_available = False
    if jpl_data and isinstance(jpl_data, dict) and is_active:
        dist_earth = jpl_data.get("range_km", 0.0)
        dist_moon  = max(0.0, EARTH_MOON_KM - dist_earth)
        velocity   = abs(jpl_data.get("range_rate_km_s", 0.0))
        jpl_available = True
        phase, progress_pct, _, _, _ = _phase_from_elapsed(elapsed_hours)
    else:
        phase, progress_pct, dist_earth, dist_moon, velocity = _phase_from_elapsed(elapsed_hours)

    # Mission name from LL2 or default
    mission_name = "Artemis II — Orion"
    if next_launch:
        mission_name = next_launch.get("name", mission_name)

    # Countdown (only if not active)
    countdown_str = ""
    if not is_active and next_net_dt:
        delta = next_net_dt - utcnow
        countdown_str = _fmt_countdown(delta)
        # Refine progress based on days-to-launch
        days_to = delta.total_seconds() / 86400
        if days_to > 30:
            progress_pct = 15.0
        elif days_to > 7:
            progress_pct = 25.0
        elif days_to > 1:
            progress_pct = 35.0
        else:
            progress_pct = 40.0

    elapsed_str = _fmt_elapsed(elapsed) if is_active else "0д 0ч 0м"

    # Launch date display string (localised month in Russian)
    MONTHS_RU = ["Января","Февраля","Марта","Апреля","Мая","Июня",
                 "Июля","Августа","Сентября","Октября","Ноября","Декабря"]
    launch_display = "~2026"
    if next_net_dt:
        launch_display = f"{next_net_dt.day} {MONTHS_RU[next_net_dt.month - 1]} {next_net_dt.year}"

    data = {
        "mission_name":     mission_name,
        "phase":            phase,
        "is_active":        is_active,
        "launch_display":   launch_display,
        "countdown_str":    countdown_str,
        "elapsed_str":      elapsed_str,
        "elapsed_hours":    elapsed_hours,
        "dist_earth_km":    dist_earth,
        "dist_moon_km":     dist_moon,
        "velocity_km_s":    velocity,
        "jpl_available":    jpl_available,
        "progress_pct":     progress_pct,
        "crew":             ARTEMIS_II_CREW,
        "missions":         ARTEMIS_MISSIONS,
        "nasa_snippet":     nasa_snippet,
        "apod_text":        apod_text,
        "next_net_dt":      next_net_dt,
    }

    _cache_data = data
    _cache_time = now
    return data


# ─── Text formatter ───────────────────────────────────────────────────────────

def get_artemis_text(data: dict) -> str:
    sep = "<code>━━━━━━━━━━━━━━━━━━━━━</code>"

    mission   = data["mission_name"]
    phase     = data["phase"]
    launch    = data["launch_display"]
    pct       = data["progress_pct"]
    bar       = progress_bar(pct)
    is_active = data["is_active"]

    lines = [
        f"🌙 <b>АРТЕМИС — Лунная программа NASA</b>",
        sep,
        f"🚀 <b>Миссия:</b> {mission}",
        f"📍 <b>Статус:</b> {phase}",
        f"📅 <b>Запуск:</b> {launch}",
        "",
    ]

    if not is_active and data["countdown_str"]:
        lines.append(f"⏳ <b>До старта:</b> {data['countdown_str']}")
        lines.append(f"[{bar}] {pct:.0f}%")
    elif is_active:
        lines.append(f"🕐 <b>Время в полёте:</b> {data['elapsed_str']}")
        lines.append(f"[{bar}] {pct:.0f}%")
    else:
        lines.append(f"[{bar}] {pct:.0f}%")

    de = data["dist_earth_km"]
    dm = data["dist_moon_km"]
    v  = data["velocity_km_s"]

    lines += [
        "",
        sep,
        "📡 <b>ТЕЛЕМЕТРИЯ</b>",
        "",
        f"🌍 Расстояние от Земли:  <code>{de:>10,.0f} км</code>",
        f"🌕 Расстояние до Луны:   <code>{dm:>10,.0f} км</code>",
        f"⚡ Скорость:             <code>{v:>10.1f} км/с</code>",
        f"🕐 Время в полёте:       <code>{data['elapsed_str']:>12}</code>",
        "",
    ]
    if data["jpl_available"]:
        lines.append("📡 <i>Источник: JPL Horizons (реальные данные)</i>")
    else:
        lines.append("📡 <i>Источник: расчёт по траектории миссии</i>")

    lines += [
        "",
        sep,
        "👨‍🚀 <b>ЭКИПАЖ ARTEMIS II</b>",
        "",
    ]
    for member in data["crew"]:
        lines.append(f"{member['flag']} <b>{member['name']}</b> — {member['role']}")

    lines += [
        "",
        sep,
        "📋 <b>ПРОГРАММА АРТЕМИС</b>",
        "",
    ]
    for m in data["missions"]:
        lines.append(f"{m['status']} {m['name']} — {m['desc']} ({m['year']})")

    lines += [
        "",
        sep,
        "🗺 <i>Карта позиции отправлена ниже</i>",
        "🔗 nasa.gov/artemis",
    ]

    return "\n".join(lines)
