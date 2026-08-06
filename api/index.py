"""Byelingua API: subscriptions plus manually imported WeChat translations."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone
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
SESSION.headers.update({"User-Agent":"Mozilla/5.0 (compatible; Byelingua/3.0; +https://byelingua.vercel.app/)","Accept-Language":"en-US,en;q=0.8"})
PARIS_TIMEZONE = ZoneInfo("Europe/Paris")
WECHAT_EXPORTER_URL = os.environ.get("WECHAT_EXPORTER_URL", "https://down.mptext.top").rstrip("/")


def require_admin(headers):
    expected, supplied = os.environ.get("ADMIN_PASSWORD", ""), headers.get("X-Admin-Password", "")
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
    response = SESSION.get(match.url, headers={"Authorization":f"Bearer {token}"}, timeout=20)
    response.raise_for_status()
    return response.json()


def save_blob_json(pathname, value):
    payload = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
    with blob_client() as client:
        client.put(pathname, payload, access="private", content_type="application/json; charset=utf-8", overwrite=True, cache_control_max_age=0)


def load_config():
    config = load_blob_json("byelingua/config.json", json.loads(json.dumps(DEFAULT_CONFIG)))
    config.setdefault("target_language", "zh")
    config.setdefault("subscriptions", [])
    if int(config.get("version", 1)) < 3:
        existing = {item.get("feed_url") for item in config["subscriptions"]}
        config["subscriptions"].extend(json.loads(json.dumps(item)) for item in DEFAULT_CONFIG["subscriptions"] if item["feed_url"] not in existing)
        config["version"] = 3
        save_blob_json("byelingua/config.json", config)
    return config


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


def fetch_wechat_from_exporter(url):
    """Fetch normalized article HTML through wechat-article-exporter."""
    endpoint = f"{WECHAT_EXPORTER_URL}/api/public/v1/download?url={quote(url, safe='')}&format=html"
    headers = {}
    if os.environ.get("WECHAT_EXPORTER_AUTH_KEY"):
        headers["X-Auth-Key"] = os.environ["WECHAT_EXPORTER_AUTH_KEY"]
    access_id = os.environ.get("WECHAT_EXPORTER_CF_ACCESS_CLIENT_ID", "").strip()
    access_secret = os.environ.get("WECHAT_EXPORTER_CF_ACCESS_CLIENT_SECRET", "").strip()
    if access_id and access_secret:
        headers["CF-Access-Client-Id"] = access_id
        headers["CF-Access-Client-Secret"] = access_secret
    response = SESSION.get(endpoint, headers=headers, timeout=(8, 25))
    response.raise_for_status()
    return response.content


def fetch_wechat_from_proxy(url):
    """Fetch a WeChat page through the user's private Cloudflare Worker."""
    proxy_url = os.environ.get("WECHAT_PROXY_URL", "").strip().rstrip("/")
    if not proxy_url:
        raise ValueError("WECHAT_PROXY_URL is not configured.")
    separator = "&" if "?" in proxy_url else "?"
    endpoint = f"{proxy_url}{separator}url={quote(url, safe='')}&preset=mp"
    response = SESSION.get(endpoint, timeout=(8, 25))
    response.raise_for_status()
    return response.content


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
    sources = [lambda: fetch(normalized).content]
    if os.environ.get("WECHAT_PROXY_URL", "").strip():
        sources.append(lambda: fetch_wechat_from_proxy(normalized))
    sources.append(lambda: fetch_wechat_from_exporter(normalized))
    for load_html in sources:
        try:
            content_bytes = load_html()
            soup = BeautifulSoup(content_bytes, "html.parser")
        except requests.RequestException:
            continue
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
        if len(extracted) >= 200 and title:
            break
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
        if metadata_updates:
            existing.update(metadata_updates)
            now = datetime.now(timezone.utc).isoformat()
            existing["processed_at"] = now
            save_blob_json("byelingua/articles.json", {"updated_at":now,"articles":articles})
        return {"article":existing,"reused":True}
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


