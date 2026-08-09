import json
import os
import sys

import requests

from dotenv import load_dotenv

load_dotenv(".env.local")

SUPABASE_URL = os.environ.get("SUPABASE_URL")

SUPABASE_KEY = (
    os.environ.get("SUPABASE_SECRET_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
)

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing")

if not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY is missing"
    )


API_URL = f"{SUPABASE_URL}/rest/v1/public_articles"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Content-Profile": "public",
    "Accept-Profile": "public",
    "Prefer": "resolution=merge-duplicates,return=minimal",
}


def first_value(article, *keys):
    for key in keys:
        value = article.get(key)

        if value not in (None, ""):
            return value

    return None


def normalize_article(article):
    article_id = str(
        first_value(
            article,
            "id",
            "key",
            "article_id",
        )
        or ""
    ).strip()

    if not article_id:
        print("SKIP: article has no id")
        return None

    url = first_value(
        article,
        "url",
        "original_url",
        "canonical_url",
    )

    if not url:
        print(f"SKIP {article_id}: article has no URL")
        return None

    return {
        "id": article_id,

        "canonical_url": first_value(
            article,
            "canonical_url",
            "url",
            "original_url",
        ),

        "url": url,

        "kind": article.get("kind"),
        "source": article.get("source"),
        "country": article.get("country"),

        "original_title": first_value(
            article,
            "original_title",
            "title",
        ),

        "title": article.get("title"),

        "author_label": first_value(
            article,
            "author_label",
            "author",
        ),

        "category": article.get("category"),

        "published_at": first_value(
            article,
            "published_at",
            "published",
        ),

        "result": article.get("result"),

        "translations": article.get("translations") or {},
        "translated_titles": article.get("translated_titles") or {},
        "summaries": article.get("summaries") or {},
        "translation_jobs": article.get("translation_jobs") or {},

        "contents": article.get("contents") or {},
        "titles": article.get("titles") or {},

        "cover": article.get("cover"),
        "language": article.get("language"),
        "mode": article.get("mode"),

        "processed_at": article.get("processed_at"),

        "metadata_updated_at": article.get(
            "metadata_updated_at"
        ),

        "raw_data": article,
    }


def load_articles(filename):
    with open(filename, "r", encoding="utf-8") as file:
        payload = json.load(file)

    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        articles = payload.get("articles")

        if isinstance(articles, list):
            return articles

    raise RuntimeError(
        "Cannot find article list in JSON file"
    )


def upload_batch(rows):
    response = requests.post(
        API_URL,
        headers=HEADERS,
        json=rows,
        timeout=60,
    )

    if not response.ok:
        print("\nSupabase returned an error:")
        print("Status:", response.status_code)
        print(response.text)
        response.raise_for_status()


def main():
    filename = "articles_backup.json"

    if len(sys.argv) > 1:
        filename = sys.argv[1]

    print(f"Reading {filename} ...")

    articles = load_articles(filename)

    print(f"Loaded {len(articles)} articles")

    rows = []

    for article in articles:
        row = normalize_article(article)

        if row:
            rows.append(row)

    print(f"Prepared {len(rows)} rows")

    if not rows:
        print("Nothing to migrate.")
        return

    batch_size = 25

    for start in range(
        0,
        len(rows),
        batch_size,
    ):
        batch = rows[
            start:start + batch_size
        ]

        upload_batch(batch)

        finished = min(
            start + batch_size,
            len(rows),
        )

        print(
            f"Uploaded {finished}/{len(rows)}"
        )

    print("\nMigration finished successfully.")


if __name__ == "__main__":
    main()