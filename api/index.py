"""Byelingua API: collect, translate and publish international music news."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import escape
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

import feedparser
import requests
from bs4 import BeautifulSoup
from openai import OpenAI


LANGUAGES = {
    "en": "English",
    "zh": "简体中文",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "it": "Italiano",
    "pt": "Português",
    "ja": "日本語",
}
COUNTRIES = {
    "de": "德国", "fr": "法国", "es": "西班牙", "it": "意大利",
    "gb": "英国", "us": "美国", "at": "奥地利", "ch": "瑞士",
    "pt": "葡萄牙", "other": "其他地区",
}
TLD_COUNTRIES = {f".{code}": code for code in ("de", "fr", "es", "it", "at", "ch", "pt")}
DEFAULT_CONFIG = {
    "version": 2,
    "target_language": "zh",
    "subscriptions": [
        {"id": "backstageclassical", "name": "BackstageClassical", "country": "de",
         "url": "https://backstageclassical.com/", "feed_url": "https://backstageclassical.com/feed",
         "source_type": "rss", "language": "", "mode": "summary", "enabled": True},
        {"id": "scherzo", "name": "Scherzo", "country": "es",
         "url": "https://scherzo.es/noticias/criticas/", "feed_url": "https://scherzo.es/feed",
         "source_type": "rss", "language": "", "mode": "summary", "enabled": True},
        {"id": "slipped-disc", "name": "Slipped Disc", "country": "gb",
         "url": "https://slippedisc.com/", "feed_url": "https://slippedisc.com/feed",
         "source_type": "rss", "language": "", "mode": "summary", "enabled": True},
    ],
}
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; Byelingua/2.0; +https://byelingua.vercel.app/)",
    "Accept-Language": "en-US,en;q=0.8",
})
MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
MAX_ARTICLES = int(os.environ.get("MAX_ARTICLES", "200"))
RECENT_DAYS = int(os.environ.get("RECENT_DAYS", "14"))


def get_openai_client():
    return OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def require_admin(headers):
    expected = os.environ.get("ADMIN_PASSWORD", "")
    supplied = headers.get("X-Admin-Password", "")
    if not expected:
        raise PermissionError("尚未在 Vercel 设置 ADMIN_PASSWORD。")
    if not hmac.compare_digest(expected, supplied):
        raise PermissionError("管理密码不正确。")


def blob_client():
    if not os.environ.get("BLOB_READ_WRITE_TOKEN"):
        raise RuntimeError("尚未连接 Vercel Blob 存储。")
    from vercel.blob import BlobClient
    return BlobClient()


def load_blob_json(pathname, default):
    token = os.environ.get("BLOB_READ_WRITE_TOKEN", "")
    with blob_client() as client:
        listing = client.list_objects(prefix=pathname)
        match = next((blob for blob in listing.blobs if blob.pathname == pathname), None)
    if match is None:
        return default
    response = SESSION.get(match.url, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    response.raise_for_status()
    return response.json()


def save_blob_json(pathname, value):
    payload = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
    with blob_client() as client:
        client.put(pathname, payload, access="private", content_type="application/json; charset=utf-8",
                   overwrite=True, cache_control_max_age=0)


def load_config():
    config = load_blob_json("byelingua/config.json", json.loads(json.dumps(DEFAULT_CONFIG)))
    config.setdefault("target_language", "zh")
    config.setdefault("subscriptions", [])
    if int(config.get("version", 1)) < 2:
        existing = {item.get("feed_url") for item in config["subscriptions"]}
        config["subscriptions"].extend(
            json.loads(json.dumps(item)) for item in DEFAULT_CONFIG["subscriptions"]
            if item["feed_url"] not in existing
        )
        config["version"] = 2
        save_blob_json("byelingua/config.json", config)
    return config


def canonical_url(base, href=""):
    joined = urljoin(base, href)
    parsed = urlsplit(joined.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("请输入有效的 http 或 https 网站地址。")
    path = re.sub(r"/{2,}", "/", parsed.path).rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def country_from_url(url):
    hostname = (urlsplit(url).hostname or "").lower()
    for suffix, country in TLD_COUNTRIES.items():
        if hostname.endswith(suffix):
            return country
    if hostname.endswith(".uk"):
        return "gb"
    if hostname.endswith(".com") and any(name in hostname for name in ("nytimes", "washingtonpost", "latimes")):
        return "us"
    return "other"


def country_from_language(value):
    language = str(value or "").lower().replace("_", "-").split("-")[0]
    return {"de": "de", "fr": "fr", "es": "es", "it": "it", "pt": "pt"}.get(language, "other")


def fetch(url):
    response = SESSION.get(url, timeout=(10, 30))
    response.raise_for_status()
    return response


def discover_source(url):
    source_url = canonical_url(url)
    response = fetch(source_url)
    content_type = response.headers.get("Content-Type", "").lower()
    sample = response.text[:800].lower()
    if "xml" in content_type or "<rss" in sample or "<feed" in sample:
        parsed = feedparser.parse(response.content)
        if parsed.entries:
            detected = country_from_url(source_url)
            if detected == "other":
                detected = country_from_language(parsed.feed.get("language"))
            return source_url, "rss", detected
    soup = BeautifulSoup(response.content, "html.parser")
    detected = country_from_url(source_url)
    if detected == "other":
        html = soup.select_one("html[lang]")
        locale = soup.select_one('meta[property="og:locale"]')
        detected = country_from_language((html.get("lang") if html else "") or (locale.get("content") if locale else ""))
    for link in soup.select('link[rel~="alternate"][href]'):
        kind = link.get("type", "").lower()
        if kind in {"application/rss+xml", "application/atom+xml"}:
            feed_url = canonical_url(source_url, link["href"])
            parsed = feedparser.parse(fetch(feed_url).content)
            if parsed.entries:
                feed_country = country_from_language(parsed.feed.get("language"))
                return feed_url, "rss", feed_country if feed_country != "other" else detected
    return source_url, "website", detected


def validate_subscription(data):
    source_url = canonical_url(str(data.get("url", "")))
    feed_url, source_type, detected_country = discover_source(source_url)
    name = str(data.get("name", "")).strip() or (urlsplit(source_url).hostname or source_url)
    country = str(data.get("country", "auto")).strip().lower()
    if country == "auto" or country not in COUNTRIES:
        country = detected_country
    language = str(data.get("language", "")).strip().lower()
    if language and language not in LANGUAGES:
        raise ValueError("不支持所选输出语言。")
    mode = str(data.get("mode", "summary")).strip().lower()
    if mode not in {"summary", "translate"}:
        raise ValueError("不支持所选处理方式。")
    identifier = hashlib.sha256(feed_url.encode("utf-8")).hexdigest()[:16]
    return {"id": identifier, "name": name, "country": country, "url": source_url,
            "feed_url": feed_url, "source_type": source_type, "language": language,
            "mode": mode, "enabled": bool(data.get("enabled", True))}


def parse_date(value):
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(str(value))
        except (TypeError, ValueError, OverflowError):
            return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def soup_date(soup):
    selectors = (('meta[property="article:published_time"]', "content"),
                 ('meta[name="date"]', "content"), ("time[datetime]", "datetime"))
    for selector, attribute in selectors:
        node = soup.select_one(selector)
        if node:
            parsed = parse_date(node.get(attribute))
            if parsed:
                return parsed
    return ""


def extract_article(url):
    response = fetch(canonical_url(url))
    soup = BeautifulSoup(response.content, "html.parser")
    for element in soup.select("script,style,nav,footer,header,aside,form,.advertisement,.sharedaddy"):
        element.decompose()
    article = soup.select_one("article,.entry-content,.post-content,.article-content,main") or soup
    paragraphs, seen = [], set()
    for paragraph in article.select("p"):
        text = " ".join(paragraph.get_text(" ", strip=True).split())
        if len(text) >= 50 and text not in seen:
            paragraphs.append(text)
            seen.add(text)
    result = "\n".join(paragraphs)[:12000]
    if len(result) < 200:
        raise ValueError("无法从该页面提取足够的文章正文。")
    return result, soup_date(soup)


def entry_date(entry):
    return parse_date(entry.get("published") or entry.get("updated") or "")


def entry_text(entry):
    content = entry.get("content") or []
    raw = content[0].get("value", "") if content and isinstance(content, list) else (
        entry.get("summary") or entry.get("description") or "")
    return BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)[:12000]


def collect_rss(subscription, seen_urls, limit):
    feed = feedparser.parse(fetch(subscription["feed_url"]).content)
    articles = []
    for entry in feed.entries:
        link = canonical_url(subscription["url"], entry.get("link", ""))
        if link in seen_urls:
            continue
        articles.append({"title": entry.get("title", link), "url": link,
                         "published": entry_date(entry), "feed_text": entry_text(entry)})
        if len(articles) >= limit:
            break
    return articles


def collect_website(subscription, seen_urls, limit):
    soup = BeautifulSoup(fetch(subscription["url"]).content, "html.parser")
    selectors = "article h1 a,article h2 a,article h3 a,h1 a,h2 a,h3 a,.post-title a,.entry-title a,a:has(h2)"
    hostname = urlsplit(subscription["url"]).hostname
    articles, local_seen = [], set()
    for link in soup.select(selectors):
        title = " ".join(link.get_text(" ", strip=True).split())
        href = link.get("href")
        if not href or len(title) < 12:
            continue
        try:
            url = canonical_url(subscription["url"], href)
        except ValueError:
            continue
        if urlsplit(url).hostname != hostname or url in seen_urls or url in local_seen:
            continue
        if any(piece in urlsplit(url).path.lower() for piece in ("/author/", "/tag/", "/category/", "/page/")):
            continue
        local_seen.add(url)
        articles.append({"title": title, "url": url, "published": "", "feed_text": ""})
        if len(articles) >= limit:
            break
    return articles


def collect_new_articles(subscription, seen_urls, limit=2):
    if subscription.get("source_type") == "website":
        return collect_website(subscription, seen_urls, limit)
    return collect_rss(subscription, seen_urls, limit)


def translate_article(article_text, language_code, mode):
    language = LANGUAGES.get(language_code, LANGUAGES["zh"])
    if mode == "summary":
        instruction = (f"用{language}写一段准确、自然的新闻摘要，约150至250字。只使用原文事实，"
                       "保留人名、作品名、机构和地点；不要使用‘本文介绍’之类套话，只输出摘要。")
    else:
        instruction = (f"将正文完整翻译成{language}。保持原意和段落，准确保留专有名词，"
                       "不要解释或补充，只输出译文。")
    response = get_openai_client().responses.create(model=MODEL, input=f"{instruction}\n\n正文：\n{article_text}")
    return response.output_text.strip()


def send_digest_email(items):
    api_key = os.environ.get("RESEND_API_KEY", "")
    recipients = [value.strip() for value in os.environ.get("DIGEST_TO_EMAIL", "").replace(";", ",").split(",") if value.strip()]
    if not api_key or not recipients or not items:
        return []
    sender = os.environ.get("EMAIL_FROM", "Byelingua <onboarding@resend.dev>")
    sections = ["<article style='margin:0 0 28px'>"
                f"<p style='color:#64748b;margin:0'>{escape(item['source'])} · {escape(COUNTRIES.get(item['country'], '其他地区'))}</p>"
                f"<h2><a href='{escape(item['url'])}'>{escape(item['title'])}</a></h2>"
                f"<p style='line-height:1.7'>{escape(item['result'])}</p></article>" for item in items]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    batch_key = hashlib.sha256("|".join(item["url"] for item in items).encode()).hexdigest()[:16]
    sent = []
    for recipient in recipients[:50]:
        response = requests.post("https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                     "Idempotency-Key": f"byelingua-{today}-{batch_key}-{hashlib.sha256(recipient.encode()).hexdigest()[:10]}"},
            json={"from": sender, "to": [recipient], "subject": f"Byelingua 国际音乐简报 · {today}",
                  "html": "<main style='max-width:720px;margin:auto;font-family:Arial,sans-serif'><h1>国际音乐简报</h1>" + "".join(sections) + "</main>"}, timeout=30)
        response.raise_for_status()
        sent.append(response.json())
    return sent


def run_daily_digest():
    config = load_config()
    seen_data = load_blob_json("byelingua/seen.json", {"urls": []})
    archive = load_blob_json("byelingua/articles.json", {"updated_at": "", "articles": []})
    seen_urls = {canonical_url(url) for url in seen_data.get("urls", [])}
    completed_urls, results, errors = [], [], []
    for subscription in config["subscriptions"]:
        if not subscription.get("enabled", True):
            continue
        try:
            candidates = collect_new_articles(subscription, seen_urls)
        except Exception as error:
            errors.append(f"{subscription['name']}: {error}")
            continue
        language = subscription.get("language") or config["target_language"]
        for article in candidates:
            try:
                try:
                    text, page_date = extract_article(article["url"])
                    article["published"] = article["published"] or page_date
                except Exception:
                    text = article.get("feed_text", "")
                    if len(text) < 200:
                        raise
                result = translate_article(text, language, subscription["mode"])
                item = {**article, "id": hashlib.sha256(article["url"].encode()).hexdigest()[:16],
                        "source": subscription["name"], "country": subscription["country"],
                        "language": language, "mode": subscription["mode"], "result": result,
                        "processed_at": datetime.now(timezone.utc).isoformat()}
                item.pop("feed_text", None)
                results.append(item)
                completed_urls.append(article["url"])
                seen_urls.add(article["url"])
            except Exception as error:
                errors.append(f"{article['title']}: {error}")
    merged_articles = results + [item for item in archive.get("articles", []) if item.get("url") not in completed_urls]
    now = datetime.now(timezone.utc).isoformat()
    save_blob_json("byelingua/articles.json", {"updated_at": now, "articles": merged_articles[:MAX_ARTICLES]})
    save_blob_json("byelingua/seen.json", {"urls": list(seen_urls)[:2000]})
    send_digest_email(results)
    return {"processed": len(results), "items": len(merged_articles[:MAX_ARTICLES]), "errors": errors[:10]}


def public_payload():
    config = load_config()
    archive = load_blob_json("byelingua/articles.json", {"updated_at": "", "articles": []})
    return {"target_language": config.get("target_language", "zh"), "countries": COUNTRIES,
            "updated_at": archive.get("updated_at", ""), "articles": archive.get("articles", [])}


class handler(BaseHTTPRequestHandler):
    def send_json(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            self.send_json(200, public_payload())
        except Exception as error:
            self.send_json(500, {"error": str(error)})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            action = data.get("action", "get_public")
            if action == "get_public":
                self.send_json(200, public_payload())
                return
            require_admin(self.headers)
            config = load_config()
            if action == "get_config":
                self.send_json(200, config)
            elif action == "save_settings":
                language = data.get("target_language", "zh")
                if language not in LANGUAGES:
                    raise ValueError("不支持所选输出语言。")
                config["target_language"] = language
                save_blob_json("byelingua/config.json", config)
                self.send_json(200, config)
            elif action == "save_subscription":
                subscription = validate_subscription(data.get("subscription", {}))
                config["subscriptions"] = [item for item in config["subscriptions"] if item.get("id") != subscription["id"]] + [subscription]
                save_blob_json("byelingua/config.json", config)
                self.send_json(200, config)
            elif action == "delete_subscription":
                identifier = data.get("id", "")
                config["subscriptions"] = [item for item in config["subscriptions"] if item.get("id") != identifier]
                save_blob_json("byelingua/config.json", config)
                self.send_json(200, config)
            elif action == "run_digest":
                self.send_json(200, run_daily_digest())
            else:
                self.send_json(400, {"error": "未知操作。"})
        except PermissionError as error:
            self.send_json(401, {"error": str(error)})
        except (ValueError, requests.RequestException) as error:
            self.send_json(400, {"error": str(error)})
        except Exception as error:
            self.send_json(500, {"error": str(error)})
