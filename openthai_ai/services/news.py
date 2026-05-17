import html
import logging
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import quote


NEWS_LOGGER = logging.getLogger(__name__)
CACHE_TTL = 900  # 15 minutes
RSS_FETCH_ITEMS = 30
DEFAULT_NEWS_ITEMS = 5
THAI_RSS_HL = "th"
THAI_RSS_GL = "TH"
THAI_RSS_CEID = "TH:th"


@dataclass(frozen=True)
class NewsRequest:
    query: str
    label: str = ""


CATEGORIES: dict[str, dict] = {
    "hot": {
        "label": "ข่าวร้อน",
        "keywords": ["ข่าวร้อน", "ข่าวด่วน", "breaking", "breaking news", "เด่น", "highlight", "เด็ด"],
        "query": "ข่าวร้อน ข่าวด่วน",
    },
    "sports": {
        "label": "กีฬา",
        "keywords": [
            "กีฬา", "ฟุตบอล", "บาสเก็ตบอล", "บาส", "sport", "แข่งขัน",
            "นักกีฬา", "ทีม", "ลีก", "tennis", "เทนนิส", "มวย", "golf",
            "กอล์ฟ", "วอลเลย์บอล", "volleyball", "แบดมินตัน", "badminton",
        ],
        "query": "กีฬาไทย ฟุตบอลไทย",
    },
    "finance": {
        "label": "การเงิน",
        "keywords": [
            "หุ้น", "การเงิน", "เศรษฐกิจ", "ราคา", "ตลาดหุ้น", "ลงทุน",
            "finance", "stock", "crypto", "บิทคอยน์", "bitcoin", "fund",
            "กองทุน", "ธนาคาร", "เงินเฟ้อ", "ดอกเบี้ย", "อัตราแลกเปลี่ยน",
            "SET", "ตลาดหลักทรัพย์", "ราคาทอง", "ทองคำ", "ทองคํา", "gold", "forex",
        ],
        "query": "หุ้นไทย เศรษฐกิจไทย การเงิน ราคาทอง",
    },
    "tech": {
        "label": "เทคโนโลยี",
        "keywords": [
            "เทคโนโลยี", "เทโนโลยี", "tech", "technology", "ai", "เอไอ", "gadget", "software",
            "แอปพลิเคชัน", "app", "โทรศัพท์", "สมาร์ทโฟน", "คอมพิวเตอร์",
            "อินเทอร์เน็ต", "ซอฟต์แวร์", "hardware", "startup", "สตาร์ทอัพ",
            "robot", "หุ่นยนต์", "chatgpt", "openai", "claude",
            "ไอที", "ดิจิทัล", "ไอโอเอส", "แอนดรอยด์", "อัปเดต",
        ],
        "query": "เทคโนโลยี AI ดิจิทัล",
    },
    "politics": {
        "label": "การเมือง",
        "keywords": [
            "การเมือง", "รัฐบาล", "นายกรัฐมนตรี", "นายก", "election",
            "พรรค", "vote", "politics", "รัฐสภา", "สส", "ส.ส.", "ส.ว.",
            "กระทรวง", "cabinet", "เลือกตั้ง", "รัฐประหาร", "ยุบสภา",
        ],
        "query": "การเมืองไทย รัฐบาลไทย",
    },
}

NEWS_STOPWORDS = [
    "สรุปข่าว", "ค้นหาข่าว", "ค้นข่าว", "ข่าว", "ล่าสุด", "วันนี้", "ตอนนี้",
    "เมื่อวาน", "สัปดาห์นี้", "เกี่ยวกับ", "เรื่อง", "ภาษาไทย", "ประเทศไทย",
    "search news", "latest news", "news", "today", "now", "recent", "about",
    "please", "summary", "summarize", "find",
]

_cache: dict[str, tuple[float, list[dict]]] = {}


def _rss_search(query: str) -> str:
    return (
        f"https://news.google.com/rss/search?q={quote(query)}"
        f"&hl={THAI_RSS_HL}&gl={THAI_RSS_GL}&ceid={THAI_RSS_CEID}"
    )


def _rss_top_stories() -> str:
    return f"https://news.google.com/rss?hl={THAI_RSS_HL}&gl={THAI_RSS_GL}&ceid={THAI_RSS_CEID}"


def is_news_query(text: str) -> bool:
    low = text.lower()
    explicit = [
        "ข่าว", "news", "สรุปข่าว", "อัพเดท", "อัปเดต",
        "เกิดอะไรขึ้น", "มีอะไรใหม่", "ล่าสุด",
    ]
    if any(s in low for s in explicit):
        return True
    all_keywords = [kw for info in CATEGORIES.values() for kw in info["keywords"]]
    return any(kw.lower() in low for kw in all_keywords)


def detect_category(text: str) -> str:
    low = text.lower()
    scores: dict[str, int] = {cat: 0 for cat in CATEGORIES}
    for cat, info in CATEGORIES.items():
        for kw in info["keywords"]:
            if kw.lower() in low:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "hot"