def delete_article(identifier, allow_resync=False):
    archive = load_blob_json("byelingua/articles.json", {"updated_at":"","articles":[]})
    removed = next((item for item in archive.get("articles", []) if item.get("id") == identifier), None)
    if not removed:
        raise ValueError("找不到要删除的文章。")
    articles = [item for item in archive.get("articles", []) if item.get("id") != identifier]
    now = datetime.now(timezone.utc).isoformat()
    save_blob_json("byelingua/articles.json", {"updated_at":now,"articles":articles})
    if allow_resync and removed.get("url"):
        seen_data = load_blob_json("byelingua/seen.json", {"urls":[]})
        removed_url = canonical_url(removed["url"])
        urls = [url for url in seen_data.get("urls", []) if canonical_url(url) != removed_url]
        save_blob_json("byelingua/seen.json", {"urls":urls})
    return {"deleted":identifier,"items":len(articles),"resync_allowed":bool(allow_resync)}


def retranslate_article(identifier):
    archive = load_blob_json("byelingua/articles.json", {"updated_at":"","articles":[]})
    articles = archive.get("articles", [])
    item = next((article for article in articles if article.get("id") == identifier), None)
    if not item:
        raise ValueError("找不到要重新翻译的文章。")
    original_title = item.get("original_title") or item.get("title") or ""
    try:
        if item.get("kind") == "wechat":
            extracted = extract_wechat_article(item.get("url", ""))
            source_text, original_title = extracted["text"], extracted["title"] or original_title
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
    config, seen_data = load_config(), load_blob_json("byelingua/seen.json", {"urls":[]})
    archive = load_blob_json("byelingua/articles.json", {"updated_at":"","articles":[]})
    state = load_blob_json("byelingua/update-state.json", {"next_source":0})
    seen, results, errors = {canonical_url(url) for url in seen_data.get("urls", [])}, [], []
    subscriptions = [item for item in config["subscriptions"] if item.get("enabled", True)]
    if subscription_override is not None:
        subscriptions = [subscription_override]
        source_id = subscription_override["id"]
    elif source_id:
        subscriptions = [item for item in subscriptions if item.get("id") == source_id]
        if not subscriptions:
            raise ValueError(f"Unknown or disabled source: {source_id}")
    start = 0 if source_id else int(state.get("next_source", 0)) % max(len(subscriptions), 1)
    ordered = subscriptions[start:] + subscriptions[:start]
    for offset, subscription in enumerate(ordered):
        try: candidates = collect_new_articles(subscription, seen, 1)
        except Exception as error: errors.append(f"{subscription['name']}: {error}"); continue
        for article in candidates:
            try:
                try:
                    text, page_date = extract_article(article["url"]); article["published"] = article["published"] or page_date
                except Exception:
                    text = article.get("feed_text", "")
                    if len(text) < 200: raise
                original_title = article["title"]
                bilingual = translate_bilingual_article(text, original_title, subscription["mode"])
                item = {**article,"title":bilingual["titles"]["zh"],"result":bilingual["contents"]["zh"],"titles":bilingual["titles"],"contents":bilingual["contents"],"original_title":original_title,"id":hashlib.sha256(article["url"].encode()).hexdigest()[:16],"kind":"subscription","source":subscription["name"],"country":subscription["country"],"language":"bilingual","mode":subscription["mode"],"processed_at":datetime.now(timezone.utc).isoformat()}
                item.pop("feed_text", None); results.append(item); seen.add(article["url"])
            except Exception as error: errors.append(f"{article['title']}: {error}")
        if results:
            if not source_id:
                state["next_source"] = (start + offset + 1) % max(len(subscriptions), 1)
            break
    urls = {item["url"] for item in results}
    merged = results + [item for item in archive.get("articles", []) if item.get("url") not in urls]
    now = datetime.now(timezone.utc).isoformat()
    save_blob_json("byelingua/articles.json", {"updated_at":now,"articles":merged[:MAX_ARTICLES]})
    save_blob_json("byelingua/seen.json", {"urls":list(seen)[:2000]})
    save_blob_json("byelingua/update-state.json", state)
    return {"processed":len(results),"items":len(merged[:MAX_ARTICLES]),"errors":errors[:10],"batch_limit":1,"source":source_id or "round-robin"}


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
    save_blob_json("byelingua/config.json", config)
    try:
        # Use the just-saved source directly. Blob storage may briefly return the
        # previous config, which used to make a new source look "unknown" here.
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
    save_blob_json("byelingua/config.json", config)
    return {"id": identifier, "enabled": subscription["enabled"]}


