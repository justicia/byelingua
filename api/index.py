"""Byelingua API: subscriptions plus manually imported WeChat translations."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import unicodedata
import uuid
import base64
from difflib import SequenceMatcher
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html import escape
from http.server import BaseHTTPRequestHandler
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import feedparser
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

LANGUAGES = {"en":"English","zh":"简体中文","es":"Español","fr":"Français","de":"Deutsch","it":"Italiano","pt":"Português","ja":"日本語"}
COUNTRIES = {"cn":"中国","de":"德国","fr":"法国","es":"西班牙","it":"意大利","gb":"英国","us":"美国","at":"奥地利","ch":"瑞士","pt":"葡萄牙","other":"其他地区"}
DEFAULT_CONFIG = {"version":3,"target_language":"zh","subscriptions":[
    {"id":"backstageclassical","name":"BackstageClassical","country":"de","url":"https://backstageclassical.com/","feed_url":"https://backstageclassical.com/feed","source_type":"rss","language":"","mode":"summary","enabled":True},
    {"id":"scherzo","name":"Scherzo","country":"es","url":"https://scherzo.es/noticias/criticas/","feed_url":"https://scherzo.es/feed","source_type":"rss","language":"","mode":"summary","enabled":True},
    {"id":"slipped-disc","name":"Slipped Disc","country":"gb","url":"https://slippedisc.com/","feed_url":"https://slippedisc.com/feed","source_type":"rss","language":"","mode":"summary","enabled":True},
]}
MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
MAX_ARTICLES = int(os.environ.get("MAX_ARTICLES", "200"))
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent":"Mozilla/5.0 (compatible; Byelingua/3.0)",
    "Accept-Language":"en-US,en;q=0.8"
})


def normalize_search_key(value):
    """Stable accent-insensitive key; display/canonical values are never changed."""
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("œ", "oe").replace("Œ", "oe").replace("æ", "ae").replace("Æ", "ae")
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"[^\w\s'\-]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def valid_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def search_match_score(query, *values):
    needle = normalize_search_key(query)
    haystacks = [normalize_search_key(value) for value in values if value]
    if not needle:
        return 0.0
    if any(value == needle for value in haystacks):
        return 1.0
    if any(value.startswith(needle) for value in haystacks):
        return 0.9
    if any(needle in value for value in haystacks):
        return 0.8
    return max((SequenceMatcher(None, needle, value).ratio() for value in haystacks), default=0.0)


def event_keys_for_internal_ids(internal_ids):
    if not internal_ids:
        return {}
    rows = supabase_service("GET", "/rest/v1/events", params={"id": f"in.({','.join(internal_ids)})", "select": "id,event_key", "limit": "5000"}) or []
    return {str(row.get("id")): str(row.get("event_key")) for row in rows if row.get("id") and row.get("event_key")}

PARIS_TIMEZONE = ZoneInfo("Europe/Paris")


def require_admin(headers):
    expected, supplied = os.environ.get("ADMIN_PASSWORD", ""), headers.get("X-Admin-Password", "")
    if not expected:
        raise PermissionError("尚未在 Vercel 设置 ADMIN_PASSWORD。")
    if not hmac.compare_digest(expected, supplied):
        raise PermissionError("管理密码不正确。")


def require_wechat_sync(headers):
    expected = os.environ.get("WECHAT_SYNC_SECRET", "")
    supplied = headers.get("X-WeChat-Sync-Secret", "")
    if not expected:
        raise PermissionError("WECHAT_SYNC_SECRET is not configured.")
    if not hmac.compare_digest(expected, supplied):
        raise PermissionError("Invalid WeChat sync credentials.")


PUBLIC_ARTICLE_COLUMNS = (
    "id", "canonical_url", "url", "kind", "source", "country",
    "original_title", "title", "language", "mode", "category",
    "translation_instruction", "author",
    "author_label", "cover", "contents", "summaries", "translations",
    "translated_titles", "titles", "translation_jobs", "result", "raw_data",
    "published", "published_at", "processed_at", "metadata_updated_at",
    "updated_at",
)
PUBLIC_ARTICLE_JSON_COLUMNS = {
    "contents", "summaries", "translations", "translated_titles", "titles",
    "translation_jobs",
}


def public_article_from_row(row):
    """Restore the legacy API shape while Supabase remains the source of truth."""
    raw_data = dict(row.get("raw_data") or {})
    article = dict(raw_data)
    for key, value in row.items():
        if key not in {"raw_data", "created_at"} and value is not None:
            article[key] = value
    article["published"] = row.get("published_at") or raw_data.get("published") or ""
    return article


def public_article_to_row(article, now=None):
    """Map the runtime article object onto the public_articles schema."""
    now = now or datetime.now(timezone.utc).isoformat()
    url = str(article.get("url") or article.get("canonical_url") or "").strip()
    if not url:
        raise ValueError("Public article URL is required.")
    identifier = str(article.get("id") or hashlib.sha256(url.encode()).hexdigest()[:16])
    row = {
        key: ({} if key in PUBLIC_ARTICLE_JSON_COLUMNS else None)
        for key in PUBLIC_ARTICLE_COLUMNS
    }
    for key in PUBLIC_ARTICLE_COLUMNS:
        if key in article and article[key] is not None:
            row[key] = article[key]
    row.update({
        "id": identifier,
        "canonical_url": article.get("canonical_url") or url,
        "url": url,
        "published": True,
        "published_at": article.get("published_at") or article.get("published") or None,
        "updated_at": now,
        "raw_data": article,
    })
    return row


def load_public_articles():
    rows = supabase_service(
        "GET",
        "/rest/v1/public_articles",
        params={"published": "eq.true", "select": "*", "order": "published_at.desc"},
    ) or []
    return [public_article_from_row(row) for row in rows]


def save_public_articles(articles):
    """Replace the public archive in Supabase, matching the old archive semantics."""
    now = datetime.now(timezone.utc).isoformat()
    rows = [public_article_to_row(article, now) for article in articles]
    existing = supabase_service(
        "GET",
        "/rest/v1/public_articles",
        params={"published": "eq.true", "select": "id"},
    ) or []
    if rows:
        supabase_service(
            "POST",
            "/rest/v1/public_articles",
            params={"on_conflict": "id"},
            payload=rows,
            prefer="resolution=merge-duplicates,return=minimal",
        )
    retained = {row["id"] for row in rows}
    for row in existing:
        if row.get("id") not in retained:
            supabase_service(
                "DELETE",
                "/rest/v1/public_articles",
                params={"id": f"eq.{row['id']}"},
                prefer="return=minimal",
            )


def load_blob_json(pathname, default):
    """Compatibility shim for article workflows migrated away from Blob."""
    if pathname != "byelingua/articles.json":
        raise ValueError(f"Unsupported legacy Blob path: {pathname}")
    return {"updated_at": "", "articles": load_public_articles()}


def save_blob_json(pathname, value):
    """Compatibility shim that persists the legacy archive shape in Supabase."""
    if pathname != "byelingua/articles.json":
        raise ValueError(f"Unsupported legacy Blob path: {pathname}")
    save_public_articles(value.get("articles", []))

def load_app_state(key, default):
    rows = supabase_service(
        "GET",
        "/rest/v1/public_app_state",
        params={
            "key": f"eq.{key}",
            "select": "value",
            "limit": "1",
        },
    )

    if not rows:
        return json.loads(json.dumps(default))

    return rows[0].get("value", json.loads(json.dumps(default)))


def save_app_state(key, value):
    supabase_service(
        "POST",
        "/rest/v1/public_app_state",
        params={"on_conflict": "key"},
        payload={
            "key": key,
            "value": value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        prefer="resolution=merge-duplicates,return=minimal",
    )


def load_seen_urls():
    rows = supabase_service(
        "GET",
        "/rest/v1/public_seen_urls",
        params={
            "select": "url",
            "order": "created_at.desc",
            "limit": "2000",
        },
    ) or []

    return [row["url"] for row in rows if row.get("url")]


def add_seen_urls(urls):
    rows = [{"url": url} for url in urls if url]

    if not rows:
        return

    supabase_service(
        "POST",
        "/rest/v1/public_seen_urls",
        params={"on_conflict": "url"},
        payload=rows,
        prefer="resolution=ignore-duplicates,return=minimal",
    )


def remove_seen_url(url):
    supabase_service(
        "DELETE",
        "/rest/v1/public_seen_urls",
        params={"url": f"eq.{url}"},
        prefer="return=minimal",
    )


def load_scheduled_state(default=None):
    default = default or {"paris_date": ""}

    rows = supabase_service(
        "GET",
        "/rest/v1/public_scheduled_state",
        params={
            "key": "eq.daily_update",
            "select": "value",
            "limit": "1",
        },
    )

    if not rows:
        return json.loads(json.dumps(default))

    return rows[0].get("value", json.loads(json.dumps(default)))


def save_scheduled_state(value):
    supabase_service(
        "POST",
        "/rest/v1/public_scheduled_state",
        params={"on_conflict": "key"},
        payload={
            "key": "daily_update",
            "value": value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        prefer="resolution=merge-duplicates,return=minimal",
    )


def load_config():
    config = load_app_state(
        "config",
        json.loads(json.dumps(DEFAULT_CONFIG)),
    )

    config.setdefault("target_language", "zh")
    config.setdefault("subscriptions", [])

    if int(config.get("version", 1)) < 3:
        existing = {
            item.get("feed_url")
            for item in config["subscriptions"]
        }

        config["subscriptions"].extend(
            json.loads(json.dumps(item))
            for item in DEFAULT_CONFIG["subscriptions"]
            if item["feed_url"] not in existing
        )

        config["version"] = 3
        save_app_state("config", config)

    return config


def save_config(config):
    save_app_state("config", config)


def canonical_url(base, href=""):
    parsed = urlsplit(urljoin(base, href).strip())
    if parsed.scheme not in {"http","https"} or not parsed.netloc:
        raise ValueError("请输入有效的 http 或 https 地址。")
    path = re.sub(r"/{2,}", "/", parsed.path).rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def normalize_wechat_url(url):
    """Validate a WeChat article URL while retaining legacy /s query identifiers."""
    parsed = urlsplit(str(url).strip())
    if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() != "mp.weixin.qq.com":
        raise ValueError("Only mp.weixin.qq.com article links are accepted.")
    path = re.sub(r"/{2,}", "/", parsed.path).rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), "mp.weixin.qq.com", path, parsed.query, ""))


def country_from_url(url):
    host = (urlsplit(url).hostname or "").lower()
    for code in ("de","fr","es","it","at","ch","pt"):
        if host.endswith(f".{code}"):
            return code
    if host.endswith(".uk"):
        return "gb"
    return "other"


def country_from_language(value):
    code = str(value or "").lower().replace("_", "-").split("-")[0]
    return code if code in {"de","fr","es","it","pt"} else "other"


def fetch(url):
    response = SESSION.get(url, timeout=(8,15))
    response.raise_for_status()
    return response


def fetch_wechat_direct(url):
    """Fetch a public WeChat article directly, without an exporter service."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
            "MicroMessenger/8.0.49"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
        "Referer": "https://mp.weixin.qq.com/",
    }
    # Keep the synchronous ingestion request short. Translation happens later,
    # from the Chinese text already persisted in Supabase.
    response = SESSION.get(url, headers=headers, timeout=(4, 8), allow_redirects=True)
    response.raise_for_status()
    html = response.content
    sample = response.text[:10000]
    blocked_markers = ("环境异常", "访问过于频繁", "请在微信客户端打开", "verify_", "waf-captcha")
    if any(marker in sample for marker in blocked_markers):
        raise ValueError("微信拒绝了服务器访问，请稍后重试或在下方粘贴中文全文。")
    return html


def discover_source(url):
    source_url = canonical_url(url)
    response = fetch(source_url)
    content_type, sample = response.headers.get("Content-Type", "").lower(), response.text[:800].lower()
    if "xml" in content_type or "<rss" in sample or "<feed" in sample:
        feed = feedparser.parse(response.content)
        if feed.entries:
            detected = country_from_url(source_url)
            return source_url, "rss", detected if detected != "other" else country_from_language(feed.feed.get("language"))
    soup = BeautifulSoup(response.content, "html.parser")
    detected = country_from_url(source_url)
    if detected == "other":
        html, locale = soup.select_one("html[lang]"), soup.select_one('meta[property="og:locale"]')
        detected = country_from_language((html.get("lang") if html else "") or (locale.get("content") if locale else ""))
    for link in soup.select('link[rel~="alternate"][href]'):
        if link.get("type", "").lower() in {"application/rss+xml","application/atom+xml"}:
            feed_url = canonical_url(source_url, link["href"])
            feed = feedparser.parse(fetch(feed_url).content)
            if feed.entries:
                feed_country = country_from_language(feed.feed.get("language"))
                return feed_url, "rss", feed_country if feed_country != "other" else detected
    return source_url, "website", detected


def validate_subscription(data):
    source_url = canonical_url(str(data.get("url", "")))
    feed_url, source_type, detected = discover_source(source_url)
    country = str(data.get("country", "auto")).lower()
    country = detected if country == "auto" or country not in COUNTRIES else country
    language, mode = str(data.get("language", "")).lower(), str(data.get("mode", "summary")).lower()
    if language and language not in LANGUAGES:
        raise ValueError("不支持所选输出语言。")
    if mode not in {"summary","translate"}:
        raise ValueError("不支持所选处理方式。")
    return {"id":hashlib.sha256(feed_url.encode()).hexdigest()[:16],"name":str(data.get("name","")).strip() or (urlsplit(source_url).hostname or source_url),"country":country,"url":source_url,"feed_url":feed_url,"source_type":source_type,"language":language,"mode":mode,"enabled":bool(data.get("enabled",True))}


def parse_date(value):
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(str(value))
        except (TypeError,ValueError,OverflowError):
            return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def soup_date(soup):
    for selector, attribute in (('meta[property="article:published_time"]',"content"),('meta[name="date"]',"content"),("time[datetime]","datetime")):
        node = soup.select_one(selector)
        parsed = parse_date(node.get(attribute)) if node else ""
        if parsed:
            return parsed
    return ""


def extract_article(url):
    soup = BeautifulSoup(fetch(canonical_url(url)).content, "html.parser")
    for node in soup.select("script,style,nav,footer,header,aside,form,.advertisement,.sharedaddy"):
        node.decompose()
    article = soup.select_one("article,.entry-content,.post-content,.article-content,main") or soup
    paragraphs, seen = [], set()
    for paragraph in article.select("p"):
        text = " ".join(paragraph.get_text(" ", strip=True).split())
        if len(text) >= 50 and text not in seen:
            paragraphs.append(text); seen.add(text)
    result = "\n".join(paragraphs)[:12000]
    if len(result) < 200:
        raise ValueError("无法从该页面提取足够正文。")
    return result, soup_date(soup)


def extract_wechat_article(url, manual_text="", manual_title="", manual_author=""):
    normalized = normalize_wechat_url(url)
    if (urlsplit(normalized).hostname or "").lower() != "mp.weixin.qq.com":
        raise ValueError("请输入 mp.weixin.qq.com 的微信公众号文章链接。")
    title = author = published = cover = extracted = ""
    if not manual_text.strip() or not manual_title.strip():
        try:
            content_bytes = fetch_wechat_direct(normalized)
            soup = BeautifulSoup(content_bytes, "html.parser")
        except (requests.RequestException, ValueError):
            soup = BeautifulSoup("", "html.parser")
        title_node, title_meta = soup.select_one("#activity-name"), soup.select_one('meta[property="og:title"]')
        author_node, author_meta = soup.select_one("#js_name,.account_nickname"), soup.select_one('meta[name="author"]')
        cover_meta, content = soup.select_one('meta[property="og:image"]'), soup.select_one("#js_content")
        title = (title_node.get_text(" ", strip=True) if title_node else "") or (title_meta.get("content", "").strip() if title_meta else "")
        author = (author_node.get_text(" ", strip=True) if author_node else "") or (author_meta.get("content", "").strip() if author_meta else "")
        cover, published = (cover_meta.get("content", "").strip() if cover_meta else ""), soup_date(soup)
        if content:
            for node in content.select("script,style,noscript"):
                node.decompose()
            lines = [" ".join(line.split()) for line in content.get_text("\n", strip=True).splitlines()]
            extracted = "\n\n".join(dict.fromkeys(line for line in lines if line))[:20000]
    text, title = manual_text.strip() or extracted, manual_title.strip() or title
    author = manual_author.strip() or author or "微信公众号"
    if len(text) < 200:
        raise ValueError("未读取到足够正文，请粘贴完整文章内容。")
    if not title:
        raise ValueError("未读取到标题，请填写备用标题。")
    return {"title":title,"source":author,"url":normalized,"published":published,"cover":cover,"text":text}


