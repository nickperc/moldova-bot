import logging
import re

import aiohttp
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ContextTypes

from ..timeutil import now_chisinau

logger = logging.getLogger(__name__)

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
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*ml\b', text)
    if m:
        return float(m.group(1).replace(",", "."))
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*l\b', text)
    if m:
        return float(m.group(1).replace(",", ".")) * 1000
    return None


def _beer_price(text: str) -> float | None:
    m = re.search(r'(\d+[.,]\d+)', text.replace(" ", ""))
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
                dm = re.search(r'(\d+)', disc_el.get_text())
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

        updated = now_chisinau().strftime("%d.%m.%Y %H:%M")

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
