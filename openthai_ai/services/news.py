import time
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import quote


def _rss_search(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(query)}&hl=th&gl=TH&ceid=TH:th"


CATEGORIES: dict[str, dict] = {
    "hot": {
        "label": "ข่าวร้อน",
        "url": "https://news.google.com/rss?hl=th&gl=TH&ceid=TH:th",
        "keywords": ["ข่าวร้อน", "breaking", "เด่น", "highlight", "เด็ด"],
    },
    "sports": {
        "label": "กีฬา",
        "url": _rss_search("กีฬา"),
        "keywords": [
            "กีฬา", "ฟุตบอล", "บาสเก็ตบอล", "บาส", "sport", "แข่งขัน",
            "นักกีฬา", "ทีม", "ลีก", "tennis", "เทนนิส", "มวย", "golf",
            "กอล์ฟ", "วอลเลย์บอล", "volleyball", "แบดมินตัน", "badminton",
        ],
    },
    "finance": {
        "label": "การเงิน",
        "url": _rss_search("หุ้น เศรษฐกิจ การเงิน"),
        "keywords": [
            "หุ้น", "การเงิน", "เศรษฐกิจ", "ราคา", "ตลาดหุ้น", "ลงทุน",
            "finance", "stock", "crypto", "บิทคอยน์", "bitcoin", "fund",
            "กองทุน", "ธนาคาร", "เงินเฟ้อ", "ดอกเบี้ย", "อัตราแลกเปลี่ยน",
            "SET", "ตลาดหลักทรัพย์", "ราคาทอง", "ทองคํา", "gold", "forex",
        ],
    },
    "tech": {
        "label": "เทคโนโลยี",
        "url": _rss_search("ไอที ดิจิทัล สมาร์ทโฟน แอปพลิเคชัน"),
        "keywords": [
            "เทคโนโลยี", "เทโนโลยี", "tech", "ai", "เอไอ", "gadget", "software",
            "แอปพลิเคชัน", "app", "โทรศัพท์", "สมาร์ทโฟน", "คอมพิวเตอร์",
            "อินเทอร์เน็ต", "ซอฟต์แวร์", "hardware", "startup", "สตาร์ทอัพ",
            "robot", "หุ่นยนต์", "chatgpt", "openai", "claude",
            "ไอที", "ดิจิทัล", "ไอโอเอส", "แอนดรอยด์", "อัปเดต",
        ],
    },
    "politics": {
        "label": "การเมือง",
        "url": _rss_search("การเมืองไทย"),
        "keywords": [
            "การเมือง", "รัฐบาล", "นายกรัฐมนตรี", "นายก", "election",
            "พรรค", "vote", "politics", "รัฐสภา", "สส", "ส.ส.", "ส.ว.",
            "กระทรวง", "cabinet", "เลือกตั้ง", "รัฐประหาร", "ยุบสภา",
        ],
    },
}

_cache: dict[str, tuple[float, list[dict]]] = {}
CACHE_TTL = 900  # 15 minutes


def is_news_query(text: str) -> bool:
    low = text.lower()
    explicit = [
        "ข่าว", "news", "สรุปข่าว", "อัพเดท", "อัปเดต",
        "เกิดอะไรขึ้น", "มีอะไรใหม่", "ล่าสุด", "สรุป",
    ]
    if any(s in low for s in explicit):
        return True
    # category keyword + time signal → news intent
    time_signals = [
        "วันนี้", "ตอนนี้", "เมื่อกี้", "เมื่อวาน", "สัปดาห์นี้",
        "today", "now", "latest", "recent", "week",
    ]
    all_keywords = [kw for info in CATEGORIES.values() for kw in info["keywords"]]
    return any(kw.lower() in low for kw in all_keywords) and any(t in low for t in time_signals)


def detect_category(text: str) -> str:
    low = text.lower()
    scores: dict[str, int] = {cat: 0 for cat in CATEGORIES}
    for cat, info in CATEGORIES.items():
        for kw in info["keywords"]:
            if kw.lower() in low:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "hot"


def fetch_news(category: str, max_items: int = 8) -> list[dict]:
    now = time.time()
    if category in _cache:
        ts, articles = _cache[category]
        if now - ts < CACHE_TTL:
            return articles

    url = CATEGORIES[category]["url"]
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; RSSReader/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        xml_data = resp.read()

    root = ET.fromstring(xml_data)
    channel = root.find("channel")
    fetch_count = max_items if category == "hot" else max_items * 3
    raw: list[dict] = []
    for item in (channel.findall("item") if channel else [])[:fetch_count]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        source_el = item.find("source")
        source = (source_el.text or "").strip() if source_el is not None else ""
        raw.append({"title": title, "link": link, "pub_date": pub_date, "source": source})

    if category != "hot":
        kws = [kw.lower() for kw in CATEGORIES[category]["keywords"]]
        filtered = [a for a in raw if any(kw in a["title"].lower() for kw in kws)]
        articles = (filtered if len(filtered) >= 3 else raw)[:max_items]
    else:
        articles = raw[:max_items]

    _cache[category] = (now, articles)
    return articles


def format_news_context(category: str, articles: list[dict]) -> str:
    label = CATEGORIES[category]["label"]
    lines = [f"[ข่าว{label}ล่าสุดจาก Google News]"]
    for i, a in enumerate(articles, 1):
        src = f" — {a['source']}" if a.get("source") else ""
        lines.append(f"{i}. {a['title']}{src}")
    return "\n".join(lines)