def public_payload():
    config, archive = load_config(), load_blob_json("byelingua/articles.json", {"updated_at":"","articles":[]})
    articles = sorted(archive.get("articles", []), key=lambda item: item.get("published") or item.get("published_at") or item.get("processed_at") or "", reverse=True)
    return {"target_language":config.get("target_language","zh"),"countries":COUNTRIES,"subscriptions":public_subscriptions(config),"updated_at":archive.get("updated_at",""),"articles":articles}


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
        raise PermissionError("登录已过期，请重新获取验证码。")
    user = response.json()
    if not user.get("id"):
        raise PermissionError("无法识别登录用户。")
    return user


def personal_payload(user_id):
    profile = supabase_service("GET", "/rest/v1/profiles", params={"id":f"eq.{user_id}","select":"*"})
    profile = profile[0] if profile else {}
    subscriptions = supabase_service("GET", "/rest/v1/user_subscriptions", params={"user_id":f"eq.{user_id}","select":"*","order":"created_at.desc"})
    article_params = {"user_id":f"eq.{user_id}","select":"*","order":"processed_at.desc","limit":"200"}
    if profile.get("preferred_language") in LANGUAGES:
        article_params["language"] = f"eq.{profile['preferred_language']}"
    articles = supabase_service("GET", "/rest/v1/user_articles", params=article_params)
    return {"profile":profile,"subscriptions":subscriptions or [],"articles":articles or []}


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
    return rows[0] if rows else record


def delete_personal_subscription(user_id, identifier):
    supabase_service("DELETE", "/rest/v1/user_subscriptions", params={"id":f"eq.{identifier}","user_id":f"eq.{user_id}"})
    return personal_payload(user_id)


def save_personal_language(user_id, language):
    language = str(language or "").lower()
    if language not in LANGUAGES:
        raise ValueError("不支持所选语言。")
    supabase_service("PATCH", "/rest/v1/profiles", params={"id":f"eq.{user_id}"}, payload={"preferred_language":language,"updated_at":datetime.now(timezone.utc).isoformat()})
    supabase_service("PATCH", "/rest/v1/user_subscriptions", params={"user_id":f"eq.{user_id}"}, payload={"language":language,"updated_at":datetime.now(timezone.utc).isoformat()})
    return personal_payload(user_id)


def _run_personal_digest_legacy(user_id):
    personal = personal_payload(user_id)
    profile, subscriptions = personal["profile"], personal["subscriptions"]
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


def run_personal_digest(user_id, automated=False, article_limit=3):
    """Process up to three personal sources using the account's saved language."""
    personal = personal_payload(user_id)
    profile, subscriptions = personal["profile"], personal["subscriptions"]
    if profile.get("status") != "active":
        raise PermissionError("This subscription account is not active.")

    paris_midnight = datetime.now(PARIS_TIMEZONE).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).astimezone(timezone.utc).isoformat()
    if not automated:
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
    processed, errors, characters = 0, [], 0

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
                supabase_service(
                    "POST",
                    "/rest/v1/user_articles",
                    params={"on_conflict":"user_id,canonical_url,language"},
                    payload=record,
                    prefer="resolution=merge-duplicates,return=representation",
                )
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
    return {"processed":processed,"errors":errors[:10],"data":personal_payload(user_id)}


def paris_schedule_due(now=None):
    """Return True only during the 09:00 hour in Europe/Paris."""
    current = now or datetime.now(timezone.utc)
    return current.astimezone(PARIS_TIMEZONE).hour == 9