def translate_article(text, language_code, mode, title="", custom_instruction=""):
    language = LANGUAGES.get(language_code, LANGUAGES["zh"])
    instruction = (f"用{language}写一段准确自然的新闻摘要，约150至250字。只使用原文事实，保留专有名词，不要套话。" if mode == "summary" else f"将正文完整翻译成{language}。保持原意与段落，准确保留专有名词，不要解释或删减。")
    custom_instruction = str(custom_instruction or "").strip()[:1000]
    if custom_instruction:
        instruction += f"\n用户对译文的额外要求：{custom_instruction}"
    prompt = f"""{instruction}
同时把标题翻译成{language}。只返回有效 JSON，不要使用 Markdown：
{{"title":"翻译后的标题","content":"翻译或摘要后的正文"}}

原标题：{title}
正文：
{text}"""
    output = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), timeout=25.0, max_retries=0).responses.create(model=MODEL, input=prompt).output_text.strip()
    try:
        payload = json.loads(output.removeprefix("```json").removesuffix("```").strip())
        translated_title = str(payload.get("title", "")).strip()
        content = str(payload.get("content", "")).strip()
        if translated_title and content:
            return {"title":translated_title,"content":content}
    except (json.JSONDecodeError, AttributeError):
        pass
    return {"title":title,"content":output}


def translate_bilingual_article(text, title, mode):
    task = "分别写准确自然的新闻摘要" if mode == "summary" else "完整翻译正文"
    prompt = f"""请将原标题翻译成简体中文和英文，并将正文{task}为简体中文和英文。保持专有名词准确，只使用原文事实。
只返回有效 JSON，不要使用 Markdown：
{{"titles":{{"zh":"中文标题","en":"English title"}},"contents":{{"zh":"中文正文","en":"English content"}}}}

原标题：{title}
正文：
{text}"""
    output = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), timeout=35.0, max_retries=0).responses.create(model=MODEL, input=prompt).output_text.strip()
    try:
        payload = json.loads(output.removeprefix("```json").removesuffix("```").strip())
        titles, contents = payload.get("titles", {}), payload.get("contents", {})
        if all(str(titles.get(code, "")).strip() and str(contents.get(code, "")).strip() for code in ("zh","en")):
            return {"titles":{code:str(titles[code]).strip() for code in ("zh","en")},"contents":{code:str(contents[code]).strip() for code in ("zh","en")}}
    except (json.JSONDecodeError, AttributeError):
        pass
    raise ValueError("双语翻译返回格式不完整，请稍后重试。")


def translate_backfill_article(chinese_content, title):
    prompt = f"""现有正文已经是简体中文。请把原标题分别翻译成简体中文和英文，并把现有中文正文完整翻译成英文。保留所有事实、专有名词和段落，不要摘要或增删内容。
只返回有效 JSON，不要使用 Markdown：
{{"titles":{{"zh":"中文标题","en":"English title"}},"content_en":"English content"}}

原标题：{title}
现有中文正文：
{chinese_content}"""
    output = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), timeout=35.0, max_retries=0).responses.create(model=MODEL, input=prompt).output_text.strip()
    try:
        payload = json.loads(output.removeprefix("```json").removesuffix("```").strip())
        titles = payload.get("titles", {})
        content_en = str(payload.get("content_en", "")).strip()
        if all(str(titles.get(code, "")).strip() for code in ("zh", "en")) and content_en:
            return {"titles":{code:str(titles[code]).strip() for code in ("zh", "en")},"content_en":content_en}
    except (json.JSONDecodeError, AttributeError):
        pass
    raise ValueError("旧文章英文补全返回格式不完整，请稍后重试。")


def backfill_bilingual_article():
    archive = load_blob_json("byelingua/articles.json", {"updated_at":"","articles":[]})
    articles = archive.get("articles", [])
    item = next((article for article in reversed(articles) if not article.get("contents", {}).get("en")), None)
    if not item:
        return {"processed":0,"remaining":0}
    original_title = item.get("original_title") or item.get("title") or ""
    current_content = item.get("result", "")
    if not current_content.strip():
        raise ValueError("这篇旧文章没有可用于回填的中文正文。")
    bilingual = translate_backfill_article(current_content, original_title)
    item["titles"] = bilingual["titles"]
    item["contents"] = {"zh":current_content,"en":bilingual["content_en"]}
    item["title"], item["result"] = bilingual["titles"]["zh"], current_content
    item.setdefault("original_title", original_title)
    now = datetime.now(timezone.utc).isoformat()
    save_blob_json("byelingua/articles.json", {"updated_at":now,"articles":articles})
    remaining = sum(1 for article in articles if not article.get("contents", {}).get("en"))
    return {"processed":1,"remaining":remaining,"title":bilingual["titles"]["en"]}


def import_wechat_article(data):
    language = str(data.get("language", "")).lower()
    if language not in LANGUAGES:
        raise ValueError("请选择一种目标语言。")
    url = normalize_wechat_url(str(data.get("url", "")))
    archive = load_blob_json("byelingua/articles.json", {"updated_at":"","articles":[]})
    articles, existing = archive.get("articles", []), None
    existing = next((item for item in articles if item.get("url") == url), None)
    author_label = str(data.get("author_label") or data.get("author") or "").strip()[:120]
    category = str(data.get("category") or "").strip()[:80]
    published = parse_date(data.get("published"))
    custom_instruction = str(data.get("translation_instruction") or "").strip()[:1000]
    metadata_updates = {}
    if author_label: metadata_updates.update({"source":author_label,"author_label":author_label})
    if category: metadata_updates["category"] = category
    if published: metadata_updates["published"] = published
    if custom_instruction: metadata_updates["translation_instruction"] = custom_instruction
    if existing and language in existing.get("translations", {}):
        compatibility_updates = {
            "id":existing.get("id") or hashlib.sha256(url.encode()).hexdigest()[:16],
            "kind":"wechat",
            "country":"cn",
            "mode":"translate",
        }
        if not existing.get("contents"):
            compatibility_updates["contents"] = dict(existing.get("translations") or {})
        if not existing.get("titles") and existing.get("translated_titles"):
            compatibility_updates["titles"] = dict(existing["translated_titles"])
        updates = {**compatibility_updates, **metadata_updates}
        if any(existing.get(key) != value for key, value in updates.items()):
            existing.update(updates)
            now = datetime.now(timezone.utc).isoformat()
            existing["processed_at"] = now
            save_blob_json("byelingua/articles.json", {"updated_at":now,"articles":articles})
        return {"article":existing,"reused":True}
    stored_chinese = (existing or {}).get("translations", {}).get("zh") or (existing or {}).get("contents", {}).get("zh")
    if existing and str(stored_chinese or "").strip():
        # The archived Chinese article is canonical. Adding another language must
        # never fetch WeChat a second time.
        original_title = (existing.get("translated_titles", {}).get("zh") or
                          existing.get("titles", {}).get("zh") or
                          existing.get("original_title") or existing.get("title") or "")
        original_text = str(stored_chinese).strip()
        wechat = {key:value for key,value in existing.items() if key not in ("translations","translated_titles","titles","contents","result")}
    else:
        # WeChat is fetched exactly once, when the canonical Chinese version is created.
        wechat = extract_wechat_article(url, str(data.get("text", "")), str(data.get("title", "")), str(data.get("author", "")))
        original_title, original_text = wechat["title"], wechat.pop("text")
    translated = ({"title":original_title,"content":original_text} if language == "zh" else translate_article(original_text, language, "translate", original_title, custom_instruction))
    translation = translated["content"]
    translations = dict(existing.get("translations", {})) if existing else {}
    translations.setdefault("zh", original_text)
    translations[language] = translation
    now = datetime.now(timezone.utc).isoformat()
    translated_titles = dict(existing.get("translated_titles", {})) if existing else {}
    translated_titles.setdefault("zh", original_title)
    translated_titles[language] = translated["title"]
    item = {**(existing or {}),**wechat,**metadata_updates,"title":original_title,"original_title":original_title,"id":hashlib.sha256(url.encode()).hexdigest()[:16],"kind":"wechat","country":"cn","category":category or (existing or {}).get("category") or "未分类","author_label":author_label or wechat.get("source") or "微信公众号","language":language,"mode":"translate","translations":translations,"translated_titles":translated_titles,"titles":dict(translated_titles),"contents":dict(translations),"result":original_text,"processed_at":now}
    save_blob_json("byelingua/articles.json", {"updated_at":now,"articles":([item]+[x for x in articles if x.get("url") != url])[:MAX_ARTICLES]})
    return {"article":item,"reused":False}


def sync_wechat_article(data):
    """Persist only the canonical Chinese article; translations are separate."""
    chinese = dict(data or {})
    chinese["language"] = "zh"
    saved = import_wechat_article(chinese)
    return {"chinese":saved,"article":saved["article"]}


def save_wechat_chinese(data):
    """Admin import endpoint: fetch and persist Chinese without OpenAI work."""
    chinese = dict(data or {})
    chinese["language"] = "zh"
    return import_wechat_article(chinese)


PUBLIC_WECHAT_LANGUAGES = {"en", "es", "de", "fr"}


def is_wechat_article(item):
    """Accept current records and legacy records identified by their WeChat URL."""
    if not item:
        return False
    if item.get("kind") == "wechat" and item.get("country") == "cn":
        return True
    try:
        return (urlsplit(str(item.get("url") or "")).hostname or "").lower() == "mp.weixin.qq.com"
    except ValueError:
        return False


def translate_wechat_article(identifier, language):
    """Start one background translation from the archived Chinese source."""
    language = str(language or "").lower()
    if language not in PUBLIC_WECHAT_LANGUAGES:
        raise ValueError("Only English, Spanish, German and French are available here.")
    archive = load_blob_json("byelingua/articles.json", {"updated_at":"","articles":[]})
    articles = archive.get("articles", [])
    item = next((article for article in articles if str(article.get("id")) == str(identifier)), None)
    if not is_wechat_article(item):
        raise ValueError("WeChat article not found.")
    translations = dict(item.get("translations") or item.get("contents") or {})
    titles = dict(item.get("translated_titles") or item.get("titles") or {})
    if translations.get(language) and titles.get(language):
        return {"article":item,"reused":True,"status":"completed"}
    jobs = dict(item.get("translation_jobs") or {})
    existing_job = jobs.get(language) or {}
    if existing_job.get("response_id") and existing_job.get("status") in {"queued","in_progress"}:
        return {"article":item,"reused":True,"status":existing_job["status"]}
    chinese = str(translations.get("zh") or item.get("result") or "").strip()
    chinese_title = str(titles.get("zh") or item.get("original_title") or item.get("title") or "").strip()
    if not chinese or not chinese_title:
        raise ValueError("This article has no archived Chinese source to translate.")
    language_name = LANGUAGES[language]
    custom_instruction = str(item.get("translation_instruction") or "").strip()[:1000]
    extra = f"\nAdditional translation requirement: {custom_instruction}" if custom_instruction else ""
    prompt = f"""Translate the following Chinese article completely into {language_name}. Preserve meaning, paragraphs, names, titles and factual detail. Also write a concise 120-180 word summary in {language_name}.{extra}
Return valid JSON only, without Markdown:
{{"title":"translated title","summary":"concise summary","content":"complete translated article"}}

Chinese title: {chinese_title}
Chinese article:
{chinese}"""
    response = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), timeout=10.0, max_retries=0).responses.create(model=MODEL, input=prompt, background=True)
    now = datetime.now(timezone.utc).isoformat()
    # Even a very fast completed response is finalized through the polling path,
    # which owns JSON validation and persistence.
    client_status = "in_progress" if response.status == "completed" else response.status
    jobs[language] = {"response_id":response.id,"status":client_status,"created_at":now}
    item.update({"translation_jobs":jobs,"processed_at":now})
    save_blob_json("byelingua/articles.json", {"updated_at":now,"articles":articles})
    return {"article":item,"reused":False,"status":client_status}


def poll_wechat_translation(identifier, language):
    """Poll a background response and persist its result once completed."""
    language = str(language or "").lower()
    if language not in PUBLIC_WECHAT_LANGUAGES:
        raise ValueError("Only English, Spanish, German and French are available here.")
    archive = load_blob_json("byelingua/articles.json", {"updated_at":"","articles":[]})
    articles = archive.get("articles", [])
    item = next((article for article in articles if str(article.get("id")) == str(identifier)), None)
    if not is_wechat_article(item):
        raise ValueError("WeChat article not found.")
    translations = dict(item.get("translations") or item.get("contents") or {})
    titles = dict(item.get("translated_titles") or item.get("titles") or {})
    if translations.get(language) and titles.get(language):
        return {"article":item,"status":"completed"}
    jobs = dict(item.get("translation_jobs") or {})
    job = dict(jobs.get(language) or {})
    response_id = str(job.get("response_id") or "")
    if not response_id:
        raise ValueError("Translation job not found. Start the translation again.")
    response = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), timeout=10.0, max_retries=0).responses.retrieve(response_id)
    status = str(response.status)
    job["status"] = status
    jobs[language] = job
    item["translation_jobs"] = jobs
    if status in {"queued","in_progress"}:
        return {"article":item,"status":status}
    if status != "completed":
        job["error"] = "The translation did not complete. Please try again."
        now = datetime.now(timezone.utc).isoformat()
        save_blob_json("byelingua/articles.json", {"updated_at":now,"articles":articles})
        return {"article":item,"status":status,"error":job["error"]}
    try:
        payload = json.loads(response.output_text.removeprefix("```json").removesuffix("```").strip())
        translated_title = str(payload.get("title") or "").strip()
        summary = str(payload.get("summary") or "").strip()
        content = str(payload.get("content") or "").strip()
    except (json.JSONDecodeError, AttributeError):
        translated_title = summary = content = ""
    if not translated_title or not summary or not content:
        job.update({"status":"failed","error":"The completed translation returned an incomplete result. Please try again."})
        now = datetime.now(timezone.utc).isoformat()
        save_blob_json("byelingua/articles.json", {"updated_at":now,"articles":articles})
        return {"article":item,"status":"failed","error":job["error"]}
    translations[language] = content
    titles[language] = translated_title
    summaries = dict(item.get("summaries") or {})
    summaries[language] = summary
    now = datetime.now(timezone.utc).isoformat()
    job["completed_at"] = now
    item.update({"translations":translations,"contents":dict(translations),"translated_titles":titles,"titles":dict(titles),"summaries":summaries,"translation_jobs":jobs,"processed_at":now})
    save_blob_json("byelingua/articles.json", {"updated_at":now,"articles":articles})
    return {"article":item,"status":"completed"}


def update_article_metadata(identifier, data):
    """Persist editable article metadata without retranslating content."""
    archive = load_blob_json("byelingua/articles.json", {"updated_at":"","articles":[]})
    articles = archive.get("articles", [])
    item = next((article for article in articles if str(article.get("id")) == str(identifier)), None)
    if not item:
        raise ValueError("Article not found.")
    if "author_label" in data or "author" in data:
        author = str(data.get("author_label", data.get("author", "")) or "").strip()[:120]
        item["author_label"] = author
        item["source"] = author
    if "category" in data:
        item["category"] = str(data.get("category") or "").strip()[:80]
    if "published" in data:
        raw_published = str(data.get("published") or "").strip()
        parsed = parse_date(raw_published)
        if raw_published and not parsed:
            raise ValueError("Invalid publication date.")
        item["published"] = parsed
    now = datetime.now(timezone.utc).isoformat()
    item["metadata_updated_at"] = now
    save_blob_json("byelingua/articles.json", {"updated_at":now,"articles":articles})
    return {"article":item,"updated":True}


