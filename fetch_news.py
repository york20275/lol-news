#!/usr/bin/env python3
"""抓取 LoL / T1 / Faker / LPL / BLG 近 7 天的新聞、Reddit、X 貼文，輸出 news.json，並把圖片存到 images/。"""
import json, re, html, os, hashlib
import datetime as dt
from calendar import timegm
from urllib.parse import quote

import feedparser
import requests

DAYS = 7               # 只保留幾天內的內容
MAX_ITEMS = 200        # news.json 最多幾篇
IMG_FETCH_LIMIT = 60   # 每次最多去新聞頁面找幾張 og:image
LOCAL_IMG_LIMIT = 40   # 最新幾篇把圖片存進 images/（讓網頁能「複製圖片」）
OUT, IMG_DIR = "news.json", "images"
# Reddit 要求有辨識度的 User-Agent，建議把 yourname 換成你的 Reddit 帳號
UA = {"User-Agent": "script:lol-fan-news:1.0 (by /u/yourname)"}

# ---------- 1. 新聞：Google News RSS ----------
QUERIES = ["T1 Faker", "T1 英雄聯盟", "LPL 英雄聯盟", "BLG Bilibili Gaming", "LoL Worlds 2026", "英雄聯盟 世界賽"]

def gnews(q, lang):
    q = quote(f"{q} when:{DAYS}d")
    if lang == "zh":
        return f"https://news.google.com/rss/search?q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"

SOURCES = [{"url": gnews(q, l), "type": "news"} for l in ("zh", "en") for q in QUERIES]
SOURCES.append({"url": "https://dotesports.com/feed", "type": "news"})  # 額外媒體 RSS，可自行增減

# ---------- 2. Reddit：版面 RSS ----------
RQ = quote("T1 OR Faker OR BLG OR LPL OR Worlds")
SOURCES += [
    {"url": "https://www.reddit.com/r/T1/new/.rss", "type": "reddit", "tags": ["T1"], "filter": False},
    {"url": f"https://www.reddit.com/r/leagueoflegends/search.rss?q={RQ}&restrict_sr=1&sort=new&t=week", "type": "reddit"},
    {"url": f"https://www.reddit.com/r/LoLeSports/search.rss?q={RQ}&restrict_sr=1&sort=new&t=week", "type": "reddit"},
]

# ---------- 3. X（Twitter）：官方沒有免費讀取，需自備 RSS 橋接 ----------
# 在 GitHub repository 的 Settings → Secrets and variables → Actions → Variables 新增
# X_FEED_TEMPLATE，例如 https://你的橋接網址/{handle}/rss ；沒設定就自動略過 X。
X_ACCOUNTS = ["T1", "lolesports"]   # 要追蹤的 X 帳號（不含 @），請自行確認
X_TEMPLATE = os.environ.get("X_FEED_TEMPLATE", "").strip()
if X_TEMPLATE:
    SOURCES += [{"url": X_TEMPLATE.format(handle=h), "type": "x", "filter": False, "source": f"X @{h}"} for h in X_ACCOUNTS]

TAGS = {
    "T1": ["t1", "skt"],
    "Faker": ["faker", "李相赫", "이상혁"],
    "LPL": ["lpl", "anyone's legend", "top esports", "invictus", "jd gaming"],
    "BLG": ["blg", "bilibili", "哔哩哔哩", "嗶哩嗶哩"],
    "Worlds": ["worlds", "世界賽", "全球總決賽", "世界赛"],
}
MUST_MATCH = ["league of legends", "lol", "英雄聯盟", "英雄联盟", "lck", "lpl", "worlds", "faker", "t1"]