def run_scheduled_updates():
    """Update public news and all active subscribers once per Paris day."""
    paris_date = datetime.now(PARIS_TIMEZONE).date().isoformat()
    state = load_blob_json("byelingua/scheduled-state.json", {"paris_date":""})
    if state.get("paris_date") == paris_date:
        return {"already_run":True,"paris_date":paris_date,"public_processed":0,"users":0,"personal_processed":0,"errors":[]}

    errors, public_processed, personal_processed = [], 0, 0
    for _ in range(3):
        result = run_daily_digest()
        public_processed += int(result.get("processed", 0))
        errors.extend(result.get("errors", []))

    profiles = supabase_service(
        "GET", "/rest/v1/profiles", params={"status":"eq.active","select":"id"}
    ) or []
    completed_users = 0
    for profile in profiles:
        try:
            result = run_personal_digest(profile["id"], automated=True, article_limit=3)
            personal_processed += int(result.get("processed", 0))
            errors.extend(result.get("errors", []))
            completed_users += 1
        except Exception as error:
            errors.append(f"User {profile.get('id', 'unknown')}: {error}")

    save_blob_json(
        "byelingua/scheduled-state.json",
        {"paris_date":paris_date,"completed_at":datetime.now(timezone.utc).isoformat()},
    )
    return {"already_run":False,"paris_date":paris_date,"public_processed":public_processed,"users":completed_users,"personal_processed":personal_processed,"errors":errors[:20]}


def invite_user(email):
    email = str(email or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("请输入有效邮箱地址。")
    url, _, service = supabase_settings()
    headers = {"apikey":service,"Content-Type":"application/json","User-Agent":"Byelingua-Server/3.0"}
    if not service.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {service}"
    response = SESSION.post(f"{url}/auth/v1/admin/users", json={"email":email,"email_confirm":True,"user_metadata":{"invited":True}}, headers=headers, timeout=20)
    if response.status_code == 422 and "already" in response.text.lower():
        return {"email":email,"existing":True}
    if not response.ok:
        raise ValueError(response.json().get("message") or "创建邀请账户失败。")
    return {"email":email,"existing":False}


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
            if action == "get_auth_config":
                url, publishable, _ = supabase_settings(); self.send_json(200,{"url":url,"publishable_key":publishable}); return
            if action in {"get_my_data","save_my_subscription","delete_my_subscription","run_my_digest","save_my_language"}:
                user = authenticated_user(self.headers)
                if action == "get_my_data": result = personal_payload(user["id"])
                elif action == "save_my_subscription": result = save_personal_subscription(user["id"], data.get("subscription",{}))
                elif action == "delete_my_subscription": result = delete_personal_subscription(user["id"], str(data.get("id","")))
                elif action == "save_my_language": result = save_personal_language(user["id"], data.get("language",""))
                else: result = run_personal_digest(user["id"])
                self.send_json(200,result); return
            require_admin(self.headers); config = load_config()
            if action == "get_config": self.send_json(200, config)
            elif action == "save_settings":
                language = data.get("target_language","zh")
                if language not in LANGUAGES: raise ValueError("不支持所选输出语言。")
                config["target_language"] = language; save_blob_json("byelingua/config.json", config); self.send_json(200, config)
            elif action == "save_subscription":
                self.send_json(200, save_public_subscription(data.get("subscription",{}), data.get("old_id","")))
            elif action == "delete_subscription":
                config["subscriptions"] = [x for x in config["subscriptions"] if x.get("id") != data.get("id","")]; save_blob_json("byelingua/config.json",config); self.send_json(200,config)
            elif action == "set_subscription_enabled": self.send_json(200, set_public_subscription_enabled(str(data.get("id","")), bool(data.get("enabled",False))))
            elif action == "run_subscription": self.send_json(200, run_daily_digest(str(data.get("id",""))))
            elif action == "run_digest": self.send_json(200, run_daily_digest())
            elif action == "import_wechat": self.send_json(200, import_wechat_article(data.get("article",{})))
            elif action == "delete_article": self.send_json(200, delete_article(str(data.get("id","")), bool(data.get("allow_resync",False))))
            elif action == "retranslate_article": self.send_json(200, retranslate_article(str(data.get("id",""))))
            elif action == "invite_user": self.send_json(200, invite_user(data.get("email","")))
            elif action == "backfill_bilingual": self.send_json(200, backfill_bilingual_article())
            else: self.send_json(400, {"error":"未知操作。"})
        except PermissionError as error: self.send_json(401, {"error":str(error)})
        except (ValueError, requests.RequestException) as error: self.send_json(400, {"error":str(error)})
        except Exception as error: self.send_json(500, {"error":str(error)})