def delete_article(identifier, allow_resync=False):
    archive = load_blob_json(
        "byelingua/articles.json",
        {"updated_at": "", "articles": []},
    )

    removed = next(
        (
            item
            for item in archive.get("articles", [])
            if item.get("id") == identifier
        ),
        None,
    )

    if not removed:
        raise ValueError("找不到要删除的文章。")

    articles = [
        item
        for item in archive.get("articles", [])
        if item.get("id") != identifier
    ]

    now = datetime.now(timezone.utc).isoformat()

    save_blob_json(
        "byelingua/articles.json",
        {
            "updated_at": now,
            "articles": articles,
        },
    )

    if allow_resync and removed.get("url"):
        removed_url = canonical_url(removed["url"])
        remove_seen_url(removed_url)

    return {
        "deleted": identifier,
        "items": len(articles),
        "resync_allowed": bool(allow_resync),
    }

def retranslate_article(identifier):
    archive = load_blob_json("byelingua/articles.json", {"updated_at":"","articles":[]})
    articles = archive.get("articles", [])
    item = next((article for article in articles if article.get("id") == identifier), None)
    if not item:
        raise ValueError("找不到要重新翻译的文章。")
    original_title = item.get("original_title") or item.get("title") or ""
    try:
        if item.get("kind") == "wechat":
            # Retranslation uses the archived Chinese source and never re-fetches WeChat.
            source_text = item.get("translations", {}).get("zh") or item.get("contents", {}).get("zh") or item.get("result", "")
            if not str(source_text).strip():
                raise ValueError("这篇微信文章没有已保存的中文原文，无法重新翻译。")
            bilingual = translate_bilingual_article(source_text, original_title, "translate")
        else:
            source_text, _ = extract_article(item.get("url", ""))
            bilingual = translate_bilingual_article(source_text, original_title, item.get("mode", "translate"))
        titles, contents = bilingual["titles"], bilingual["contents"]
    except (ValueError, requests.RequestException):
        chinese_content = item.get("contents", {}).get("zh") or item.get("result", "")
        if not chinese_content.strip():
            raise ValueError("无法重新读取原文，且没有可用的中文正文。")
        backfill = translate_backfill_article(chinese_content, original_title)
        titles, contents = backfill["titles"], {"zh":chinese_content,"en":backfill["content_en"]}
    item.update({"original_title":original_title,"title":titles["zh"],"result":contents["zh"],"titles":titles,"contents":contents,"language":"bilingual","processed_at":datetime.now(timezone.utc).isoformat()})
    if item.get("kind") == "wechat":
        item["translated_titles"], item["translations"] = dict(titles), dict(contents)
    now = datetime.now(timezone.utc).isoformat()
    save_blob_json("byelingua/articles.json", {"updated_at":now,"articles":articles})
    return {"article":item,"retranslated":True}


def entry_text(entry):
    content = entry.get("content") or []
    raw = content[0].get("value", "") if content and isinstance(content, list) else entry.get("summary") or entry.get("description") or ""
    return BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)[:12000]


def collect_rss(subscription, seen, limit):
    feed, items = feedparser.parse(fetch(subscription["feed_url"]).content), []
    for entry in feed.entries:
        link = canonical_url(subscription["url"], entry.get("link", ""))
        if link in seen: continue
        items.append({"title":entry.get("title",link),"url":link,"published":parse_date(entry.get("published") or entry.get("updated") or ""),"feed_text":entry_text(entry)})
        if len(items) >= limit: break
    return items


def collect_website(subscription, seen, limit):
    soup = BeautifulSoup(fetch(subscription["url"]).content, "html.parser")
    host, items, local = urlsplit(subscription["url"]).hostname, [], set()
    for link in soup.select("article h1 a,article h2 a,article h3 a,h1 a,h2 a,h3 a,.post-title a,.entry-title a,a:has(h2)"):
        title, href = " ".join(link.get_text(" ", strip=True).split()), link.get("href")
        if not href or len(title) < 12: continue
        try: url = canonical_url(subscription["url"], href)
        except ValueError: continue
        if urlsplit(url).hostname != host or url in seen or url in local: continue
        if any(x in urlsplit(url).path.lower() for x in ("/author/","/tag/","/category/","/page/")): continue
        local.add(url); items.append({"title":title,"url":url,"published":"","feed_text":""})
        if len(items) >= limit: break
    return items


def collect_new_articles(subscription, seen, limit=2):
    return collect_website(subscription, seen, limit) if subscription.get("source_type") == "website" else collect_rss(subscription, seen, limit)


def run_daily_digest(source_id=None, subscription_override=None):
    config = load_config()

    seen = {
        canonical_url(url)
        for url in load_seen_urls()
    }

    archive = load_blob_json(
        "byelingua/articles.json",
        {"updated_at": "", "articles": []},
    )

    state = load_app_state(
        "update_state",
        {"next_source": 0},
    )

    results, errors = [], []

    subscriptions = [
        item
        for item in config["subscriptions"]
        if item.get("enabled", True)
    ]

    if subscription_override is not None:
        subscriptions = [subscription_override]
        source_id = subscription_override["id"]

    elif source_id:
        subscriptions = [
            item
            for item in subscriptions
            if item.get("id") == source_id
        ]

        if not subscriptions:
            raise ValueError(
                f"Unknown or disabled source: {source_id}"
            )

    start = (
        0
        if source_id
        else int(state.get("next_source", 0))
        % max(len(subscriptions), 1)
    )

    ordered = subscriptions[start:] + subscriptions[:start]

    for offset, subscription in enumerate(ordered):
        try:
            candidates = collect_new_articles(
                subscription,
                seen,
                1,
            )

        except Exception as error:
            errors.append(
                f"{subscription['name']}: {error}"
            )
            continue

        for article in candidates:
            try:
                try:
                    text, page_date = extract_article(article["url"])
                    article["published"] = (
                        article["published"] or page_date
                    )

                except Exception:
                    text = article.get("feed_text", "")

                    if len(text) < 200:
                        raise

                original_title = article["title"]

                bilingual = translate_bilingual_article(
                    text,
                    original_title,
                    subscription["mode"],
                )

                item = {
                    **article,
                    "title": bilingual["titles"]["zh"],
                    "result": bilingual["contents"]["zh"],
                    "titles": bilingual["titles"],
                    "contents": bilingual["contents"],
                    "original_title": original_title,
                    "id": hashlib.sha256(
                        article["url"].encode()
                    ).hexdigest()[:16],
                    "kind": "subscription",
                    "source": subscription["name"],
                    "country": subscription["country"],
                    "language": "bilingual",
                    "mode": subscription["mode"],
                    "processed_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                }

                item.pop("feed_text", None)

                results.append(item)
                seen.add(article["url"])

            except Exception as error:
                errors.append(
                    f"{article['title']}: {error}"
                )

        if results:
            if not source_id:
                state["next_source"] = (
                    start + offset + 1
                ) % max(len(subscriptions), 1)

            break

    urls = {
        item["url"]
        for item in results
    }

    merged = results + [
        item
        for item in archive.get("articles", [])
        if item.get("url") not in urls
    ]

    now = datetime.now(timezone.utc).isoformat()

    save_blob_json(
        "byelingua/articles.json",
        {
            "updated_at": now,
            "articles": merged[:MAX_ARTICLES],
        },
    )

    add_seen_urls(list(seen)[:2000])

    save_app_state(
        "update_state",
        state,
    )

    return {
        "processed": len(results),
        "items": len(merged[:MAX_ARTICLES]),
        "errors": errors[:10],
        "batch_limit": 1,
        "source": source_id or "round-robin",
    }


def public_subscriptions(config):
    """Return the safe fields needed to show enabled public sources."""
    fields = ("id", "name", "country", "url", "source_type", "mode")
    return [
        {field: item.get(field, "") for field in fields}
        for item in config.get("subscriptions", [])
        if item.get("enabled", True)
    ]


def save_public_subscription(data, old_id=""):
    """Save a public source and immediately try to publish its first article."""
    config = load_config()
    subscription = validate_subscription(data)
    config["subscriptions"] = [
        item for item in config["subscriptions"]
        if item.get("id") not in {subscription["id"], str(old_id or "")}
    ] + [subscription]
    save_config(config)
    try:
        # Use the just-saved source directly so this request is not sensitive to
        # a concurrent configuration read.
        update = run_daily_digest(subscription_override=subscription)
    except Exception as error:
        update = {"processed": 0, "items": 0, "errors": [str(error)], "source": subscription["id"]}
    return {"subscription": public_subscriptions({"subscriptions": [subscription]})[0], "update": update}


def set_public_subscription_enabled(identifier, enabled):
    config = load_config()
    subscription = next((item for item in config.get("subscriptions", []) if item.get("id") == identifier), None)
    if subscription is None:
        raise ValueError("找不到这个公共订阅。")
    subscription["enabled"] = bool(enabled)
    save_config(config)
    return {"id": identifier, "enabled": subscription["enabled"]}


def public_payload():
    config = load_config()
    articles = load_public_articles()

    return {
        "target_language": config.get("target_language", "zh"),
        "countries": COUNTRIES,
        "subscriptions": public_subscriptions(config),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "articles": articles,
    }


def supabase_settings():
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    publishable = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
    service = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not publishable or not service:
        raise RuntimeError("Supabase 环境变量尚未完整设置。")
    return url, publishable, service


def supabase_service(method, path, *, params=None, payload=None, prefer="return=representation"):
    url, _, service = supabase_settings()
    headers = {"apikey":service,"Content-Type":"application/json","Prefer":prefer,"User-Agent":"Byelingua-Server/3.0"}
    if not service.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {service}"
    response = SESSION.request(method, f"{url}{path}", params=params, json=payload, headers=headers, timeout=30)
    if not response.ok:
        raise ValueError(response.json().get("message") or response.text or "Supabase 请求失败。")
    return response.json() if response.content else None


def authenticated_user(headers):
    value = headers.get("Authorization", "")
    if not value.startswith("Bearer "):
        raise PermissionError("请先登录账户。")
    url, publishable, _ = supabase_settings()
    response = SESSION.get(f"{url}/auth/v1/user", headers={"apikey":publishable,"Authorization":value}, timeout=20)
    if not response.ok:
        raise PermissionError("登录已过期，请重新登录。")
    user = response.json()
    if not user.get("id"):
        raise PermissionError("无法识别登录用户。")
    return user


MANUAL_BRIEF_EVENT_TYPE = "manual_news_brief"


def manual_brief_status(user_id):
    try:
        rows = supabase_service(
            "GET", "/rest/v1/usage_events",
            params={
                "user_id": f"eq.{user_id}",
                "event_type": f"eq.{MANUAL_BRIEF_EVENT_TYPE}",
                "select": "created_at",
                "order": "created_at.desc",
                "limit": "1",
            },
        ) or []
    except Exception:
        rows = []
    last = rows[0].get("created_at") if rows else None
    if not last:
        return {"last_success_at": None, "next_available_at": None, "rate_limited": False}
    try:
        parsed = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        next_available = parsed + timedelta(hours=24)
        limited = datetime.now(timezone.utc) < next_available
        return {"last_success_at": parsed.astimezone(timezone.utc).isoformat(), "next_available_at": next_available.astimezone(timezone.utc).isoformat(), "rate_limited": limited}
    except ValueError:
        return {"last_success_at": last, "next_available_at": None, "rate_limited": False}


class ManualBriefRateLimitError(ValueError):
    def __init__(self, status):
        self.status = status
        super().__init__("Manual Brief is available once every 24 hours.")


def personal_payload(user_id):
    profile = supabase_service("GET", "/rest/v1/profiles", params={"id":f"eq.{user_id}","select":"*"})
    profile = profile[0] if profile else {}
    subscriptions = supabase_service("GET", "/rest/v1/user_subscriptions", params={"user_id":f"eq.{user_id}","select":"*","order":"created_at.desc"})
    article_params = {"user_id":f"eq.{user_id}","select":"*","order":"processed_at.desc","limit":"200"}
    if profile.get("preferred_language") in LANGUAGES:
        article_params["language"] = f"eq.{profile['preferred_language']}"
    articles = supabase_service("GET", "/rest/v1/user_articles", params=article_params)
    try:
        general_subscriptions = supabase_service("GET", "/rest/v1/user_general_subscriptions", params={"user_id":f"eq.{user_id}","select":"*"}) or []
    except Exception:
        general_subscriptions = []
    return {"profile":profile,"subscriptions":subscriptions or [],"general_subscriptions":general_subscriptions,"articles":articles or [],"manual_brief":manual_brief_status(user_id)}


def set_general_subscription(user_id, source, enabled):
    source_id = str(source.get("id") or source.get("feed_url") or "").strip()
    if not source_id:
        raise ValueError("无效的公共新闻来源。")
    record = {"user_id":user_id,"source_id":source_id,"feed_url":source.get("feed_url"),"name":source.get("name"),"enabled":bool(enabled)}
    rows = supabase_service("POST", "/rest/v1/user_general_subscriptions", params={"on_conflict":"user_id,source_id"}, payload=record, prefer="resolution=merge-duplicates,return=representation") or []
    return personal_payload(user_id)


def effective_subscriptions(personal):
    personal_rows = [row for row in personal.get("subscriptions", []) if row.get("enabled", True)]
    general_rows = [row for row in personal.get("general_subscriptions", []) if row.get("enabled", False)]
    by_feed = {(row.get("feed_url") or row.get("id")): row for row in personal_rows}
    for row in general_rows:
        source = next((item for item in available_news_sources() if item.get("id") == row.get("source_id") or item.get("feed_url") == row.get("feed_url")), None)
        if source and source.get("feed_url") not in by_feed:
            by_feed[source["feed_url"]] = {**source, "enabled":True}
    return list(by_feed.values())


def save_personal_subscription(user_id, data):
    personal = personal_payload(user_id)
    profile = personal["profile"]
    if profile.get("status") != "active":
        raise PermissionError("账户当前不可添加订阅。")
    sub = validate_subscription(data)
    existing = next((item for item in personal["subscriptions"] if item.get("feed_url") == sub["feed_url"]), None)
    if not existing and len(personal["subscriptions"]) >= int(profile.get("max_subscriptions", 3)):
        raise ValueError(f"试运行账户最多添加 {profile.get('max_subscriptions', 3)} 个网站。")
    record = {key:sub[key] for key in ("name","url","feed_url","country","source_type","language","mode","enabled")}
    record["user_id"] = user_id
    if existing:
        rows = supabase_service("PATCH", "/rest/v1/user_subscriptions", params={"id":f"eq.{existing['id']}"}, payload=record)
    else:
        rows = supabase_service("POST", "/rest/v1/user_subscriptions", payload=record)
    return personal_payload(user_id)


def delete_personal_subscription(user_id, identifier):
    supabase_service("DELETE", "/rest/v1/user_subscriptions", params={"id":f"eq.{identifier}","user_id":f"eq.{user_id}"})
    return personal_payload(user_id)


def set_personal_subscription_enabled(user_id, identifier, enabled):
    rows = supabase_service(
        "PATCH", "/rest/v1/user_subscriptions",
        params={"id": f"eq.{identifier}", "user_id": f"eq.{user_id}"},
        payload={"enabled": bool(enabled), "updated_at": datetime.now(timezone.utc).isoformat()},
    ) or []
    if not rows:
        raise ValueError("找不到该新闻来源。")
    return personal_payload(user_id)


def available_news_sources():
    result = []
    for source in load_config().get("subscriptions", []):
        if not source.get("feed_url"):
            continue
        custom = bool(source.get("custom_eligible", str(source.get("source_type") or "").lower() == "website"))
        result.append({**{key: source.get(key) for key in ("id","name","url","feed_url","country","source_type","language","mode")}, "custom_eligible": custom})
    return result


def list_my_invite_codes(user_id):
    rows = supabase_service("GET", "/rest/v1/invite_codes", params={"created_by":f"eq.{user_id}","select":"id,code,max_uses,used_count,status,created_at","order":"created_at.desc"}) or []
    return {"codes":rows}


def save_personal_language(user_id, language):
    language = str(language or "").lower()
    if language not in LANGUAGES:
        raise ValueError("不支持所选语言。")
    supabase_service("PATCH", "/rest/v1/profiles", params={"id":f"eq.{user_id}"}, payload={"preferred_language":language,"updated_at":datetime.now(timezone.utc).isoformat()})
    supabase_service("PATCH", "/rest/v1/user_subscriptions", params={"user_id":f"eq.{user_id}"}, payload={"language":language,"updated_at":datetime.now(timezone.utc).isoformat()})
    return personal_payload(user_id)


def _profile_digest_enabled(profile):
    """Read the canonical opt-in first, with a legacy-column fallback."""
    if "email_digest_enabled" in profile and profile.get("email_digest_enabled") is not None:
        return bool(profile.get("email_digest_enabled"))
    if "email_subscription_enabled" in profile and profile.get("email_subscription_enabled") is not None:
        return bool(profile.get("email_subscription_enabled"))
    return False


def save_email_digest_preference(user_id, enabled):
    """Persist the daily-news digest opt-in without touching schedule email."""
    if not isinstance(enabled, bool):
        raise ValueError("Email digest preference must be true or false.")
    payload = {"email_digest_enabled": enabled, "updated_at": datetime.now(timezone.utc).isoformat()}
    try:
        supabase_service("PATCH", "/rest/v1/profiles", params={"id": f"eq.{user_id}"}, payload=payload)
    except Exception:
        # Compatibility while the canonical column migration is pending.
        supabase_service(
            "PATCH", "/rest/v1/profiles",
            params={"id": f"eq.{user_id}"},
            payload={"email_subscription_enabled": enabled, "updated_at": payload["updated_at"]},
        )
    return personal_payload(user_id)


def save_email_subscription(user_id, enabled):
    """Backward-compatible action name for the daily digest preference."""
    return save_email_digest_preference(user_id, enabled)


def _run_personal_digest_legacy(user_id):
    personal = personal_payload(user_id)
    profile, subscriptions = personal["profile"], effective_subscriptions(personal)
    today = datetime.now(timezone.utc).date().isoformat()
    usage = supabase_service("GET", "/rest/v1/usage_events", params={"user_id":f"eq.{user_id}","event_type":"eq.digest","created_at":f"gte.{today}T00:00:00Z","select":"id"})
    if len(usage or []) >= int(profile.get("daily_update_limit", 1)):
        raise ValueError("今天的更新次数已经用完，请明天再试。")
    seen = {item.get("canonical_url") for item in personal["articles"]}
    processed, errors, characters = 0, [], 0
    for subscription in subscriptions:
        if not subscription.get("enabled", True):
            continue
        try:
            candidates = collect_new_articles(subscription, seen, 1)
        except Exception as error:
            errors.append(f"{subscription['name']}: {error}"); continue
        for article in candidates:
            try:
                try:
                    text, page_date = extract_article(article["url"]); article["published"] = article.get("published") or page_date
                except Exception:
                    text = article.get("feed_text", "")
                    if len(text) < 200: raise
                characters += len(text)
                if int(profile.get("used_characters", 0)) + characters > int(profile.get("monthly_character_limit", 100000)):
                    raise ValueError("本月翻译字符额度已经用完。")
                translated = translate_article(text, subscription["language"], subscription["mode"], article["title"])
                record = {"user_id":user_id,"subscription_id":subscription["id"],"canonical_url":article["url"],"title":translated["title"],"source":subscription["name"],"country":subscription["country"],"published_at":article.get("published") or None,"language":subscription["language"],"mode":subscription["mode"],"result":translated["content"]}
                supabase_service("POST", "/rest/v1/user_articles", params={"on_conflict":"user_id,canonical_url,language"}, payload=record, prefer="resolution=merge-duplicates,return=representation")
                processed += 1; seen.add(article["url"])
            except Exception as error:
                errors.append(f"{article.get('title','文章')}: {error}")
        if processed:
            break
    now = datetime.now(timezone.utc).isoformat()
    supabase_service("POST", "/rest/v1/usage_events", payload={"user_id":user_id,"event_type":"digest","characters":characters})
    if characters:
        supabase_service("PATCH", "/rest/v1/profiles", params={"id":f"eq.{user_id}"}, payload={"used_characters":int(profile.get("used_characters",0))+characters,"updated_at":now})
    return {"processed":processed,"errors":errors[:10],"data":personal_payload(user_id)}


def run_personal_digest(user_id, automated=False, article_limit=3, enforce_daily_limit=True):
    """Process up to three personal sources using the account's saved language."""
    personal = personal_payload(user_id)
    profile, subscriptions = personal["profile"], effective_subscriptions(personal)
    if profile.get("status") != "active":
        raise PermissionError("This subscription account is not active.")

    paris_midnight = datetime.now(PARIS_TIMEZONE).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).astimezone(timezone.utc).isoformat()
    if not automated and enforce_daily_limit:
        usage = supabase_service(
            "GET",
            "/rest/v1/usage_events",
            params={
                "user_id":f"eq.{user_id}",
                "event_type":"eq.digest",
                "created_at":f"gte.{paris_midnight}",
                "select":"id",
            },
        )
        if len(usage or []) >= int(profile.get("daily_update_limit", 1)):
            raise ValueError(
                "You have already used today's manual update. "
                "Automatic daily updates will continue normally."
            )

    language = profile.get("preferred_language", "zh")
    if language not in LANGUAGES:
        language = "zh"
    seen = {item.get("canonical_url") for item in personal["articles"]}
    processed, errors, characters, new_articles = 0, [], 0, []

    for subscription in subscriptions:
        if processed >= article_limit:
            break
        if not subscription.get("enabled", True):
            continue
        try:
            candidates = collect_new_articles(subscription, seen, 1)
        except Exception as error:
            errors.append(f"{subscription['name']}: {error}")
            continue
        for article in candidates:
            if processed >= article_limit:
                break
            try:
                try:
                    text, page_date = extract_article(article["url"])
                    article["published"] = article.get("published") or page_date
                except Exception:
                    text = article.get("feed_text", "")
                    if len(text) < 200:
                        raise
                characters += len(text)
                if int(profile.get("used_characters", 0)) + characters > int(profile.get("monthly_character_limit", 100000)):
                    raise ValueError("The monthly translation character limit has been reached.")
                translated = translate_article(text, language, subscription["mode"], article["title"])
                record = {
                    "user_id":user_id,
                    "subscription_id":subscription["id"],
                    "canonical_url":article["url"],
                    "title":translated["title"],
                    "source":subscription["name"],
                    "country":subscription["country"],
                    "published_at":article.get("published") or None,
                    "language":language,
                    "mode":subscription["mode"],
                    "result":translated["content"],
                }
                inserted = supabase_service(
                    "POST",
                    "/rest/v1/user_articles",
                    params={"on_conflict":"user_id,canonical_url,language"},
                    payload=record,
                    prefer="resolution=ignore-duplicates,return=representation",
                ) or []
                if not inserted:
                    seen.add(article["url"])
                    continue
                new_articles.append(inserted[0])
                processed += 1
                seen.add(article["url"])
            except Exception as error:
                errors.append(f"{article.get('title', 'Article')}: {error}")

    now = datetime.now(timezone.utc).isoformat()
    supabase_service(
        "POST",
        "/rest/v1/usage_events",
        payload={
            "user_id":user_id,
            "event_type":"translation" if automated else "digest",
            "characters":characters,
        },
    )
    if characters:
        supabase_service(
            "PATCH",
            "/rest/v1/profiles",
            params={"id":f"eq.{user_id}"},
            payload={
                "used_characters":int(profile.get("used_characters", 0)) + characters,
                "updated_at":now,
            },
        )
    return {"processed":processed,"new_articles":new_articles,"errors":errors[:10],"data":personal_payload(user_id)}


