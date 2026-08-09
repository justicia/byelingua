import json
import os
import sys

import requests

from dotenv import load_dotenv

load_dotenv(".env.local")

def supabase_request_settings():
    url = os.environ.get("SUPABASE_URL")
    key = (
        os.environ.get("SUPABASE_SECRET_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    )
    if not url:
        raise RuntimeError("SUPABASE_URL is missing")
    if not key:
        raise RuntimeError(
            "SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY is missing"
        )
    return f"{url.rstrip('/')}/rest/v1/public_articles", {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Content-Profile": "public",
        "Accept-Profile": "public",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }


def first_value(article, *keys):
    raw_data = article.get("raw_data")
    sources = (article, raw_data) if isinstance(raw_data, dict) else (article,)
    for source in sources:
        for key in keys:
            value = source.get(key)

            if value not in (None, "", {}):
                return value

    return None


def json_object(article, key):
    """Prefer populated top-level JSONB data, then fall back to raw_data."""
    value = article.get(key)
    if isinstance(value, dict) and value:
        return value
    raw_data = article.get("raw_data")
    value = raw_data.get(key) if isinstance(raw_data, dict) else None
    return value if isinstance(value, dict) else {}


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

        "kind": first_value(article, "kind"),
        "source": first_value(article, "source"),
        "country": first_value(article, "country"),

        "original_title": first_value(
            article,
            "original_title",
            "title",
        ),

        "title": first_value(article, "title"),

        "author": first_value(article, "author"),

        "author_label": first_value(
            article,
            "author_label",
            "author",
        ),

        "category": first_value(article, "category"),
        "translation_instruction": first_value(
            article,
            "translation_instruction",
        ),

        "published_at": first_value(
            article,
            "published_at",
            "published",
        ),

        "result": first_value(article, "result"),

        "translations": json_object(article, "translations"),
        "translated_titles": json_object(article, "translated_titles"),
        "summaries": json_object(article, "summaries"),
        "translation_jobs": json_object(article, "translation_jobs"),

        "contents": json_object(article, "contents"),
        "titles": json_object(article, "titles"),

        "cover": first_value(article, "cover"),
        "language": first_value(article, "language"),
        "mode": first_value(article, "mode"),

        "processed_at": first_value(article, "processed_at"),

        "metadata_updated_at": first_value(article, "metadata_updated_at"),

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
    api_url, headers = supabase_request_settings()
    response = requests.post(
        api_url,
        headers=headers,
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
