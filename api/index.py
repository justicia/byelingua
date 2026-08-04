import asyncio
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import escape
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urljoin, urlparse

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
}
COUNTRIES = {"de", "fr", "es", "other"}
DEFAULT_CONFIG = {
    "target_language": "zh",
    "subscriptions": [],
}


def get_openai_client():
    return OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def require_admin(headers):
    expected = os.environ.get("ADMIN_PASSWORD", "")
    supplied = headers.get("X-Admin-Password", "")
    if not expected:
        raise PermissionError("请先在 Vercel 设置 ADMIN_PASSWORD。")
    if not hmac.compare_digest(expected, supplied):
        raise PermissionError("管理密码不正确。")


def blob_client():
    if not os.environ.get("BLOB_READ_WRITE_TOKEN"):
        raise RuntimeError("请先为项目创建 Vercel Blob 存储。")
    from vercel.blob import BlobClient
    return BlobClient()


async def read_private_blob(pathname):
    from vercel.blob import AsyncBlobClient

    async with AsyncBlobClient() as client:
        result = await client.get(pathname, access="private")
        if result is None or result.status_code != 200 or result.stream is None:
            return None
        chunks = []
        async for chunk in result.stream:
            chunks.append(chunk)
        return b"".join(chunks)


def load_blob_json(pathname, default):
    body = asyncio.run(read_private_blob(pathname))
    if body is None:
        return default
    return json.loads(body.decode("utf-8"))


def save_blob_json(pathname, value):
    payload = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
    with blob_client() as client:
        client.put(
            pathname,
            payload,
            access="private",
            content_type="application/json; charset=utf-8",
            overwrite=True,
            cache_control_max_age=0,
        )


def load_config():
    config = load_blob_json("byelingua/config.json", DEFAULT_CONFIG.copy())
    config.setdefault("target_language", "zh")
    config.setdefault("subscriptions", [])
    return config


def save_config(config):
    save_blob_json("byelingua/config.json", config)


def normalize_url(url):
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("请输入有效的 http 或 https 地址。")
    return parsed.geturl()


def discover_feed_url(url):
    headers = {"User-Agent": "Mozilla/5.0 Byelingua/1.0"}
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()
    sample = response.text[:500].lower()
    if "xml" in content_type or "<rss" in sample or "<feed" in sample:
        parsed_feed = feedparser.parse(response.content)
        if parsed_feed.entries:
            return url

    soup = BeautifulSoup(response.text, "html.parser")
    for link in soup.find_all("link", href=True):
        rel = " ".join(link.get("rel", [])).lower()
        kind = link.get("type", "").lower()
        if "alternate" in rel and kind in {
            "application/rss+xml",
            "application/atom+xml",
        }:
            return urljoin(url, link["href"])

    raise ValueError("没有找到 RSS。请直接填写该网站的 RSS 地址。")


def extract_article_text(url):
    url = normalize_url(url)
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 Byelingua/1.0"},
        timeout=20,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
        element.decompose()
    article = soup.find("article") or soup.find("main") or soup
    paragraphs = []
    seen = set()
    for paragraph in article.find_all("p"):
        text = paragraph.get_text(" ", strip=True)
        if len(text) >= 40 and text not in seen:
            paragraphs.append(text)
            seen.add(text)
    result = "\n".join(paragraphs)
    if not result:
        raise ValueError("未能从该页面提取正文。")
    return result[:12000]


def translate_article(article_text, language_code, mode):
    language = LANGUAGES.get(language_code, LANGUAGES["zh"])
    if mode == "summary":
        request = (
            f"请使用{language}总结下面的文章。控制在 200 至 350 字，保留重要的"
            "人名、作品名、机构名、日期与作者观点，只使用原文信息，只输出摘要正文。"
        )
    else:
        request = (
            f"请将下面文章准确、自然地翻译成{language}。保留段落结构、专有名词，"
            "不要增加解释，只输出译文。"
        )
    response = get_openai_client().responses.create(
        model="gpt-5-mini",
        input=f"{request}\n\n原文：\n{article_text}",
    )
    return response.output_text.strip()


def validate_subscription(data):
    name = str(data.get("name", "")).strip()
    country = str(data.get("country", "other")).strip().lower()
    language = str(data.get("language", "")).strip().lower()
    mode = str(data.get("mode", "summary")).strip().lower()
    source_url = normalize_url(str(data.get("url", "")))
    if not name:
        raise ValueError("请填写订阅名称。")
    if country not in COUNTRIES:
        country = "other"
    if language and language not in LANGUAGES:
        raise ValueError("不支持所选语言。")
    if mode not in {"summary", "translate"}:
        raise ValueError("不支持所选处理方式。")
    feed_url = discover_feed_url(source_url)
    identifier = hashlib.sha256(feed_url.encode("utf-8")).hexdigest()[:16]
    return {
        "id": identifier,
        "name": name,
        "country": country,
        "url": source_url,
        "feed_url": feed_url,
        "language": language,
        "mode": mode,
        "enabled": bool(data.get("enabled", True)),
    }


