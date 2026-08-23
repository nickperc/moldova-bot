import logging
import xml.etree.ElementTree as ET

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

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

    lines = []
    for i, art in enumerate(articles, 1):
        title = art["title"]
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
