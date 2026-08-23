import logging

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

from ..config import CMC_API_KEY

logger = logging.getLogger(__name__)

STABLECOINS = {
    "USDT", "USDC", "BUSD", "DAI", "TUSD", "USDP", "USDD",
    "FRAX", "LUSD", "GUSD", "FDUSD", "PYUSD", "USDE",
}


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