def parse_entry_date(entry):
    raw = entry.get("published") or entry.get("updated") or ""
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return raw


def collect_new_articles(subscription, seen_urls, limit=3):
    response = requests.get(
        subscription["feed_url"],
        headers={"User-Agent": "Mozilla/5.0 Byelingua/1.0"},
        timeout=20,
    )
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    articles = []
    for entry in feed.entries:
        link = entry.get("link", "").strip()
        if not link or link in seen_urls:
            continue
        articles.append({
            "title": entry.get("title", link),
            "url": link,
            "published": parse_entry_date(entry),
        })
        if len(articles) >= limit:
            break
    return articles


def send_digest_email(items):
    api_key = os.environ.get("RESEND_API_KEY", "")
    recipient = os.environ.get("DIGEST_TO_EMAIL", "")
    sender = os.environ.get("EMAIL_FROM", "Byelingua <onboarding@resend.dev>")
    if not api_key or not recipient:
        raise RuntimeError("请设置 RESEND_API_KEY 和 DIGEST_TO_EMAIL。")

    sections = []
    for item in items:
        sections.append(
            "<article style='margin:0 0 28px'>"
            f"<p style='color:#64748b;margin:0'>{escape(item['source'])}</p>"
            f"<h2 style='margin:6px 0'><a href='{escape(item['url'])}'>{escape(item['title'])}</a></h2>"
            f"<p style='white-space:pre-wrap;line-height:1.65'>{escape(item['result'])}</p>"
            "</article>"
        )
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": f"byelingua-{today}",
        },
        json={
            "from": sender,
            "to": [recipient],
            "subject": f"Byelingua 每日乐评摘要 · {today}",
            "html": "<main style='max-width:720px;margin:auto;font-family:Arial,sans-serif'>"
                    "<h1>每日乐评摘要</h1>" + "".join(sections) + "</main>",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def run_daily_digest():
    config = load_config()
    seen_data = load_blob_json("byelingua/seen.json", {"urls": []})
    seen_urls = set(seen_data.get("urls", []))
    completed_urls = []
    results = []

    for subscription in config["subscriptions"]:
        if not subscription.get("enabled", True):
            continue
        articles = collect_new_articles(subscription, seen_urls)
        language = subscription.get("language") or config["target_language"]
        for article in articles:
            try:
                text = extract_article_text(article["url"])
                result = translate_article(text, language, subscription["mode"])
                results.append({
                    **article,
                    "source": subscription["name"],
                    "country": subscription["country"],
                    "result": result,
                })
                completed_urls.append(article["url"])
            except Exception as error:
                results.append({
                    **article,
                    "source": subscription["name"],
                    "country": subscription["country"],
                    "result": f"处理失败：{error}",
                })

    if results:
        send_digest_email(results)
        merged = (completed_urls + list(seen_urls))[:2000]
        save_blob_json("byelingua/seen.json", {"urls": merged})
    return {"processed": len(completed_urls), "items": len(results)}


class handler(BaseHTTPRequestHandler):
    def send_json(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.send_json(200, {"status": "ok", "message": "Python API is working."})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            action = data.get("action", "process_article")

            if action == "process_article":
                text = extract_article_text(data.get("url", ""))
                result = translate_article(
                    text,
                    data.get("target_language", "zh"),
                    data.get("mode", "summary"),
                )
                self.send_json(200, {"result": result, "characters": len(text)})
                return

            require_admin(self.headers)
            config = load_config()

            if action == "get_config":
                self.send_json(200, config)
            elif action == "save_settings":
                language = data.get("target_language", "zh")
                if language not in LANGUAGES:
                    raise ValueError("不支持所选语言。")
                config["target_language"] = language
                save_config(config)
                self.send_json(200, config)
            elif action == "save_subscription":
                subscription = validate_subscription(data.get("subscription", {}))
                config["subscriptions"] = [
                    item for item in config["subscriptions"]
                    if item.get("id") != subscription["id"]
                ] + [subscription]
                save_config(config)
                self.send_json(200, config)
            elif action == "delete_subscription":
                identifier = data.get("id", "")
                config["subscriptions"] = [
                    item for item in config["subscriptions"]
                    if item.get("id") != identifier
                ]
                save_config(config)
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