def extract_news_request(text: str) -> NewsRequest:
    category = detect_category(text)
    query = normalize_news_keyword(_extract_keyword(text))
    if not query:
        query = CATEGORIES[category].get("query") or CATEGORIES[category]["label"]
    return NewsRequest(query=query, label=query)


def normalize_news_keyword(keyword: str) -> str:
    cleaned = " ".join((keyword or "").split())
    aliases = {
        "hot news": "ข่าวร้อน ข่าวด่วน",
        "breaking news": "ข่าวด่วน",
        "breaking": "ข่าวด่วน",
        "technology": "เทคโนโลยี",
        "tech": "เทคโนโลยี",
        "finance": "การเงิน เศรษฐกิจ",
        "stock": "หุ้น",
        "stocks": "หุ้น",
        "gold": "ราคาทอง",
        "crypto": "คริปโต",
        "bitcoin": "บิทคอยน์",
        "ai": "AI ปัญญาประดิษฐ์",
    }
    return aliases.get(cleaned.lower(), cleaned)


def _extract_keyword(text: str) -> str:
    cleaned = f" {text.strip()} "
    protected_phrases = {
        "__HOTQUERY__": "hot news",
        "__BREAKINGQUERY__": "breaking news",
        "__HOTTHAIQUERY__": "ข่าวร้อน",
        "__BREAKINGTHAIQUERY__": "ข่าวด่วน",
    }
    for placeholder, phrase in protected_phrases.items():
        cleaned = _replace_insensitive(cleaned, phrase, placeholder)
    for token in sorted(NEWS_STOPWORDS, key=len, reverse=True):
        cleaned = _replace_insensitive(cleaned, token, " ")
    for placeholder, phrase in protected_phrases.items():
        cleaned = cleaned.replace(placeholder, phrase)
    cleaned = " ".join(cleaned.replace("  ", " ").split())
    return cleaned.strip(" :：-–—,，.。?？!！")


def fetch_news_search(news_request: NewsRequest, max_items: int = DEFAULT_NEWS_ITEMS) -> list[dict]:
    cache_key = f"search-th:{news_request.query.lower()}:{max_items}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    url = _rss_top_stories() if _is_generic_news_query(news_request.query) else _rss_search(news_request.query)
    raw_articles = _fetch_rss_articles(url, RSS_FETCH_ITEMS)
    term_filtered = _filter_by_query_terms(raw_articles, news_request.query)
    candidates = term_filtered if len(term_filtered) >= max_items else raw_articles
    selected = _latest_articles(candidates, max_items)
    enriched = [_enrich_article(article) for article in selected]

    NEWS_LOGGER.debug(
        "news_search_th query=%r raw_articles=%s selected=%s article_read_success=%s rss_fallback=%s",
        news_request.query,
        len(raw_articles),
        len(enriched),
        sum(1 for item in enriched if item.get("content_source") == "article"),
        sum(1 for item in enriched if item.get("content_source") == "rss"),
    )
    _cache[cache_key] = (time.time(), enriched)
    return enriched


def _cache_get(key: str) -> list[dict] | None:
    now = time.time()
    if key in _cache:
        ts, articles = _cache[key]
        if now - ts < CACHE_TTL:
            return articles
    return None


def _fetch_rss_articles(url: str, max_items: int) -> list[dict]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; OpenThaiChatLab/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        xml_data = resp.read()

    root = ET.fromstring(xml_data)
    channel = root.find("channel")
    articles: list[dict] = []
    for item in (channel.findall("item") if channel else [])[:max_items]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        description = _html_to_text(item.findtext("description") or "")
        source_el = item.find("source")
        source = (source_el.text or "").strip() if source_el is not None else ""
        source_url = (source_el.attrib.get("url", "") if source_el is not None else "").strip()
        articles.append({
            "title": title,
            "link": link,
            "source_url": source_url,
            "pub_date": pub_date,
            "published_at": _parse_pub_date(pub_date),
            "description": description,
            "source": source,
        })
    return articles


def _latest_articles(articles: list[dict], max_items: int) -> list[dict]:
    return sorted(
        articles,
        key=lambda item: item.get("published_at") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )[:max_items]


def _parse_pub_date(pub_date: str) -> datetime | None:
    if not pub_date:
        return None
    try:
        parsed = parsedate_to_datetime(pub_date)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_generic_news_query(query: str) -> bool:
    compact = re.sub(r"\s+", " ", (query or "").strip().lower())
    return compact in {
        "ข่าว",
        "ข่าวร้อน",
        "ข่าวด่วน",
        "ข่าวร้อน ข่าวด่วน",
        "hot news",
        "breaking news",
    }


def _enrich_article(article: dict) -> dict:
    enriched = dict(article)
    content, final_url = _fetch_article_content(article.get("link", ""))
    if not content and article.get("source_url"):
        source_content, source_final_url = _fetch_article_content(article["source_url"])
        if _content_matches_title(source_content, article.get("title", "")):
            content, final_url = source_content, source_final_url
    if final_url:
        enriched["link"] = final_url
    if content:
        enriched["content"] = content
        enriched["content_source"] = "article"
    else:
        fallback = article.get("description") or article.get("title") or ""
        enriched["content"] = fallback
        enriched["content_source"] = "rss"
    return enriched


