import logging
import xml.etree.ElementTree as ET
from datetime import datetime

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


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
