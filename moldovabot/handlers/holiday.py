from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ContextTypes

from ..timeutil import now_chisinau


def _orthodox_easter(year: int) -> datetime:
    """Julian calendar Easter (Orthodox) → Gregorian date."""
    a = year % 4
    b = year % 7
    c = year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month = (d + e + 114) // 31
    day = ((d + e + 114) % 31) + 1
    return datetime(year, month, day) + timedelta(days=13)  # Julian → Gregorian


def _get_moldova_holidays(year: int) -> list[tuple[datetime, str, str]]:
    """Returns sorted list of (date, name_ru, emoji) for Moldova public holidays."""
    easter = _orthodox_easter(year)
    holidays = [
        (datetime(year, 1, 1),   "Новый год",                   "🎆"),
        (datetime(year, 1, 7),   "Рождество Христово",          "⛪"),
        (datetime(year, 1, 8),   "Рождество (2-й день)",        "⛪"),
        (datetime(year, 3, 8),   "Международный день женщин",   "💐"),
        (easter,                  "Пасха (Православная)",        "🐣"),
        (easter + timedelta(1),  "Пасха (2-й день)",            "🐣"),
        (datetime(year, 5, 1),   "День труда",                  "⚒️"),
        (datetime(year, 5, 9),   "День победы / День Европы",   "🕊️"),
        (datetime(year, 6, 1),   "День защиты детей",           "👶"),
        (datetime(year, 8, 27),  "День независимости",          "🇲🇩"),
        (datetime(year, 8, 31),  "Праздник языка",              "📚"),
        (datetime(year, 12, 25), "Рождество (новый стиль)",     "🎄"),
    ]
    return sorted(holidays, key=lambda h: h[0])


async def holiday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/holiday [all] — ближайшие или все праздники Молдовы."""
    today = now_chisinau().date()
    year = today.year
    show_all = bool(context.args and context.args[0].lower() in ("all", "все"))

    pool = _get_moldova_holidays(year) + _get_moldova_holidays(year + 1)

    if show_all:
        display = [h for h in pool if h[0].year == year]
        title = f"🇲🇩 <b>Праздники Молдовы {year}</b>"
    else:
        display = [h for h in pool if h[0].date() >= today][:5]
        title = "🇲🇩 <b>Ближайшие праздники Молдовы</b>"

    lines = []
    for d, name, emoji in display:
        date_str = d.strftime("%d.%m.%Y")
        days_left = (d.date() - today).days
        if days_left == 0:
            suffix = " — <b>сегодня! 🎉</b>"
        elif days_left == 1:
            suffix = " — <i>завтра</i>"
        elif 2 <= days_left <= 7:
            suffix = f" — <i>через {days_left} дн.</i>"
        else:
            suffix = ""
        lines.append(f"{emoji} {date_str} — {name}{suffix}")

    footer = "\n\n<i>Все праздники года: /holiday all</i>" if not show_all else ""
    await update.message.reply_html(title + "\n\n" + "\n".join(lines) + footer)
