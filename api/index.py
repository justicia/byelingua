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
from urllib.parse import urljoin, urlsplit, urlunsplit

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
    response = SESSION.get(url, timeout=(10,30))
    response.raise_for_status()
    return response


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
    try:
        soup = BeautifulSoup(fetch(normalized).content, "html.parser")
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
    except Exception:
        if not manual_text.strip():
            raise ValueError("微信暂时阻止了自动读取，请把文章正文粘贴到备用正文框。")
    text, title = manual_text.strip() or extracted, manual_title.strip() or title
    author = manual_author.strip() or author or "微信公众号"
    if len(text) < 200:
        raise ValueError("未读取到足够正文，请粘贴完整文章内容。")
    if not title:
        raise ValueError("未读取到标题，请填写备用标题。")
    return {"title":title,"source":author,"url":normalized,"published":published,"cover":cover,"text":text}


def translate_article(text, language_code, mode):
    language = LANGUAGES.get(language_code, LANGUAGES["zh"])
    instruction = (f"用{language}写一段准确自然的新闻摘要，约150至250字。只使用原文事实，保留专有名词，不要套话，只输出摘要。" if mode == "summary" else f"将正文完整翻译成{language}。保持原意与段落，准确保留专有名词，不要解释或删减，只输出译文。")
    return OpenAI(api_key=os.environ.get("OPENAI_API_KEY")).responses.create(model=MODEL, input=f"{instruction}\n\n正文：\n{text}").output_text.strip()


def import_wechat_article(data):
    language = str(data.get("language", "")).lower()
    if language not in LANGUAGES:
        raise ValueError("请选择一种目标语言。")
    url = normalize_wechat_url(str(data.get("url", "")))
    archive = load_blob_json("byelingua/articles.json", {"updated_at":"","articles":[]})
    articles, existing = archive.get("articles", []), None
    existing = next((item for item in articles if item.get("url") == url), None)
    if existing and language in existing.get("translations", {}):
        return {"article":existing,"reused":True}
    wechat = extract_wechat_article(url, str(data.get("text", "")), str(data.get("title", "")), str(data.get("author", "")))
    translation = translate_article(wechat.pop("text"), language, "translate")
    translations = dict(existing.get("translations", {})) if existing else {}
    translations[language] = translation
    now = datetime.now(timezone.utc).isoformat()
    item = {**(existing or {}),**wechat,"id":hashlib.sha256(url.encode()).hexdigest()[:16],"kind":"wechat","country":"cn","language":language,"mode":"translate","translations":translations,"result":translation,"processed_at":now}
    save_blob_json("byelingua/articles.json", {"updated_at":now,"articles":([item]+[x for x in articles if x.get("url") != url])[:MAX_ARTICLES]})
    return {"article":item,"reused":False}


def delete_article(identifier):
    archive = load_blob_json("byelingua/articles.json", {"updated_at":"","articles":[]})
    articles = [item for item in archive.get("articles", []) if item.get("id") != identifier]
    save_blob_json("byelingua/articles.json", {"updated_at":datetime.now(timezone.utc).isoformat(),"articles":articles})
    return {"deleted":identifier,"items":len(articles)}


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


def run_daily_digest():
    config, seen_data = load_config(), load_blob_json("byelingua/seen.json", {"urls":[]})
    archive = load_blob_json("byelingua/articles.json", {"updated_at":"","articles":[]})
    seen, results, errors = {canonical_url(url) for url in seen_data.get("urls", [])}, [], []
    for subscription in config["subscriptions"]:
        if not subscription.get("enabled", True): continue
        try: candidates = collect_new_articles(subscription, seen)
        except Exception as error: errors.append(f"{subscription['name']}: {error}"); continue
        language = subscription.get("language") or config["target_language"]
        for article in candidates:
            try:
                try:
                    text, page_date = extract_article(article["url"]); article["published"] = article["published"] or page_date
                except Exception:
                    text = article.get("feed_text", "")
                    if len(text) < 200: raise
                result = translate_article(text, language, subscription["mode"])
                item = {**article,"id":hashlib.sha256(article["url"].encode()).hexdigest()[:16],"kind":"subscription","source":subscription["name"],"country":subscription["country"],"language":language,"mode":subscription["mode"],"result":result,"processed_at":datetime.now(timezone.utc).isoformat()}
                item.pop("feed_text", None); results.append(item); seen.add(article["url"])
            except Exception as error: errors.append(f"{article['title']}: {error}")
    urls = {item["url"] for item in results}
    merged = results + [item for item in archive.get("articles", []) if item.get("url") not in urls]
    now = datetime.now(timezone.utc).isoformat()
    save_blob_json("byelingua/articles.json", {"updated_at":now,"articles":merged[:MAX_ARTICLES]})
    save_blob_json("byelingua/seen.json", {"urls":list(seen)[:2000]})
    return {"processed":len(results),"items":len(merged[:MAX_ARTICLES]),"errors":errors[:10]}


def public_payload():
    config, archive = load_config(), load_blob_json("byelingua/articles.json", {"updated_at":"","articles":[]})
    return {"target_language":config.get("target_language","zh"),"countries":COUNTRIES,"updated_at":archive.get("updated_at",""),"articles":archive.get("articles",[])}


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
            require_admin(self.headers); config = load_config()
            if action == "get_config": self.send_json(200, config)
            elif action == "save_settings":
                language = data.get("target_language","zh")
                if language not in LANGUAGES: raise ValueError("不支持所选输出语言。")
                config["target_language"] = language; save_blob_json("byelingua/config.json", config); self.send_json(200, config)
            elif action == "save_subscription":
                sub = validate_subscription(data.get("subscription",{})); config["subscriptions"] = [x for x in config["subscriptions"] if x.get("id") != sub["id"]] + [sub]; save_blob_json("byelingua/config.json",config); self.send_json(200,config)
            elif action == "delete_subscription":
                config["subscriptions"] = [x for x in config["subscriptions"] if x.get("id") != data.get("id","")]; save_blob_json("byelingua/config.json",config); self.send_json(200,config)
            elif action == "run_digest": self.send_json(200, run_daily_digest())
            elif action == "import_wechat": self.send_json(200, import_wechat_article(data.get("article",{})))
            elif action == "delete_article": self.send_json(200, delete_article(str(data.get("id",""))))
            else: self.send_json(400, {"error":"未知操作。"})
        except PermissionError as error: self.send_json(401, {"error":str(error)})
        except (ValueError, requests.RequestException) as error: self.send_json(400, {"error":str(error)})
        except Exception as error: self.send_json(500, {"error":str(error)})