EMAIL_DIGEST_COPY = {
    "zh": {"subject":"Byelingua 每日多语言摘要", "intro":"以下是今天为你新生成的文章。", "source":"来源", "published":"发布时间", "unknown":"未知", "original":"查看原文", "home":"打开 Byelingua"},
    "en": {"subject":"Your daily Byelingua digest", "intro":"Here are the new articles generated for you today.", "source":"Source", "published":"Published", "unknown":"Unknown", "original":"View original", "home":"Open Byelingua"},
    "fr": {"subject":"Votre résumé quotidien Byelingua", "intro":"Voici les nouveaux articles générés pour vous aujourd’hui.", "source":"Source", "published":"Publication", "unknown":"Inconnue", "original":"Voir l’original", "home":"Ouvrir Byelingua"},
    "es": {"subject":"Tu resumen diario de Byelingua", "intro":"Estos son los nuevos artículos generados hoy para ti.", "source":"Fuente", "published":"Publicado", "unknown":"Desconocido", "original":"Ver original", "home":"Abrir Byelingua"},
    "de": {"subject":"Ihre tägliche Byelingua-Zusammenfassung", "intro":"Hier sind die heute neu für Sie erstellten Artikel.", "source":"Quelle", "published":"Veröffentlicht", "unknown":"Unbekannt", "original":"Original ansehen", "home":"Byelingua öffnen"},
    "it": {"subject":"Il tuo riepilogo quotidiano del Byelingua", "intro":"Ecco i nuovi articoli generati oggi per te.", "source":"Fonte", "published":"Pubblicato", "unknown":"Sconosciuto", "original":"Vedi originale", "home":"Apri Byelingua"},
    "pt": {"subject":"O seu resumo diário do Byelingua", "intro":"Estes são os novos artigos gerados hoje para si.", "source":"Fonte", "published":"Publicado", "unknown":"Desconhecido", "original":"Ver original", "home":"Abrir Byelingua"},
    "ja": {"subject":"Byelingua デイリーダイジェスト", "intro":"本日新しく生成された記事です。", "source":"配信元", "published":"公開日", "unknown":"不明", "original":"原文を見る", "home":"Byelingua を開く"},
}


def _email_article_excerpt(value, limit=600):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else f"{text[:limit].rstrip()}…"


def _safe_email_url(value, fallback="#"):
    value = str(value or "").strip()
    return value if urlsplit(value).scheme.lower() in {"http", "https"} else fallback


def build_email_digest(profile, articles, digest_date=None):
    language = profile.get("preferred_language", "zh")
    if language not in EMAIL_DIGEST_COPY:
        language = "zh"
    copy = EMAIL_DIGEST_COPY[language]
    digest_date = digest_date or datetime.now(PARIS_TIMEZONE).date().isoformat()
    home_url = _safe_email_url(os.environ.get("PUBLIC_APP_URL", "https://www.bye-lingua.site").rstrip("/"), "https://www.bye-lingua.site")
    subject = f"{copy['subject']} · {digest_date}"
    text_parts = [copy["intro"], ""]
    html_articles = []
    for article in list(articles or [])[:3]:
        title = str(article.get("title") or "")
        source = str(article.get("source") or "")
        published = str(article.get("published_at") or "")[:10] or copy["unknown"]
        excerpt = _email_article_excerpt(article.get("result"))
        original_url = _safe_email_url(article.get("canonical_url"))
        text_parts.extend([title, f"{copy['source']}: {source}", f"{copy['published']}: {published}", excerpt, f"{copy['original']}: {original_url}", ""])
        meta = f"{copy['source']}: {source} · {copy['published']}: {published}"
        html_articles.append(
            '<article style="padding:20px 0;border-top:1px solid #d7d7ce">'
            f'<h2 style="margin:0 0 8px;font:600 22px/1.35 Georgia,serif;color:#214d3a">{escape(title)}</h2>'
            f'<p style="margin:0 0 12px;color:#68716b;font-size:13px">{escape(meta)}</p>'
            f'<p style="margin:0 0 12px;color:#26332c;line-height:1.7">{escape(excerpt)}</p>'
            f'<a href="{escape(original_url, quote=True)}" style="color:#214d3a;font-weight:700">{escape(copy["original"])}</a></article>'
        )
    text_parts.append(f"{copy['home']}: {home_url}")
    html = '<!doctype html><html><body style="margin:0;background:#f5f2e9;color:#17201b"><main style="max-width:680px;margin:auto;padding:32px 22px;font-family:Arial,sans-serif">' \
        f'<div style="font:500 38px/1 Georgia,serif;color:#214d3a">BYELINGUA</div><p style="margin:14px 0 24px;color:#39423d">{escape(copy["intro"])}</p>' \
        + "".join(html_articles) + f'<p style="margin:24px 0"><a href="{escape(home_url, quote=True)}" style="display:inline-block;padding:10px 15px;background:#214d3a;color:#fff;text-decoration:none">{escape(copy["home"])}</a></p></main></body></html>'
    return {"subject":subject,"text":"\n".join(text_parts),"html":html,"language":language}


def send_resend_email(recipient, subject, text, html):
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    sender = os.environ.get("EMAIL_FROM", "").strip()
    if not api_key or not sender:
        missing = [name for name, value in (("RESEND_API_KEY", api_key), ("EMAIL_FROM", sender)) if not value]
        raise RuntimeError(f"Email digest configuration missing: {', '.join(missing)}.")
    if not recipient:
        raise ValueError("Email digest recipient is missing from the profile.")
    response = SESSION.post(
        "https://api.resend.com/emails",
        headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json","User-Agent":"Byelingua-Server/3.0"},
        json={"from":sender,"to":[recipient],"subject":subject,"text":text,"html":html},
        timeout=20,
    )
    if not response.ok:
        try:
            detail = response.json().get("message") or response.text
        except Exception:
            detail = response.text
        raise RuntimeError(f"Resend request failed ({response.status_code}): {str(detail)[:500]}")
    provider_id = response.json().get("id")
    if not provider_id:
        raise RuntimeError("Resend response did not include a message id.")
    return provider_id


def _safe_delivery_error(error):
    message = str(error).replace(os.environ.get("RESEND_API_KEY", ""), "[redacted]")
    return message[:1000]


def deliver_personal_digest(profile, articles, digest_date=None):
    digest_date = digest_date or datetime.now(PARIS_TIMEZONE).date().isoformat()
    articles = list(articles or [])[:3]
    enabled = _profile_digest_enabled(profile)
    if not enabled or not articles:
        return {"status":"skipped","reason":"disabled" if not enabled else "no_new_articles"}
    article_ids = [str(article.get("id")) for article in articles if article.get("id")]
    if not article_ids:
        return {"status":"skipped","reason":"no_persisted_articles"}
    reserved = supabase_service(
        "POST", "/rest/v1/email_digest_deliveries",
        params={"on_conflict":"user_id,digest_date"},
        payload={"user_id":profile["id"],"digest_date":digest_date,"status":"pending","article_ids":article_ids},
        prefer="resolution=ignore-duplicates,return=representation",
    ) or []
    if not reserved:
        return {"status":"skipped","reason":"already_delivered"}
    delivery = reserved[0]
    delivery_id = delivery.get("id")
    if not delivery_id:
        raise RuntimeError("Email digest delivery reservation did not return an id.")
    try:
        message = build_email_digest(profile, articles, digest_date)
        provider_id = send_resend_email(profile.get("email"), message["subject"], message["text"], message["html"])
        supabase_service("PATCH", "/rest/v1/email_digest_deliveries", params={"id":f"eq.{delivery_id}"}, payload={"status":"sent","provider_message_id":provider_id,"error":None,"sent_at":datetime.now(timezone.utc).isoformat()})
        return {"status":"sent","provider_message_id":provider_id,"article_ids":article_ids}
    except Exception as error:
        safe_error = _safe_delivery_error(error)
        supabase_service("PATCH", "/rest/v1/email_digest_deliveries", params={"id":f"eq.{delivery_id}"}, payload={"status":"failed","error":safe_error})
        return {"status":"failed","error":safe_error,"article_ids":article_ids}