def _content_matches_title(content: str, title: str) -> bool:
    if not content or not title:
        return False
    terms = [
        term.lower()
        for term in re.split(r"\W+", title)
        if len(term) >= 4 and not term.isdigit()
    ]
    if not terms:
        return False
    low_content = content.lower()
    hits = sum(1 for term in terms[:10] if term in low_content)
    return hits >= min(2, len(terms))


def _fetch_article_content(url: str) -> tuple[str, str]:
    if not url:
        return "", ""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            final_url = resp.geturl()
            content_type = resp.headers.get("Content-Type", "")
            if "html" not in content_type.lower():
                return "", final_url
            raw = resp.read(350_000)
    except Exception as exc:
        NEWS_LOGGER.debug("article_read_failed url=%r error=%s", url, exc)
        return "", ""

    charset = "utf-8"
    match = re.search(r"charset=([\w-]+)", content_type, re.IGNORECASE)
    if match:
        charset = match.group(1)
    try:
        page = raw.decode(charset, errors="ignore")
    except LookupError:
        page = raw.decode("utf-8", errors="ignore")

    text = _extract_article_text(page)
    if len(text) < 220:
        return "", final_url
    return text[:5000], final_url


def _extract_article_text(page: str) -> str:
    page = re.sub(r"(?is)<(script|style|noscript|svg|iframe).*?>.*?</\1>", " ", page)
    article_match = re.search(r"(?is)<article\b[^>]*>(.*?)</article>", page)
    source = article_match.group(1) if article_match else page
    paragraphs = re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", source)
    if paragraphs:
        chunks = [_html_to_text(p) for p in paragraphs]
        text = " ".join(chunk for chunk in chunks if len(chunk) > 20)
    else:
        text = _html_to_text(source)
    return _clean_text(text)


def _html_to_text(value: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html.unescape(value or ""))
        parser.close()
    except Exception:
        return _clean_text(re.sub(r"<[^>]+>", " ", html.unescape(value or "")))
    return _clean_text(parser.text())


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def _filter_by_query_terms(articles: list[dict], query: str) -> list[dict]:
    terms = [term.lower() for term in query.split() if len(term) > 1]
    if not terms:
        return articles
    return [
        article for article in articles
        if any(term in f"{article.get('title', '')} {article.get('description', '')}".lower() for term in terms)
    ]


def _replace_insensitive(text: str, old: str, new: str) -> str:
    if _is_ascii_hint(old):
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(old)}(?![A-Za-z0-9])", re.IGNORECASE)
        return pattern.sub(new, text)
    return re.sub(re.escape(old), new, text, flags=re.IGNORECASE)


def _is_ascii_hint(token: str) -> bool:
    return token.isascii() and any(ch.isalpha() for ch in token)


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg", "iframe"}:
            self._skip_depth += 1
        if tag in {"p", "br", "div", "li", "h1", "h2", "h3"}:
            self._chunks.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg", "iframe"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "div", "li", "h1", "h2", "h3"}:
            self._chunks.append(" ")

    def handle_data(self, data):
        if not self._skip_depth and data:
            self._chunks.append(data)

    def text(self) -> str:
        return " ".join(self._chunks)


def format_news_search_context(news_request: NewsRequest, articles: list[dict]) -> str:
    lines = [
        (
            f"[ข่าวจาก Google News RSS ภาษาไทย: {news_request.label} (query={news_request.query})]\n"
            "คำสั่งสำหรับ AI: ใช้เฉพาะข่าวจาก Context นี้เท่านั้น ห้ามแต่งข่าวเอง "
            "สรุปข่าวล่าสุด 5 รายการตามลำดับที่ให้ไว้ใน Context ให้ครบทุกข่าว ไม่ต้องคัดออกเองว่าไม่เกี่ยว "
            "สรุปเป็นภาษาไทย กระชับ อ่านง่าย และทุกข่าวต้องมี source/link ให้ผู้ใช้คลิกอ่านต้นฉบับได้ "
            "ถ้าเนื้อหาเป็น RSS fallback ให้บอกตามข้อมูลที่ RSS ให้มาเท่านั้น"
        )
    ]
    for i, article in enumerate(articles, 1):
        src = article.get("source") or "ไม่ระบุแหล่งข่าว"
        source_kind = "อ่านจากบทความจริง" if article.get("content_source") == "article" else "ข้อมูลจาก RSS"
        lines.extend([
            "",
            f"## ข่าว {i}",
            f"หัวข้อ: {article.get('title', '')}",
            f"แหล่งข่าว: {src}",
            f"วันที่ RSS: {article.get('pub_date', '') or 'ไม่ระบุ'}",
            f"ลิงก์ต้นฉบับ: {article.get('link', '')}",
            f"ประเภทข้อมูล: {source_kind}",
            f"เนื้อหา: {article.get('content') or article.get('description') or article.get('title') or ''}",
        ])
    return "\n".join(lines)