def strip_tags(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def norm(t):
    return re.sub(r"[\W_]+", "", t.lower())


def image_from_entry(e, raw):
    m = re.search(r'<img[^>]+src="([^"]+)"', raw or "")
    if m:
        return html.unescape(m.group(1))
    for k in ("media_thumbnail", "media_content"):
        v = e.get(k)
        if v and v[0].get("url"):
            return html.unescape(v[0]["url"])
    for l in e.get("links", []):
        if l.get("type", "").startswith("image"):
            return l.get("href")
    return None


def og_image(url):
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


def cache_image(url):
    """下載圖片到 images/，回傳相對路徑；失敗回傳 None。"""
    try:
        name = hashlib.sha1(url.encode()).hexdigest()[:16]
        for f in os.listdir(IMG_DIR):
            if f.startswith(name):
                return f"{IMG_DIR}/{f}"
        r = requests.get(url, headers=UA, timeout=10)
        ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(
            r.headers.get("content-type", "").split(";")[0])
        if r.status_code != 200 or not ext or len(r.content) > 2_500_000:
            return None
        path = f"{IMG_DIR}/{name}{ext}"
        with open(path, "wb") as f:
            f.write(r.content)
        return path
    except Exception:
        return None


def main():
    os.makedirs(IMG_DIR, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=DAYS)

    cache = {}
    if os.path.exists(OUT):
        try:
            for a in json.load(open(OUT, encoding="utf-8")).get("articles", []):
                if a.get("image"):
                    cache[a["link"]] = a["image"]
        except Exception:
            pass

    seen, items = set(), []
    for src in SOURCES:
        try:
            r = requests.get(src["url"], headers=UA, timeout=15)
        except Exception as ex:
            print("ERROR", src["type"], src["url"][:70], ex)
            continue
        if r.status_code != 200:
            print("HTTP", r.status_code, src["type"], src["url"][:70])
            continue
        feed = feedparser.parse(r.content)
        for e in feed.entries:
            t = e.get("published_parsed") or e.get("updated_parsed")
            if not t:
                continue
            pub = dt.datetime.fromtimestamp(timegm(t), dt.timezone.utc)
            if pub < cutoff or pub > now + dt.timedelta(hours=1):
                continue

            title = strip_tags(e.get("title", ""))
            source = src.get("source") or (e.get("source") or {}).get("title", "")
            if src["type"] == "reddit":
                tg = (e.get("tags") or [{}])[0]
                source = tg.get("label") or (f"r/{tg['term']}" if tg.get("term") else "Reddit")
                source = f"Reddit {source}"
            elif not source and " - " in title:
                title, source = title.rsplit(" - ", 1)
            elif source and title.endswith(" - " + source):
                title = title[: -len(source) - 3]
            source = source or strip_tags(feed.feed.get("title", ""))

            key = norm(title)
            if not key or key in seen:
                continue

            raw = (e.get("content") or [{}])[0].get("value", "") or e.get("summary", "")
            summary = strip_tags(raw)
            if src["type"] == "reddit":
                summary = re.split(r"submitted by", summary)[0].strip()
            if norm(summary).startswith(key) or len(summary) < 20:
                summary = ""
            text = f"{title} {summary}".lower()
            if src.get("filter", True) and not any(k in text for k in MUST_MATCH):
                continue
            seen.add(key)

            link = e.get("link", "")
            tags = {t_ for t_, ks in TAGS.items() if any(k in text for k in ks)} | set(src.get("tags", []))
            items.append({
                "type": src["type"],
                "title": title,
                "source": source,
                "link": link,
                "published": pub.isoformat(),
                "summary": summary[:220],
                "image": image_from_entry(e, raw) or cache.get(link),
                "local_image": None,
                "tags": [t_ for t_ in TAGS if t_ in tags] or ["LoL"],
            })

    items.sort(key=lambda a: a["published"], reverse=True)
    items = items[:MAX_ITEMS]

    fetched = 0
    for a in items:
        if not a["image"] and a["type"] == "news" and fetched < IMG_FETCH_LIMIT:
            a["image"] = og_image(a["link"])
            fetched += 1

    keep = set()
    for a in [x for x in items if x["image"]][:LOCAL_IMG_LIMIT]:
        a["local_image"] = cache_image(a["image"])
        if a["local_image"]:
            keep.add(os.path.basename(a["local_image"]))
    for f in os.listdir(IMG_DIR):          # 清掉不再使用的舊圖片
        if f not in keep and f != ".gitkeep":
            os.remove(os.path.join(IMG_DIR, f))

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"updated": now.isoformat(), "articles": items}, f, ensure_ascii=False, indent=1)
    by = {k: sum(1 for a in items if a["type"] == k) for k in ("news", "reddit", "x")}
    print(f"saved {len(items)} items {by}, {sum(1 for a in items if a['image'])} with images, {len(keep)} cached")


if __name__ == "__main__":
    main()