def send_daily_digest(user_id, respect_subscription=True):
    resend_key = os.environ.get("RESEND_API_KEY", "").strip()
    email_from = os.environ.get("EMAIL_FROM", "").strip()
    if not resend_key or not email_from:
        raise RuntimeError("RESEND_API_KEY and EMAIL_FROM must be configured.")

    try:
        profiles = supabase_service(
            "GET", "/rest/v1/profiles",
            params={"id":f"eq.{user_id}","select":"email,preferred_language,email_digest_enabled,email_subscription_enabled"},
        ) or []
    except Exception:
        # Keep delivery compatible while either preference column is migrating.
        try:
            profiles = supabase_service(
                "GET", "/rest/v1/profiles",
                params={"id":f"eq.{user_id}","select":"email,preferred_language,email_digest_enabled"},
            ) or []
        except Exception:
            profiles = supabase_service(
                "GET", "/rest/v1/profiles",
                params={"id":f"eq.{user_id}","select":"email,preferred_language,email_subscription_enabled"},
            ) or []
    if not profiles or not str(profiles[0].get("email") or "").strip():
        raise ValueError(f"User {user_id} does not have a profile email.")

    profile = profiles[0]
    has_digest_flag = "email_digest_enabled" in profile or "email_subscription_enabled" in profile
    if respect_subscription and has_digest_flag and not _profile_digest_enabled(profile):
        return {"sent":False,"articles":0,"skipped":"email_disabled"}
    recipient = str(profile["email"]).strip()
    paris_now = datetime.now(PARIS_TIMEZONE)
    paris_midnight = paris_now.replace(
        hour=0, minute=0, second=0, microsecond=0
    ).astimezone(timezone.utc).isoformat()
    articles = supabase_service(
        "GET",
        "/rest/v1/user_articles",
        params={
            "user_id":f"eq.{user_id}",
            "processed_at":f"gte.{paris_midnight}",
            "select":"title,canonical_url,result,language,processed_at",
            "order":"processed_at.asc",
        },
    ) or []
    if not articles:
        return {"sent":False,"articles":0}

    article_html = []
    for article in articles:
        title = escape(str(article.get("title") or "Untitled"))
        url = escape(str(article.get("canonical_url") or "#"), quote=True)
        summary = escape(str(article.get("result") or "")).replace("\n", "<br>")
        language_code = str(article.get("language") or profile.get("preferred_language") or "")
        language = escape(LANGUAGES.get(language_code, language_code))
        article_html.append(
            f'<article style="margin:0 0 28px">'
            f'<h2 style="margin:0 0 8px;font-size:20px">'
            f'<a href="{url}" style="color:#214d3a">{title}</a></h2>'
            f'<div style="color:#68716b;font-size:13px">{language}</div>'
            f'<p style="line-height:1.7">{summary}</p>'
            f'<a href="{url}" style="color:#214d3a">Read original</a>'
            f'</article>'
        )

    digest_date = escape(paris_now.strftime("%Y-%m-%d"))
    html = (
        '<main style="max-width:680px;margin:auto;font-family:Arial,sans-serif;color:#17201b">'
        '<h1 style="font-family:Georgia,serif;color:#214d3a">BYELINGUA</h1>'
        f'<p style="color:#68716b">Daily Digest · {digest_date}</p>'
        + "".join(article_html)
        + '</main>'
    )
    response = SESSION.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization":f"Bearer {resend_key}",
            "Content-Type":"application/json",
            "User-Agent":"Byelingua-Server/3.0",
        },
        json={
            "from":email_from,
            "to":[recipient],
            "subject":"Byelingua Daily Digest",
            "html":html,
        },
        timeout=20,
    )
    if not response.ok:
        try:
            message = response.json().get("message")
        except ValueError:
            message = response.text
        raise ValueError(message or "Resend rejected the daily digest email.")
    payload = response.json()
    return {"sent":True,"articles":len(articles),"id":payload.get("id")}


def generate_brief_and_send(user_id):
    personal = personal_payload(user_id)
    if not effective_subscriptions(personal):
        raise ValueError("请先选择至少一个新闻来源。")
    status = manual_brief_status(user_id)
    if status.get("rate_limited"):
        raise ManualBriefRateLimitError(status)
    if not str(personal.get("profile", {}).get("email") or "").strip():
        raise ValueError("账户没有可用的登录邮箱。")
    result = run_personal_digest(user_id, automated=False, enforce_daily_limit=False)
    if result.get("errors") and not result.get("processed"):
        raise ValueError("Brief 生成失败：" + "; ".join(result["errors"][:2]))
    profile = dict(personal.get("profile") or {})
    profile.setdefault("id", user_id)
    delivery = deliver_personal_digest(profile, result.get("new_articles", []))
    if delivery.get("sent"):
        supabase_service("POST", "/rest/v1/usage_events", payload={"user_id":user_id,"event_type":MANUAL_BRIEF_EVENT_TYPE,"characters":0})
    return {"processed":result.get("processed",0),"errors":result.get("errors",[]),"delivery":delivery,"data":result.get("data"),"manual_brief":manual_brief_status(user_id)}


def paris_schedule_due(now=None):
    """Return True only during the 09:00 hour in Europe/Paris."""
    current = now or datetime.now(timezone.utc)
    return current.astimezone(PARIS_TIMEZONE).hour == 9


