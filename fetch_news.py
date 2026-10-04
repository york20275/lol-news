#!/usr/bin/env python3
"""抓取 LoL / T1 / Faker / LPL / BLG 近 7 天新聞，輸出 news.json（含圖片網址）。"""
import json, re, html, os
import datetime as dt
from calendar import timegm
from urllib.parse import quote

import feedparser
import requests

DAYS = 7              # 只保留幾天內的文章
MAX_ITEMS = 150       # news.json 最多幾篇
IMG_FETCH_LIMIT = 60  # 每次最多去文章頁面找幾張圖（避免跑太久）
OUT = "news.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; LoLNewsBot/1.0)"}

# ---- 1. 搜尋關鍵字（Google News RSS，中英文各抓一次）----
QUERIES = [
    "T1 Faker",
    "T1 英雄聯盟",
    "LPL 英雄聯盟",
    "BLG Bilibili Gaming",
    "LoL Worlds 2026",
    "英雄聯盟 世界賽",
]

def gnews(q, lang):
    q = quote(f"{q} when:{DAYS}d")
    if lang == "zh":
        return f"https://news.google.com/rss/search?q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"

FEEDS = [gnews(q, "zh") for q in QUERIES] + [gnews(q, "en") for q in QUERIES]

# ---- 2. 額外的電競媒體 RSS（自行增減；請先用瀏覽器確認網址可開）----
EXTRA_FEEDS = [
    "https://dotesports.com/feed",
]

# ---- 3. 標籤規則：標題或摘要含關鍵字就加上該標籤 ----
TAGS = {
    "T1": ["t1", "skt"],
    "Faker": ["faker", "李相赫", "이상혁"],
    "LPL": ["lpl", "anyone's legend", "topesports", "top esports", "invictus", "jd gaming"],
    "BLG": ["blg", "bilibili", "哔哩哔哩", "嗶哩嗶哩"],
    "Worlds": ["worlds", "世界賽", "全球總決賽", "世界赛"],
}
# 抓回來的文章至少要符合下面其中一個才保留
MUST_MATCH = ["league of legends", "lol", "英雄聯盟", "英雄联盟", "lck", "lpl", "worlds", "faker", "t1"]


def strip_tags(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def image_from_entry(e):
    for k in ("media_thumbnail", "media_content"):
        v = e.get(k)
        if v and v[0].get("url"):
            return v[0]["url"]
    for l in e.get("links", []):
        if l.get("type", "").startswith("image"):
            return l.get("href")
    m = re.search(r'<img[^>]+src="([^"]+)"', e.get("summary", "") or "")
    return m.group(1) if m else None


def og_image(url):
    """到文章頁面找 og:image。Google News 的轉址連結常無法解析，抓不到就回傳 None。"""
    try:
        r = requests.get(url, headers=UA, timeout=6, allow_redirects=True)
        if "news.google.com" in r.url:
            return None
        head = r.text[:200000]
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]*content=["\']([^"\']+)', head, re.I) \
            or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*property=["\']og:image', head, re.I)
        return html.unescape(m.group(1)) if m else None
    except Exception:
        return None


def norm(title):
    return re.sub(r"[\W_]+", "", title.lower())


def main():
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=DAYS)

    # 舊資料的圖片當快取，避免每小時重抓
    cache = {}
    if os.path.exists(OUT):
        try:
            for a in json.load(open(OUT, encoding="utf-8")).get("articles", []):
                if a.get("image"):
                    cache[a["link"]] = a["image"]
        except Exception:
            pass

    seen, items = set(), []
    for url in FEEDS + EXTRA_FEEDS:
        try:
            feed = feedparser.parse(url, request_headers=UA)
        except Exception as ex:
            print("feed error", url, ex)
            continue
        for e in feed.entries:
            if not e.get("published_parsed"):
                continue
            pub = dt.datetime.fromtimestamp(timegm(e.published_parsed), dt.timezone.utc)
            if pub < cutoff or pub > now + dt.timedelta(hours=1):
                continue

            title = strip_tags(e.get("title", ""))
            source = (e.get("source") or {}).get("title", "")
            if not source and " - " in title:          # Google News 標題格式：標題 - 媒體
                title, source = title.rsplit(" - ", 1)
            elif source and title.endswith(" - " + source):
                title = title[: -len(source) - 3]
            if not source:
                source = feed.feed.get("title", "")

            key = norm(title)
            if not key or key in seen:
                continue

            summary = strip_tags(e.get("summary", ""))
            if norm(summary).startswith(key) or len(summary) < 20:
                summary = ""                            # Google News 摘要通常只是重複標題
            text = f"{title} {summary}".lower()
            if not any(k in text for k in MUST_MATCH):
                continue
            seen.add(key)

            link = e.get("link", "")
            items.append({
                "title": title,
                "source": source,
                "link": link,
                "published": pub.isoformat(),
                "summary": summary[:200],
                "image": image_from_entry(e) or cache.get(link),
                "tags": [t for t, ks in TAGS.items() if any(k in text for k in ks)] or ["LoL"],
            })

    items.sort(key=lambda a: a["published"], reverse=True)
    items = items[:MAX_ITEMS]

    fetched = 0
    for a in items:
        if not a["image"] and fetched < IMG_FETCH_LIMIT:
            a["image"] = og_image(a["link"])
            fetched += 1

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"updated": now.isoformat(), "articles": items}, f, ensure_ascii=False, indent=1)
    print(f"saved {len(items)} articles, {sum(1 for a in items if a['image'])} with images")


if __name__ == "__main__":
    main()