def run_scheduled_updates():
    """Update public news and all active subscribers once per Paris day."""
    paris_date = datetime.now(PARIS_TIMEZONE).date().isoformat()

    state = load_scheduled_state({"paris_date": ""})

    if state.get("paris_date") == paris_date:
        return {
            "already_run": True,
            "paris_date": paris_date,
            "public_processed": 0,
            "users": 0,
            "personal_processed": 0,
            "errors": [],
        }

    errors, public_processed, personal_processed = [], 0, 0

    for _ in range(3):
        result = run_daily_digest()
        public_processed += int(result.get("processed", 0))
        errors.extend(result.get("errors", []))

    try:
        profiles = supabase_service(
            "GET", "/rest/v1/profiles",
            params={"status": "eq.active", "select": "id,email,preferred_language,email_digest_enabled,email_subscription_enabled"},
        ) or []
    except Exception:
        try:
            profiles = supabase_service(
                "GET", "/rest/v1/profiles",
                params={"status": "eq.active", "select": "id,email,preferred_language,email_digest_enabled"},
            ) or []
        except Exception:
            profiles = supabase_service(
                "GET", "/rest/v1/profiles",
                params={"status": "eq.active", "select": "id,email,preferred_language,email_subscription_enabled"},
            ) or []

    completed_users = 0

    for profile in profiles:
        try:
            result = run_personal_digest(
                profile["id"],
                automated=True,
                article_limit=3,
            )
            personal_processed += int(result.get("processed", 0))
            errors.extend(result.get("errors", []))
            try:
                delivery = deliver_personal_digest(profile, result.get("new_articles", []), paris_date)
                if delivery.get("status") == "failed":
                    errors.append(f"User {profile.get('id', 'unknown')} email: {delivery.get('error', 'delivery failed')}")
            except Exception as error:
                errors.append(
                    f"User {profile.get('id', 'unknown')} email: {error}"
                )
            completed_users += 1

        except Exception as error:
            errors.append(
                f"User {profile.get('id', 'unknown')}: {error}"
            )

    save_scheduled_state({
        "paris_date": paris_date,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "already_run": False,
        "paris_date": paris_date,
        "public_processed": public_processed,
        "users": completed_users,
        "personal_processed": personal_processed,
        "errors": errors[:20],
    }

def register_with_invite(email, password, invite_code):
    email = str(email or "").strip().lower()
    password = str(password or "")
    invite_code = str(invite_code or "").strip().upper()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("请输入有效邮箱地址。")
    if not password:
        raise ValueError("请输入密码。")
    available = supabase_service(
        "GET",
        "/rest/v1/invite_codes",
        params={
            "code":f"eq.{invite_code}",
            "status":"eq.active",
            "select":"id,max_uses,used_count,child_prefix",
        },
    ) or []
    if not available or int(available[0].get("used_count", 0)) >= int(available[0].get("max_uses", 0)):
        raise ValueError("邀请码无效或已用完。")
    child_prefix = str(available[0].get("child_prefix") or "BYE").upper()
    if not re.fullmatch(r"[A-Z0-9]{2,10}", child_prefix):
        raise ValueError("邀请码来源前缀无效。")

    url, _, service = supabase_settings()
    headers = {
        "apikey":service,
        "Content-Type":"application/json",
        "User-Agent":"Byelingua-Server/3.0",
    }
    if not service.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {service}"
    response = SESSION.post(
        f"{url}/auth/v1/admin/users",
        json={"email":email,"password":password,"email_confirm":True,"user_metadata":{"invite_prefix":child_prefix}},
        headers=headers,
        timeout=20,
    )
    if not response.ok:
        try:
            message = response.json().get("message")
        except ValueError:
            message = response.text
        raise ValueError(message or "创建账户失败。")
    user = response.json()
    user_id = str(user.get("id") or "")
    if not user_id:
        raise ValueError("Supabase 未返回新用户 ID。")

    claimed = supabase_service(
        "POST",
        "/rest/v1/rpc/claim_invite_code",
        payload={"p_code":invite_code},
    )
    if claimed is not True:
        cleanup = SESSION.delete(
            f"{url}/auth/v1/admin/users/{user_id}",
            headers=headers,
            timeout=20,
        )
        if not cleanup.ok:
            raise RuntimeError("邀请码已被用完，且新账户清理失败。")
        raise ValueError("邀请码无效或已用完。")
    return {"status":"registered","user_id":user_id}


def generate_invite_code(user_id):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    profiles = supabase_service(
        "GET",
        "/rest/v1/profiles",
        params={"id":f"eq.{user_id}","select":"invite_prefix"},
    ) or []
    prefix = str(profiles[0].get("invite_prefix") or "BYE").upper() if profiles else "BYE"
    if not re.fullmatch(r"[A-Z0-9]{2,10}", prefix):
        raise ValueError("用户邀请码来源前缀无效。")
    code = prefix + "-" + "".join(secrets.choice(alphabet) for _ in range(6))
    rows = supabase_service(
        "POST",
        "/rest/v1/rpc/create_generated_invite",
        payload={"p_user_id":user_id,"p_code":code},
    ) or []
    if not rows:
        raise ValueError("生成邀请码失败。")
    return {
        "code":str(rows[0].get("code") or code),
        "remaining_credits":int(rows[0].get("remaining_credits", 0)),
    }


def _schedule_city(value):
    """Return a stable city label for the current venue catalogue."""
    text = str(value or "").lower()
    if "paris" in text:
        return "Paris"
    if "wien" in text or "vienna" in text:
        return "Vienna"
    if "berlin" in text:
        return "Berlin"
    return value or "Other"


def _event_city(event, venue_cities=None):
    """Return explicit city data, optionally enriched from the venue directory."""
    city = event.get("city") or event.get("location_city")
    if not city and venue_cities:
        city = venue_cities.get(str(event.get("venue") or "").strip().casefold())
    return str(city or "").strip()


CANONICAL_EVENT_TYPES = (
    "opera", "operetta", "ballet", "concert", "chamber_music",
    "recital", "children_family", "matinee", "other",
)
EVENT_TYPE_LABELS = {
    "opera": "Opera", "operetta": "Operetta", "ballet": "Ballet",
    "concert": "Concert", "chamber_music": "Chamber Music",
    "recital": "Recital", "children_family": "Children & Family",
    "matinee": "Matinee", "other": "Other",
}


def canonical_event_type(raw):
    value = str(raw or "").strip().lower()
    normalized = normalize_search_key(value)
    if any(token in normalized for token in ("opera", "operette", "music drama", "drame musical", "festival ring")):
        return "operetta" if "operette" in normalized else "opera"
    if any(token in normalized for token in ("concert", "recital", "recit", "symphony", "symphonie", "chamber")):
        return "recital" if "recital" in normalized or "recit" in normalized else "concert"
    if "ballet" in normalized or "dance" in normalized:
        return "ballet"
    if value in {"opera", "opera_en_concert", "children_s_opera"}:
        return "children_family" if value == "children_s_opera" else "opera"
    if "operetta" in value:
        return "operetta"
    if "ballet" in value:
        return "ballet"
    if value.startswith("recital"):
        return "recital"
    if value in {"musique_de_chambre", "musique_de_chambre_compositrices_d_hier", "chamber_music"} or "chamber" in value:
        return "chamber_music"
    if value == "concert" or value.startswith("concert_"):
        return "concert"
    if "matinee" in value or "matin" in value:
        return "matinee"
    return value if value in CANONICAL_EVENT_TYPES else "other"


def _programme_identity(value):
    """Normalize a work title for identity comparison, never for display."""
    value = re.sub(r"\s*\([^)]*(?:festival|ring)[^)]*\)\s*", " ", str(value or ""), flags=re.IGNORECASE)
    value = normalize_search_key(value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def normalized_programme(event, rows):
    """Return performed works while rejecting editorial/media extraction noise."""
    items = [
        {"order": row.get("order"), "title": (row.get("works") or {}).get("title"),
         "composer": (row.get("works") or {}).get("composer")}
        for row in (rows or []) if (row.get("works") or {}).get("title")
    ]
    if canonical_event_type(event.get("event_type")) not in {"opera", "operetta"}:
        return items
    event_key = _programme_identity(event.get("work_title") or event.get("title"))
    if not event_key:
        return []
    matches = [item for item in items if _programme_identity(item.get("title")) == event_key]
    if not matches:
        return []
    best = min(matches, key=lambda item: (len(str(item.get("title") or "")), item.get("order") or 0))
    return [{**best, "title": canonical_work_title(best.get("title")), "order": 1}]


# Official source sites may localize a work title.  Byelingua's canonical
# display title follows the work's original language; translated source titles
# remain searchable aliases and are not used as the display value.
ORIGINAL_WORK_TITLES = {
    "le crepuscule des dieux": "Götterdämmerung",
    "l or du rhin": "Das Rheingold",
    "la walkyrie": "Die Walküre",
    "le barbier de seville": "Il barbiere di Siviglia",
    "les noces de figaro": "Le nozze di Figaro",
    "la flute enchantee": "Die Zauberflöte",
    "le vaisseau fantome": "Der fliegende Holländer",
    "le chevalier a la rose": "Der Rosenkavalier",
    "la chauve souris": "Die Fledermaus",
    "le couronnement de poppee": "L'incoronazione di Poppea",
    "l elixir d amour": "L'elisir d'amore",
    "la clemence de titus": "La clemenza di Tito",
}


def canonical_work_title(value):
    title = str(value or "").strip()
    return ORIGINAL_WORK_TITLES.get(_programme_identity(title), title)


def schedule_options():
    organizations = supabase_service(
        "GET", "/rest/v1/organizations",
        params={"select": "id,name", "order": "name"},
    ) or []
    venues = supabase_service(
        "GET", "/rest/v1/venues",
        params={"select": "id,name,city,organization_id", "order": "name"},
    ) or []
    org_by_id = {row["id"]: row for row in organizations}
    # Keep location suggestions grounded in venues represented by current events.
    # If the catalog lookup is unavailable, retain the venue-directory fallback.
    catalog_rows = supabase_service(
        "GET", "/rest/v1/event_catalog_v1",
        params={"select": "organization,venue", "limit": "5000"},
    ) or []
    active_pairs = {(str(row.get("organization") or "").strip().casefold(), str(row.get("venue") or "").strip().casefold()) for row in catalog_rows}
    venue_rows = []
    cities = set()
    for venue in venues:
        org = org_by_id.get(venue.get("organization_id"), {})
        city = _schedule_city(venue.get("city") or org.get("name"))
        pair = (str(org.get("name") or "").strip().casefold(), str(venue.get("name") or "").strip().casefold())
        if active_pairs and pair not in active_pairs:
            continue
        cities.add(city)
        venue_rows.append({
            "id": venue.get("id"), "name": venue.get("name"), "city": city,
            "organization_id": venue.get("organization_id"),
            "organization": org.get("name", ""),
        })
    return {
        "cities": sorted(cities), "organizations": organizations, "venues": venue_rows,
        "event_types": [{"value": value, "label": EVENT_TYPE_LABELS[value]} for value in CANONICAL_EVENT_TYPES],
    }


def schedule_events(data):
    date_from = str(data.get("date_from") or "")
    date_to = str(data.get("date_to") or "")
    if not date_from or not date_to:
        raise ValueError("请选择开始和结束日期。")
    if date_from > date_to:
        raise ValueError("开始日期不能晚于结束日期。")
    params = {
        "select": "*",
        "order": "date.asc,start_time.asc", "limit": "1000",
    }
    # One `and` expression keeps both date bounds in a single query parameter.
    params["and"] = f"(date.gte.{date_from},date.lte.{date_to})"
    event_type = canonical_event_type(data.get("event_type")) if data.get("event_type") else ""
    rows = supabase_service("GET", "/rest/v1/event_catalog_v1", params=params) or []
    # event_catalog_v1 intentionally exposes the canonical venue name.  The
    # occurrence room is stored on events and must be joined separately so the
    # UI can show e.g. "Auditorio ... · Sala Sinfónica".
    event_keys = [str(row.get("event_id")) for row in rows if row.get("event_id")]
    event_rooms = supabase_service(
        "GET", "/rest/v1/events",
        params={"event_key": f"in.({','.join(event_keys)})", "select": "event_key,room", "limit": "5000"},
    ) if event_keys else []
    rooms_by_key = {str(row.get("event_key")): row.get("room") for row in (event_rooms or [])}
    for row in rows:
        row["room"] = rooms_by_key.get(str(row.get("event_id")))
    artist_event_keys = None
    artist_query = str(data.get("artist_query") or data.get("query") or "").strip()
    if artist_query:
        all_artists = supabase_service("GET", "/rest/v1/artists", params={"select":"id,artist_name", "limit":"5000"}) or []
        artists = [row for row in all_artists if search_match_score(artist_query, row.get("artist_name")) >= 0.60]
        artist_ids = [str(row.get("id")) for row in artists if row.get("id")]
        if artist_ids:
            credits = supabase_service("GET", "/rest/v1/event_credits", params={"artist_id":f"in.({','.join(artist_ids)})", "select":"event_id", "limit":"5000"}) or []
            internal_ids = list(dict.fromkeys(str(row.get("event_id")) for row in credits if row.get("event_id")))
            event_rows = supabase_service("GET", "/rest/v1/events", params={"id":f"in.({','.join(internal_ids)})", "select":"id,event_key", "limit":"5000"}) if internal_ids else []
            artist_event_keys = {str(row.get("event_key")) for row in (event_rows or []) if row.get("event_key")}
        else:
            artist_event_keys = set()
    venue_cities = {}
    if any(not (row.get("city") or row.get("location_city")) for row in rows):
        venue_rows = supabase_service(
            "GET", "/rest/v1/venues",
            params={"select": "name,city", "limit": "5000"},
        ) or []
        venue_cities = {
            str(venue.get("name") or "").strip().casefold(): venue.get("city")
            for venue in venue_rows if venue.get("name") and venue.get("city")
        }
    cities = {str(x).lower() for x in data.get("cities", []) if str(x).strip()}
    organizations = {str(x).lower() for x in data.get("organizations", []) if str(x).strip()}
    venues = {str(x).lower() for x in data.get("venues", []) if str(x).strip()}
    filtered = []
    for row in rows:
        row["source_title"] = row.get("title")
        row["title"] = canonical_work_title(row.get("work_title") or row.get("title"))
        if row.get("work_title"):
            row["work_title"] = canonical_work_title(row.get("work_title"))
        row["raw_event_type"] = row.get("event_type")
        row["event_type"] = canonical_event_type(row.get("event_type"))
        if event_type and row["event_type"] != event_type:
            continue
        city = _event_city(row, venue_cities)
        if city:
            row["city"] = city
        artist_match = artist_event_keys is not None and str(row.get("event_id")) in artist_event_keys
        if cities and city.casefold() not in cities:
            continue
        if organizations and str(row.get("organization", "")).lower() not in organizations:
            continue
        if venues and str(row.get("venue", "")).lower() not in venues:
            continue
        keyword = data.get("work_query") or data.get("query")
        if keyword and not artist_match and search_match_score(keyword, row.get("title"), row.get("work_title"), row.get("composer"), row.get("organization"), row.get("venue"), row.get("artist_name")) < 0.60:
            continue
        filtered.append(row)
    unique = []
    seen_event_keys = set()
    for row in filtered:
        event_key = str(row.get("event_id") or row.get("id") or "")
        if event_key and event_key in seen_event_keys:
            continue
        if event_key:
            seen_event_keys.add(event_key)
        unique.append(row)
    return {"events": unique}


def schedule_event_detail(event_id):
    catalog = supabase_service(
        "GET", "/rest/v1/event_catalog_v1",
        params={"event_id": f"eq.{event_id}", "limit": "1"},
    ) or []
    if not catalog:
        raise ValueError("找不到这场演出。")
    event = catalog[0]
    event["source_title"] = event.get("title")
    event["title"] = canonical_work_title(event.get("work_title") or event.get("title"))
    if event.get("work_title"):
        event["work_title"] = canonical_work_title(event.get("work_title"))
    event["raw_event_type"] = event.get("event_type")
    event["event_type"] = canonical_event_type(event.get("event_type"))
    base = supabase_service(
        "GET", "/rest/v1/events",
        params={"event_key": f"eq.{event_id}", "select": "id", "limit": "1"},
    ) or []
    if not base:
        return {"event": {**event, "programme": [], "credits": []}}
    internal_id = base[0]["id"]
    room_rows = supabase_service(
        "GET", "/rest/v1/events",
        params={"id": f"eq.{internal_id}", "select": "room", "limit": "1"},
    ) or []
    event["room"] = room_rows[0].get("room") if room_rows else None
    programme = supabase_service(
        "GET", "/rest/v1/event_programme",
        params={"event_id": f"eq.{internal_id}", "select": '"order",works(title,composer)', "order": '"order"'},
    ) or []
    credits = supabase_service(
        "GET", "/rest/v1/event_credits",
        params={"event_id": f"eq.{internal_id}", "select": "artist_id,role,character,raw_character,artists(artist_name),work_characters(canonical_name)"},
    ) or []
    event["programme"] = normalized_programme(event, programme)
    event["credits"] = [
        {"artist_id": row.get("artist_id"), "artist_name": (row.get("artists") or {}).get("artist_name"), "role": row.get("role"), "raw_role_label": row.get("role"), "role_type": "cast" if ((row.get("work_characters") or {}).get("canonical_name") or row.get("raw_character") or row.get("character")) else "artistic_team", "character_role": ((row.get("work_characters") or {}).get("canonical_name") or row.get("raw_character") or row.get("character")), "artistic_function": None if ((row.get("work_characters") or {}).get("canonical_name") or row.get("raw_character") or row.get("character")) else row.get("role"), "character": ((row.get("work_characters") or {}).get("canonical_name") or row.get("raw_character") or row.get("character"))}
        for row in credits
    ]
    return {"event": event}


def _event_internal_id(event_key):
    rows = supabase_service("GET", "/rest/v1/events", params={"event_key": f"eq.{event_key}", "select": "id", "limit": "1"}) or []
    if not rows:
        raise ValueError("演出不存在。")
    return rows[0]["id"]


def user_event_relations(headers, event_keys=None):
    user = authenticated_user(headers)
    rows = supabase_service("GET", "/rest/v1/user_event_relations", params={"user_id": f"eq.{user['id']}", "select": "id,event_id,intent_status,is_planned,attendance_status,ticket_status,created_at,updated_at", "limit": "5000"}) or []
    if event_keys is None:
        event_ids = [str(row.get("event_id")) for row in rows if row.get("event_id")]
        events = supabase_service("GET", "/rest/v1/events", params={"id": f"in.({','.join(event_ids)})", "select": "id,event_key", "limit": "5000"}) if event_ids else []
        id_to_key = {str(row["id"]): row.get("event_key") for row in (events or [])}
        return {"relations": [{**row, "intent_status": "optional" if row.get("intent_status") == "maybe_go" else row.get("intent_status"), "event_key": id_to_key.get(str(row.get("event_id")))} for row in rows]}
    keys = [str(key).strip() for key in event_keys if str(key).strip()]
    if not keys:
        return {"relations": []}
    events = supabase_service("GET", "/rest/v1/events", params={"event_key": f"in.({','.join(keys)})", "select": "id,event_key", "limit": "5000"}) or []
    id_to_key = {str(row["id"]): row.get("event_key") for row in events}
    return {"relations": [{**row, "intent_status": "optional" if row.get("intent_status") == "maybe_go" else row.get("intent_status"), "event_key": id_to_key.get(str(row.get("event_id")))} for row in rows if str(row.get("event_id")) in id_to_key]}


def set_user_event_relation(headers, event_key, intent_status, is_planned=True):
    user = authenticated_user(headers)
    intent = str(intent_status or "").strip()
    if intent == "maybe_go":
        intent = "optional"
    if intent not in {"interested", "optional", "must_go"}:
        raise ValueError("无效的演出意向状态。")
    internal_id = _event_internal_id(str(event_key).strip())
    storage_intent = "maybe_go" if intent == "optional" else intent
    payload = {"user_id": user["id"], "event_id": internal_id, "intent_status": storage_intent, "is_planned": bool(is_planned), "updated_at": datetime.now(timezone.utc).isoformat()}
    rows = supabase_service("POST", "/rest/v1/user_event_relations", params={"on_conflict": "user_id,event_id"}, payload=payload, prefer="resolution=merge-duplicates,return=representation") or []
    result = rows[0] if rows else payload
    result = {**result, "intent_status": "optional" if result.get("intent_status") == "maybe_go" else result.get("intent_status")}
    return {"relation": result}


def _schedule_owned(user_id, schedule_id):
    rows = supabase_service("GET", "/rest/v1/schedules", params={"id": f"eq.{schedule_id}", "user_id": f"eq.{user_id}", "select": "*", "limit": "1"}) or []
    if not rows:
        raise PermissionError("无权访问该 Schedule。")
    return rows[0]


def _schedule_events_payload(schedule_id):
    rows = supabase_service("GET", "/rest/v1/schedule_events", params={"schedule_id": f"eq.{schedule_id}", "select": "*", "order": "sort_order.asc,created_at.asc", "limit": "5000"}) or []
    if not rows:
        return []
    ids = [str(row["event_id"]) for row in rows]
    events = supabase_service("GET", "/rest/v1/events", params={"id": f"in.({','.join(ids)})", "select": "id,event_key", "limit": "5000"}) or []
    key_by_id = {str(row["id"]): row.get("event_key") for row in events}
    keys = [key for key in key_by_id.values() if key]
    catalog = supabase_service("GET", "/rest/v1/event_catalog_v1", params={"event_id": f"in.({','.join(keys)})", "limit": "5000"}) if keys else []
    event_by_key = {str(row.get("event_id")): row for row in (catalog or [])}
    return [{**row, "event_key": key_by_id.get(str(row["event_id"])), "event": event_by_key.get(key_by_id.get(str(row["event_id"])), {})} for row in rows]


def _refresh_schedule_date_range(schedule_id, user_id):
    rows = _schedule_events_payload(schedule_id)
    dates = [str(row.get("event", {}).get("date") or "")[:10] for row in rows if row.get("event", {}).get("date")]
    payload = {"start_date": min(dates) if dates else None, "end_date": max(dates) if dates else None, "updated_at": datetime.now(timezone.utc).isoformat()}
    supabase_service("PATCH", "/rest/v1/schedules", params={"id": f"eq.{schedule_id}", "user_id": f"eq.{user_id}"}, payload=payload)
    return payload


def create_schedule(headers, title):
    user = authenticated_user(headers)
    title = str(title or "").strip()
    if not title:
        raise ValueError("Schedule 标题不能为空。")
    rows = supabase_service("POST", "/rest/v1/schedules", payload={"user_id": user["id"], "title": title, "status": "draft"}) or []
    return {"schedule": rows[0] if rows else None}


def list_schedules(headers):
    user = authenticated_user(headers)
    rows = supabase_service("GET", "/rest/v1/schedules", params={"user_id": f"eq.{user['id']}", "select": "*", "order": "updated_at.desc", "limit": "5000"}) or []
    for row in rows:
        members = _schedule_events_payload(row["id"])
        row["event_count"] = len(members)
        row["cities"] = sorted({_event_city(member.get("event") or {}) for member in members if _event_city(member.get("event") or {})})
    return {"schedules": rows}


def get_schedule(headers, schedule_id):
    user = authenticated_user(headers)
    schedule = _schedule_owned(user["id"], schedule_id)
    return {"schedule": schedule, "events": _schedule_events_payload(schedule_id)}


def update_schedule(headers, schedule_id, title=None, status=None):
    user = authenticated_user(headers); _schedule_owned(user["id"], schedule_id)
    payload = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if title is not None:
        title = str(title).strip()
        if not title: raise ValueError("Schedule 标题不能为空。")
        payload["title"] = title
    if status is not None:
        if status not in {"draft", "planned", "completed", "archived"}: raise ValueError("无效的 Schedule 状态。")
        payload["status"] = status
    rows = supabase_service("PATCH", "/rest/v1/schedules", params={"id": f"eq.{schedule_id}", "user_id": f"eq.{user['id']}"}, payload=payload) or []
    result = rows[0] if rows else {"id": schedule_id, **payload}
    if status == "planned":
        try:
            confirmed = supabase_service("PATCH", "/rest/v1/schedules", params={"id": f"eq.{schedule_id}", "user_id": f"eq.{user['id']}"}, payload={"needs_reconfirmation": False, "confirmed_at": datetime.now(timezone.utc).isoformat()}) or []
            if confirmed:
                result = confirmed[0]
        except Exception:
            pass
    return {"schedule": result}


def mark_schedule_needs_confirmation(headers, schedule_id):
    user = authenticated_user(headers)
    schedule = _schedule_owned(user["id"], schedule_id)
    if schedule.get("status") != "planned":
        return {"schedule": schedule, "reconfirmation_supported": False}
    try:
        rows = supabase_service(
            "PATCH", "/rest/v1/schedules",
            params={"id":f"eq.{schedule_id}","user_id":f"eq.{user['id']}"},
            payload={"needs_reconfirmation": True, "updated_at":datetime.now(timezone.utc).isoformat()},
        ) or []
        return {"schedule": rows[0] if rows else {**schedule, "needs_reconfirmation": True}, "reconfirmation_supported": True}
    except Exception:
        # Older deployments do not yet have the compatibility column. Never
        # demote a confirmed schedule to draft; the migration is reported separately.
        return {"schedule": {**schedule, "needs_reconfirmation": True}, "reconfirmation_supported": False}


def add_schedule_event(headers, schedule_id, event_key, note=None):
    user = authenticated_user(headers); _schedule_owned(user["id"], schedule_id)
    event_id = _event_internal_id(str(event_key).strip())
    existing = supabase_service("GET", "/rest/v1/schedule_events", params={"schedule_id": f"eq.{schedule_id}", "select": "sort_order", "order": "sort_order.desc", "limit": "1"}) or []
    sort_order = int(existing[0].get("sort_order", -1)) + 1 if existing else 0
    payload = {"schedule_id": schedule_id, "event_id": event_id, "sort_order": sort_order, "note": note}
    rows = supabase_service("POST", "/rest/v1/schedule_events", params={"on_conflict": "schedule_id,event_id"}, payload=payload, prefer="resolution=merge-duplicates,return=representation") or []
    _refresh_schedule_date_range(schedule_id, user["id"])
    if _schedule_owned(user["id"], schedule_id).get("status") == "planned":
        mark_schedule_needs_confirmation(headers, schedule_id)
    return get_schedule(headers, schedule_id)


def remove_schedule_event(headers, schedule_id, event_key):
    user = authenticated_user(headers); _schedule_owned(user["id"], schedule_id)
    event_id = _event_internal_id(str(event_key).strip())
    supabase_service("DELETE", "/rest/v1/schedule_events", params={"schedule_id": f"eq.{schedule_id}", "event_id": f"eq.{event_id}"})
    _refresh_schedule_date_range(schedule_id, user["id"])
    if _schedule_owned(user["id"], schedule_id).get("status") == "planned":
        mark_schedule_needs_confirmation(headers, schedule_id)
    return get_schedule(headers, schedule_id)


def reorder_schedule_events(headers, schedule_id, ordered_event_keys):
    user = authenticated_user(headers); _schedule_owned(user["id"], schedule_id)
    for index, key in enumerate(ordered_event_keys or []):
        event_id = _event_internal_id(str(key).strip())
        supabase_service("PATCH", "/rest/v1/schedule_events", params={"schedule_id": f"eq.{schedule_id}", "event_id": f"eq.{event_id}"}, payload={"sort_order": index, "updated_at": datetime.now(timezone.utc).isoformat()})
    _refresh_schedule_date_range(schedule_id, user["id"])
    if _schedule_owned(user["id"], schedule_id).get("status") == "planned":
        mark_schedule_needs_confirmation(headers, schedule_id)
    return get_schedule(headers, schedule_id)


def _ics_escape(value):
    return str(value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r", "").replace("\n", "\\n")


def _ics_programme(event):
    programme = event.get("programme") or event.get("program") or []
    if isinstance(programme, str):
        return programme.strip()
    if isinstance(programme, dict):
        programme = [programme]
    lines = []
    for item in programme if isinstance(programme, list) else []:
        if isinstance(item, str):
            if item.strip(): lines.append(item.strip())
            continue
        if isinstance(item, dict):
            composer = str(item.get("composer") or "").strip()
            title = str(item.get("work_title") or item.get("title") or item.get("work") or "").strip()
            text = " · ".join(part for part in (composer, title) if part)
            if text: lines.append(text)
    return "\n".join(lines)


def export_schedule_ics(headers, schedule_id):
    user = authenticated_user(headers)
    schedule = _schedule_owned(user["id"], schedule_id)
    if schedule.get("status") != "planned":
        raise ValueError("Only planned schedules can be exported.")
    rows = _schedule_events_payload(schedule_id)
    generated_at = datetime.now(timezone.utc)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Byelingua//Schedule//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-TIMEZONE:Europe/Paris"]
    for row in rows:
        event = row.get("event") or {}
        date = str(event.get("date") or "").replace("-", "")
        start = str(event.get("start_time") or "").replace(":", "")[:6]
        if not date or len(date) != 8: continue
        if len(start) < 4: start = "000000"
        elif len(start) == 4: start += "00"
        uid = f"{row.get('event_key') or row.get('event_id')}@byelingua"
        title = event.get("title") or event.get("work_title") or "Event"
        venue = event.get("venue") or ""
        city = _event_city(event)
        address = event.get("full_address") or event.get("venue_address") or event.get("address")
        location = ", ".join(part for part in (venue, address, city) if part)
        description = _ics_programme(event)
        lines += ["BEGIN:VEVENT", f"UID:{_ics_escape(uid)}", f"DTSTAMP:{generated_at.strftime('%Y%m%dT%H%M%SZ')}", f"SUMMARY:{_ics_escape(title)}", f"DTSTART;TZID=Europe/Paris:{date}T{start}"]
        end = str(event.get("end_time") or "").replace(":", "")[:6]
        if len(end) == 4: end += "00"
        if len(end) < 4:
            try:
                local_start = datetime.strptime(f"{date}{start}", "%Y%m%d%H%M%S")
                end = (local_start + timedelta(hours=2)).strftime("%H%M%S")
            except ValueError:
                end = "020000"
        lines.append(f"DTEND;TZID=Europe/Paris:{date}T{end}")
        if location: lines.append(f"LOCATION:{_ics_escape(location)}")
        if description: lines.append(f"DESCRIPTION:{_ics_escape(description)}")
        source_url = event.get("source_url") or event.get("detail_url") or event.get("original_url")
        if source_url: lines.append(f"URL:{_ics_escape(source_url)}")
        lines += ["END:VEVENT"]
    lines += ["END:VCALENDAR"]
    safe_title = re.sub(r"[^A-Za-z0-9._-]+", "_", str(schedule.get("title") or "schedule")).strip("_") or "schedule"
    date_suffix = f"-{schedule.get('start_date')}-{schedule.get('end_date')}" if schedule.get("start_date") and schedule.get("end_date") else ""
    return {"filename": f"{safe_title}{date_suffix}.ics", "ics": "\r\n".join(lines) + "\r\n"}


def _schedule_email_content(schedule, rows, language, summary_url):
    english = language == "en"
    title = str(schedule.get("title") or "Schedule")
    range_text = " – ".join(str(x) for x in (schedule.get("start_date"), schedule.get("end_date")) if x)
    groups = {}
    for row in rows:
        event = row.get("event") or {}
        groups.setdefault(str(event.get("date") or ""), []).append(event)
    grouped = []
    for date in sorted(groups):
        events = sorted(groups[date], key=lambda e: str(e.get("start_time") or ""))
        grouped.append((date, events))
    def value(event, key): return str(event.get(key) or "")
    html_groups, text_groups = [], []
    for date, events in grouped:
        html_items, text_items = [], []
        for event in events:
            event_title = escape(value(event, "title") or value(event, "work_title") or "Event")
            venue = escape(value(event, "venue")); city = escape(_event_city(event)); org = escape(value(event, "organization")); time = escape(value(event, "start_time"))
            url = value(event, "source_url") or value(event, "detail_url") or value(event, "original_url")
            link = f'<a href="{escape(url, quote=True)}">{event_title}</a>' if url else event_title
            html_items.append(f"<li><strong>{escape(time)}</strong> · {link}<br><span>{venue} · {city} · {org}</span></li>")
            text_items.append(f"- {value(event, 'start_time')} · {value(event, 'title') or value(event, 'work_title') or 'Event'} · {value(event, 'venue')} · {_event_city(event)} · {value(event, 'organization')}" + (f" · {url}" if url else ""))
        html_groups.append(f"<h2>{escape(date)}</h2><ul>{''.join(html_items)}</ul>")
        text_groups.append(date + "\n" + "\n".join(text_items))
    heading = "Your Byelingua schedule" if english else "你的 Byelingua 行程"
    subject = f"Byelingua · {title}"
    html = f'<main style="max-width:680px;margin:auto;font-family:Arial,sans-serif;color:#17201b"><h1 style="color:#214d3a">BYELINGUA</h1><h2>{escape(heading)}</h2><p>{escape(title)} · {escape(range_text)}</p>{"".join(html_groups)}<p><a href="{escape(summary_url, quote=True)}">{"Open schedule" if english else "打开行程成果页"}</a></p></main>'
    text = heading + "\n\n" + title + " · " + range_text + "\n\n" + "\n\n".join(text_groups) + "\n\n" + ("Open schedule: " if english else "打开行程成果页：") + summary_url
    return subject, html, text


def send_schedule_email(headers, schedule_id):
    user = authenticated_user(headers)
    schedule = _schedule_owned(user["id"], schedule_id)
    if schedule.get("status") != "planned": raise ValueError("Only planned schedules can be emailed.")
    resend_key = os.environ.get("RESEND_API_KEY", "").strip(); email_from = os.environ.get("EMAIL_FROM", "").strip()
    if not resend_key or not email_from: raise RuntimeError("RESEND_API_KEY and EMAIL_FROM must be configured.")
    profiles = supabase_service("GET", "/rest/v1/profiles", params={"id":f"eq.{user['id']}","select":"email,preferred_language"}) or []
    if not profiles or not str(profiles[0].get("email") or "").strip(): raise ValueError("当前账户没有可用邮箱。")
    profile = profiles[0]; rows = _schedule_events_payload(schedule_id); ics = export_schedule_ics(headers, schedule_id)
    base_url = os.environ.get("PUBLIC_APP_URL", "https://www.bye-lingua.site").rstrip("/")
    subject, html, text = _schedule_email_content(schedule, rows, profile.get("preferred_language") or "zh", f"{base_url}/schedule-summary.html?schedule_id={quote(str(schedule_id))}")
    content_hash = hashlib.sha256((html + ics["ics"]).encode("utf-8")).hexdigest()
    delivery = {"user_id":user["id"],"schedule_id":schedule_id,"recipient_email":str(profile["email"]).strip(),"status":"pending","content_hash":content_hash}
    reserved = supabase_service(
        "POST", "/rest/v1/schedule_email_deliveries",
        payload=delivery,
        prefer="return=representation",
    ) or []
    if not reserved or not reserved[0].get("id"):
        raise RuntimeError("无法创建行程邮件发送记录，邮件未发送。")
    delivery_id = reserved[0]["id"]
    try:
        response = SESSION.post("https://api.resend.com/emails", headers={"Authorization":f"Bearer {resend_key}","Content-Type":"application/json","User-Agent":"Byelingua-Server/3.0"}, json={"from":email_from,"to":[delivery["recipient_email"]],"subject":subject,"html":html,"text":text,"attachments":[{"filename":ics["filename"],"content":base64.b64encode(ics["ics"].encode()).decode("ascii")}]}, timeout=20)
        if not response.ok: raise ValueError("邮件服务拒绝了发送请求。")
        provider_id = response.json().get("id")
        supabase_service("PATCH", "/rest/v1/schedule_email_deliveries", params={"id":f"eq.{delivery_id}"}, payload={"status":"sent","provider_message_id":provider_id,"sent_at":datetime.now(timezone.utc).isoformat()})
        return {"sent":True,"recipient":delivery["recipient_email"]}
    except Exception as error:
        supabase_service("PATCH", "/rest/v1/schedule_email_deliveries", params={"id":f"eq.{delivery_id}"}, payload={"status":"failed","error":str(error)[:500]})
        raise


def character_options(query=""):
    works = supabase_service("GET", "/rest/v1/works", params={"select": "id,title,composer", "limit": "2000"}) or []
    work_by_id = {row["id"]: row for row in works}
    rows = supabase_service(
        "GET", "/rest/v1/work_characters",
        params={"select": "id,work_id,canonical_name", "order": "canonical_name", "limit": "2000"},
    ) or []
    needle = str(query or "").strip().casefold()
    result = []
    for row in rows:
        work = work_by_id.get(row.get("work_id"), {})
        if needle and needle not in str(row.get("canonical_name", "")).casefold():
            continue
        result.append({"id": row.get("id"), "canonical_name": row.get("canonical_name"), "work_id": row.get("work_id"), "work_title": work.get("title"), "composer": work.get("composer")})
    return {"characters": result[:100]}


def character_events(data):
    character_id = str(data.get("character_id") or "").strip()
    if character_id and not valid_uuid(character_id):
        raise ValueError("请选择有效的角色。")
    if not character_id:
        raise ValueError("请选择一个角色。")
    date_from, date_to = str(data.get("date_from") or ""), str(data.get("date_to") or "")
    if not date_from or not date_to:
        raise ValueError("请选择开始和结束日期。")
    params = {
        "select": "*", "character_id": f"eq.{character_id}",
        "and": f"(date.gte.{date_from},date.lte.{date_to})",
        "order": "date.asc,start_time.asc", "limit": "1000",
    }
    rows = supabase_service("GET", "/rest/v1/event_character_catalog_v1", params=params) or []
    cities = {str(x).casefold() for x in data.get("cities", []) if str(x).strip()}
    organizations = {str(x).casefold() for x in data.get("organizations", []) if str(x).strip()}
    venues = {str(x).casefold() for x in data.get("venues", []) if str(x).strip()}
    event_type = canonical_event_type(data.get("event_type")) if data.get("event_type") else ""
    result = []
    for row in rows:
        if event_type and row.get("event_type") and canonical_event_type(row.get("event_type")) != event_type:
            continue
        if cities and _schedule_city(row.get("venue") or row.get("organization")).casefold() not in cities:
            continue
        if organizations and str(row.get("organization", "")).casefold() not in organizations:
            continue
        if venues and str(row.get("venue", "")).casefold() not in venues:
            continue
        result.append(row)
    print(f"[character_events] character_id={character_id} events={len(result)}")
    return {"events": result}


def artist_options(query=""):
    rows = supabase_service(
        "GET", "/rest/v1/artists",
        params={"select": "id,artist_name", "order": "artist_name", "limit": "5000"},
    ) or []
    ranked = sorted(rows, key=lambda row: search_match_score(query, row.get("artist_name")), reverse=True)
    return {"artists": [
        {"id": row.get("id"), "artist_name": row.get("artist_name")}
        for row in ranked
        if not query or search_match_score(query, row.get("artist_name")) >= 0.60
    ][:100]}


def artist_events(data):
    artist_id = str(data.get("artist_id") or "").strip()
    if artist_id and not valid_uuid(artist_id):
        raise ValueError("请选择有效的艺术家。")
    if not artist_id:
        raise ValueError("请选择一位艺术家。")
    date_from, date_to = str(data.get("date_from") or ""), str(data.get("date_to") or "")
    if not date_from or not date_to:
        raise ValueError("请选择开始和结束日期。")
    credits = supabase_service(
        "GET", "/rest/v1/event_credits",
        params={"artist_id": f"eq.{artist_id}", "select": "event_id,artist_id,role,character,raw_character,artists(artist_name)", "limit": "5000"},
    ) or []
    event_ids = list(dict.fromkeys(str(row.get("event_id")) for row in credits if row.get("event_id")))
    if not event_ids:
        return {"events": []}
    event_key_by_internal_id = event_keys_for_internal_ids(event_ids)
    event_keys = list(event_key_by_internal_id.values())
    print(f"[artist_events] artist_id={artist_id} event_credits={len(credits)} event_ids={len(event_ids)} event_keys={len(event_keys)}")
    catalog = supabase_service(
        "GET", "/rest/v1/event_catalog_v1",
        params={"event_id": f"in.({','.join(event_keys)})", "and": f"(date.gte.{date_from},date.lte.{date_to})", "order": "date.asc,start_time.asc", "limit": "1000"},
    ) or []
    by_event = {}
    for row in credits:
        by_event.setdefault(str(row.get("event_id")), []).append(row)
    cities = {str(x).casefold() for x in data.get("cities", []) if str(x).strip()}
    venues = {str(x).casefold() for x in data.get("venues", []) if str(x).strip()}
    event_type = canonical_event_type(data.get("event_type")) if data.get("event_type") else ""
    result = []
    for event in catalog:
        if event_type and canonical_event_type(event.get("event_type")) != event_type:
            continue
        if cities and _schedule_city(event.get("venue") or event.get("organization")).casefold() not in cities:
            continue
        if venues and str(event.get("venue", "")).casefold() not in venues:
            continue
        internal_id = next((key for key, value in event_key_by_internal_id.items() if value == str(event.get("event_id"))), "")
        credit = next((row for row in by_event.get(internal_id, []) if row.get("artist_id") == artist_id), by_event.get(internal_id, [{}])[0])
        event = dict(event)
        event["role"] = credit.get("role")
        event["character"] = credit.get("character") or credit.get("raw_character")
        event["artist_name"] = (credit.get("artists") or {}).get("artist_name")
        event["event_type"] = canonical_event_type(event.get("event_type"))
        result.append(event)
    return {"events": result}


def artist_context(data):
    artist_id = str(data.get("artist_id") or "").strip()
    if not artist_id:
        raise ValueError("请选择一位艺术家。")
    artist_rows = supabase_service("GET", "/rest/v1/artists", params={"id": f"eq.{artist_id}", "select": "id,artist_name", "limit": "1"}) or []
    if not artist_rows:
        raise ValueError("找不到该艺术家。")
    credit_rows = supabase_service(
        "GET", "/rest/v1/event_credits",
        params={"artist_id": f"eq.{artist_id}", "select": "event_id,role,character,raw_character", "limit": "5000"},
    ) or []
    event_ids = list(dict.fromkeys(str(row.get("event_id")) for row in credit_rows if row.get("event_id")))
    performances = []
    if event_ids:
        event_key_by_internal_id = event_keys_for_internal_ids(event_ids)
        event_keys = list(event_key_by_internal_id.values())
        print(f"[artist_context] artist_id={artist_id} event_credits={len(credit_rows)} event_ids={len(event_ids)} event_keys={len(event_keys)}")
        catalog = supabase_service("GET", "/rest/v1/event_catalog_v1", params={"event_id": f"in.({','.join(event_keys)})", "order": "date.asc,start_time.asc", "limit": "2000"}) or []
        by_event = {str(row.get("event_id")): row for row in credit_rows}
        for event in catalog:
            internal_id = next((key for key, value in event_key_by_internal_id.items() if value == str(event.get("event_id"))), "")
            credit = by_event.get(internal_id, {})
            performances.append({
                "event_id": event.get("event_id"),
                "date": event.get("date"), "start_time": event.get("start_time"),
                "start_datetime": f"{event.get('date') or ''}T{event.get('start_time') or '00:00:00'}",
                "work_title": event.get("work_title") or event.get("title"),
                "composer": event.get("composer"),
                "title": event.get("title"),
                "organization_name": event.get("organization"), "venue_name": event.get("venue"),
                "city": _schedule_city(event.get("venue") or event.get("organization")),
                "role": credit.get("role"),
                "character": credit.get("character") or credit.get("raw_character"),
            })
    roles = sorted({str(row.get("role")) for row in credit_rows if row.get("role")})
    articles = supabase_service("GET", "/rest/v1/public_articles", params={"select": "id,title,source,published_at,canonical_url,url,raw_data", "order": "published_at.desc", "limit": "200"}) or []
    name = str(artist_rows[0].get("artist_name") or "")
    needle = normalize_search_key(name)
    news = []
    for article in articles:
        raw = article.get("raw_data") if isinstance(article.get("raw_data"), dict) else {}
        title = str(article.get("title") or raw.get("title") or "")
        original_title = str(raw.get("original_title") or raw.get("source_title") or "")
        summary = str(raw.get("summary") or raw.get("description") or "")
        content = str(raw.get("result") or raw.get("content") or article.get("result") or "")
        score = search_match_score(name, title, original_title) * 1.2
        score = max(score, search_match_score(name, summary, content))
        if needle and score < 0.60:
            continue
        news.append((score, {"id": article.get("id"), "title": title, "source": article.get("source") or "", "published_at": article.get("published_at"), "article_url": article.get("url") or article.get("canonical_url"), "canonical_url": article.get("canonical_url") or article.get("url")}))
    news.sort(key=lambda item: str(item[1].get("published_at") or ""), reverse=True)
    news.sort(key=lambda item: item[0], reverse=True)
    news = [item[1] for item in news[:10]]
    return {"artist": {"id": artist_rows[0].get("id"), "name": name, "roles": roles}, "performances": performances, "news": news}


def entity_options(query="", work_id=""):
    works = supabase_service("GET", "/rest/v1/works", params={"select": "id,title,composer", "order": "title", "limit": "2000"}) or []
    try:
        work_aliases = supabase_service("GET", "/rest/v1/work_aliases", params={"select": "work_id,alias", "limit": "10000"}) or []
    except Exception:
        work_aliases = []
    aliases_by_work = {}
    for row in work_aliases:
        aliases_by_work.setdefault(str(row.get("work_id")), []).append(row.get("alias"))
    characters = supabase_service("GET", "/rest/v1/work_characters", params={"select": "id,work_id,canonical_name", "order": "canonical_name", "limit": "3000"}) or []
    aliases = supabase_service("GET", "/rest/v1/character_aliases", params={"select": "character_id,alias", "limit": "10000"}) or []
    artists = supabase_service("GET", "/rest/v1/artists", params={"select": "id,artist_name", "order": "artist_name", "limit": "5000"}) or []
    work_by_id = {str(row.get("id")): row for row in works}
    aliases_by_character = {}
    for row in aliases:
        aliases_by_character.setdefault(str(row.get("character_id")), []).append(row.get("alias"))
    role_rows = supabase_service("GET", "/rest/v1/event_credits", params={"select": "artist_id,role", "limit": "10000"}) or []
    roles_by_artist = {}
    for row in role_rows:
        if row.get("artist_id") and row.get("role"):
            roles_by_artist.setdefault(str(row["artist_id"]), set()).add(str(row["role"]))
    work_matches = [row for row in works if not query or search_match_score(query, row.get("title"), row.get("composer"), *aliases_by_work.get(str(row.get("id")), [])) >= 0.60]
    composer_names = sorted({str(row.get("composer") or "").strip() for row in works if row.get("composer") and (not query or search_match_score(query, row.get("composer")) >= 0.60)}, key=lambda value: search_match_score(query, value), reverse=True)
    composer_results = [{"type": "composer", "id": normalize_search_key(name), "label": name, "composer": name} for name in composer_names[:10]]
    return {
        "composers": composer_results,
        "works": [{"type": "work", "id": row.get("id"), "label": row.get("title"), "title": row.get("title"), "canonical_title": row.get("title"), "composer": row.get("composer"), "aliases": aliases_by_work.get(str(row.get("id")), [])}
                  for row in sorted(work_matches, key=lambda row: search_match_score(query, row.get("title"), row.get("composer"), *aliases_by_work.get(str(row.get("id")), [])), reverse=True)][:30],
        "characters": [{"type": "character", "id": row.get("id"), "label": row.get("canonical_name"), "canonical_name": row.get("canonical_name"), "work_title": work_by_id.get(str(row.get("work_id")), {}).get("title"), "composer": work_by_id.get(str(row.get("work_id")), {}).get("composer"), "work_id": row.get("work_id")}
                       for row in sorted(characters, key=lambda row: search_match_score(query, row.get("canonical_name"), *aliases_by_character.get(str(row.get("id")), [])), reverse=True)
                       if (not work_id or str(row.get("work_id")) == str(work_id)) and (not query or search_match_score(query, row.get("canonical_name"), *aliases_by_character.get(str(row.get("id")), [])) >= 0.60)][:30],
        "artists": [{"type": "artist", "id": row.get("id"), "label": row.get("artist_name"), "artist_name": row.get("artist_name"), "roles": sorted(roles_by_artist.get(str(row.get("id")), set()))}
                    for row in sorted(artists, key=lambda row: search_match_score(query, row.get("artist_name")), reverse=True)
                    if not query or search_match_score(query, row.get("artist_name")) >= 0.60][:30],
    }


def work_events(data):
    work_id = str(data.get("work_id") or "").strip()
    if work_id and not valid_uuid(work_id):
        work_id = ""
    work_ids = [str(value) for value in data.get("work_ids", []) if value]
    if not work_id and data.get("composer_query"):
        composer_query = str(data.get("composer_query") or "").strip()
        matches = supabase_service("GET", "/rest/v1/works", params={"composer": f"ilike.*{composer_query}*", "select": "id", "limit": "2000"}) or []
        work_ids = [str(row.get("id")) for row in matches if row.get("id")]
    if not work_id and not work_ids:
        raise ValueError("请选择一部作品。")
    date_from, date_to = str(data.get("date_from") or ""), str(data.get("date_to") or "")
    programme_params = {"work_id": f"eq.{work_id}" if work_id else f"in.({','.join(work_ids)})", "select": "event_id", "limit": "5000"}
    rows = supabase_service("GET", "/rest/v1/event_programme", params=programme_params) or []
    internal_ids = list(dict.fromkeys(str(row.get("event_id")) for row in rows if row.get("event_id")))
    if not internal_ids:
        return {"events": []}
    event_rows = supabase_service("GET", "/rest/v1/events", params={"id": f"in.({','.join(internal_ids)})", "select": "id,event_key", "limit": "5000"}) or []
    keys = [str(row.get("event_key")) for row in event_rows if row.get("event_key")]
    if not keys:
        return {"events": []}
    payload = dict(data); payload["date_from"], payload["date_to"] = date_from, date_to
    catalog = supabase_service("GET", "/rest/v1/event_catalog_v1", params={"event_id": f"in.({','.join(keys)})", "and": f"(date.gte.{date_from},date.lte.{date_to})", "order": "date.asc,start_time.asc", "limit": "1000"}) or []
    cities = {str(x).casefold() for x in data.get("cities", []) if str(x).strip()}
    venues = {str(x).casefold() for x in data.get("venues", []) if str(x).strip()}
    event_type = canonical_event_type(data.get("event_type")) if data.get("event_type") else ""
    return {"events": [dict(row, event_type=canonical_event_type(row.get("event_type"))) for row in catalog if (not event_type or canonical_event_type(row.get("event_type")) == event_type) and (not cities or _schedule_city(row.get("venue") or row.get("organization")).casefold() in cities) and (not venues or str(row.get("venue", "")).casefold() in venues)]}


def combined_entity_events(data):
    data = dict(data)
    raw_work_id = str(data.get("work_id") or "").strip()
    if raw_work_id and not valid_uuid(raw_work_id):
        # Legacy clients sometimes sent the visible composer label in work_id.
        # Never pass that value to a UUID comparison; treat it as free text.
        data.pop("work_id", None)
        data["composer_query"] = data.get("composer_query") or raw_work_id
    if data.get("character_id") and not valid_uuid(data.get("character_id")):
        data.pop("character_id", None)
    if data.get("artist_id") and not valid_uuid(data.get("artist_id")):
        data.pop("artist_id", None)
    selected = []
    if data.get("work_id") or data.get("composer_query"):
        selected.append(work_events(data).get("events", []))
    if data.get("character_id"):
        selected.append(character_events(data).get("events", []))
    if data.get("artist_id"):
        selected.append(artist_events(data).get("events", []))
    if not selected:
        return schedule_events(data)
    common_ids = set(str(row.get("event_id")) for row in selected[0])
    for rows in selected[1:]:
        common_ids &= {str(row.get("event_id")) for row in rows}
    by_id = {str(row.get("event_id")): row for row in selected[0]}
    return {"events": [by_id[event_id] for event_id in sorted(common_ids, key=lambda key: (by_id[key].get("date") or "", by_id[key].get("start_time") or ""))]}


class handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Cache-Control","no-store"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        try: self.send_json(200, public_payload())
        except Exception as error: self.send_json(500, {"error":str(error)})

    def do_POST(self):
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))).decode("utf-8")); action = data.get("action","get_public")
            if action == "get_public": self.send_json(200, public_payload()); return
            if action == "translate_wechat":
                self.send_json(200, translate_wechat_article(str(data.get("id","")), data.get("language",""))); return
            if action == "poll_wechat_translation":
                self.send_json(200, poll_wechat_translation(str(data.get("id","")), data.get("language",""))); return
            if action == "get_auth_config":
                url, publishable, _ = supabase_settings(); self.send_json(200,{"url":url,"publishable_key":publishable}); return
            if action == "get_news_source_options":
                authenticated_user(self.headers); self.send_json(200,{"sources":available_news_sources()}); return
            if action == "register_with_invite":
                self.send_json(200, register_with_invite(data.get("email",""), data.get("password",""), data.get("invite_code",""))); return
            if action == "sync_wechat":
                require_wechat_sync(self.headers)
                self.send_json(200, sync_wechat_article(data.get("article",{}))); return
            if action == "schedule_options":
                self.send_json(200, schedule_options()); return
            if action == "schedule_events":
                self.send_json(200, schedule_events(data)); return
            if action == "schedule_event_detail":
                self.send_json(200, schedule_event_detail(str(data.get("event_id", "")))); return
            if action == "get_event_relations":
                self.send_json(200, user_event_relations(self.headers, data.get("event_keys"))); return
            if action == "set_event_relation":
                self.send_json(200, set_user_event_relation(self.headers, str(data.get("event_key", "")), data.get("intent_status"), data.get("is_planned", True))); return
            if action == "create_schedule":
                self.send_json(200, create_schedule(self.headers, data.get("title"))); return
            if action == "list_schedules":
                self.send_json(200, list_schedules(self.headers)); return
            if action == "get_schedule":
                self.send_json(200, get_schedule(self.headers, str(data.get("schedule_id", "")))); return
            if action == "export_schedule_ics":
                self.send_json(200, export_schedule_ics(self.headers, str(data.get("schedule_id", "")))); return
            if action == "send_schedule_email":
                self.send_json(200, send_schedule_email(self.headers, str(data.get("schedule_id", "")))); return
            if action == "mark_schedule_needs_confirmation":
                self.send_json(200, mark_schedule_needs_confirmation(self.headers, str(data.get("schedule_id", "")))); return
            if action == "rename_schedule":
                self.send_json(200, update_schedule(self.headers, str(data.get("schedule_id", "")), title=data.get("title"))); return
            if action == "update_schedule_status":
                self.send_json(200, update_schedule(self.headers, str(data.get("schedule_id", "")), status=data.get("status"))); return
            if action == "delete_schedule":
                user = authenticated_user(self.headers); schedule_id = str(data.get("schedule_id", "")); _schedule_owned(user["id"], schedule_id)
                supabase_service("DELETE", "/rest/v1/schedules", params={"id": f"eq.{schedule_id}", "user_id": f"eq.{user['id']}"}); self.send_json(200, {"deleted": True}); return
            if action == "add_event_to_schedule":
                self.send_json(200, add_schedule_event(self.headers, str(data.get("schedule_id", "")), str(data.get("event_key", "")), data.get("note"))); return
            if action == "remove_event_from_schedule":
                self.send_json(200, remove_schedule_event(self.headers, str(data.get("schedule_id", "")), str(data.get("event_key", "")))); return
            if action == "reorder_schedule_events":
                self.send_json(200, reorder_schedule_events(self.headers, str(data.get("schedule_id", "")), data.get("ordered_event_keys", []))); return
            if action == "character_options":
                self.send_json(200, character_options(data.get("query", ""))); return
            if action == "character_events":
                self.send_json(200, character_events(data)); return
            if action == "artist_options":
                self.send_json(200, artist_options(data.get("query", ""))); return
            if action == "artist_events":
                self.send_json(200, artist_events(data)); return
            if action == "artist_context":
                self.send_json(200, artist_context(data)); return
            if action == "entity_options":
                self.send_json(200, entity_options(data.get("query", ""), data.get("work_id", ""))); return
            if action == "entity_events":
                entity_type = str(data.get("entity_type") or "")
                if entity_type == "work": self.send_json(200, work_events(data)); return
                if entity_type == "character": self.send_json(200, character_events(data)); return
                if entity_type == "artist": self.send_json(200, artist_events(data)); return
                raise ValueError("不支持的搜索类型。")
            if action == "combined_entity_events":
                self.send_json(200, combined_entity_events(data)); return
            if action in {"get_my_data","save_my_subscription","set_my_subscription_enabled","set_general_subscription","delete_my_subscription","run_my_digest","generate_brief_send","save_my_language","save_email_subscription","generate_invite_code","list_my_invite_codes"}:
                user = authenticated_user(self.headers)
                if action == "get_my_data": result = personal_payload(user["id"])
                elif action == "save_my_subscription": result = save_personal_subscription(user["id"], data.get("subscription",{}))
                elif action == "set_my_subscription_enabled": result = set_personal_subscription_enabled(user["id"], str(data.get("id", "")), data.get("enabled", True))
                elif action == "set_general_subscription": result = set_general_subscription(user["id"], data.get("source", {}), data.get("enabled", False))
                elif action == "delete_my_subscription": result = delete_personal_subscription(user["id"], str(data.get("id","")))
                elif action == "save_my_language": result = save_personal_language(user["id"], data.get("language",""))
                elif action == "save_email_subscription": result = save_email_subscription(user["id"], data.get("enabled", True))
                elif action == "generate_invite_code": result = generate_invite_code(user["id"])
                elif action == "list_my_invite_codes": result = list_my_invite_codes(user["id"])
                elif action == "generate_brief_send": result = generate_brief_and_send(user["id"])
                else: result = run_personal_digest(user["id"])
                self.send_json(200,result); return
            require_admin(self.headers); config = load_config()
            if action == "get_config": self.send_json(200, config)
            elif action == "save_settings":
                language = data.get("target_language","zh")
                if language not in LANGUAGES: raise ValueError("不支持所选输出语言。")
                config["target_language"] = language; save_config(config); self.send_json(200, config)
            elif action == "save_subscription":
                self.send_json(200, save_public_subscription(data.get("subscription",{}), data.get("old_id","")))
            elif action == "delete_subscription":
                config["subscriptions"] = [x for x in config["subscriptions"] if x.get("id") != data.get("id","")]; save_config(config); self.send_json(200,config)
            elif action == "set_subscription_enabled": self.send_json(200, set_public_subscription_enabled(str(data.get("id","")), bool(data.get("enabled",False))))
            elif action == "run_subscription": self.send_json(200, run_daily_digest(str(data.get("id",""))))
            elif action == "run_digest": self.send_json(200, run_daily_digest())
            elif action == "import_wechat": self.send_json(200, save_wechat_chinese(data.get("article",{})))
            elif action == "update_article_metadata": self.send_json(200, update_article_metadata(str(data.get("id","")), data.get("metadata",{})))
            elif action == "delete_article": self.send_json(200, delete_article(str(data.get("id","")), bool(data.get("allow_resync",False))))
            elif action == "retranslate_article": self.send_json(200, retranslate_article(str(data.get("id",""))))
            elif action == "backfill_bilingual": self.send_json(200, backfill_bilingual_article())
            else: self.send_json(400, {"error":"未知操作。"})
        except ManualBriefRateLimitError as error: self.send_json(429, {"error":str(error), **error.status})
        except PermissionError as error: self.send_json(401, {"error_code":"permission_denied", "error":str(error)})
        except requests.RequestException as error: self.send_json(502, {"error_code":"network_error", "error":"Upstream request failed."})
        except ValueError as error: self.send_json(400, {"error_code":"invalid_request", "error":str(error)})
        except Exception as error: self.send_json(500, {"error_code":"unknown_error", "error":str(error)})
