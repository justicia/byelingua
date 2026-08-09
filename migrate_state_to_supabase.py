import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv(".env.local")

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=representation",
}


def read_json(filename):
    path = Path(filename)

    if not path.exists():
        raise FileNotFoundError(f"Missing file: {filename}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def upsert_app_state(key, value):
    url = f"{SUPABASE_URL}/rest/v1/public_app_state"

    payload = {
        "key": key,
        "value": value,
    }

    response = requests.post(
        url,
        params={"on_conflict": "key"},
        headers=HEADERS,
        json=payload,
        timeout=30,
    )

    if not response.ok:
        print(f"\nFailed app state: {key}")
        print(response.status_code)
        print(response.text)
        response.raise_for_status()

    print(f"Uploaded app state: {key}")


def migrate_seen_urls(data):
    urls = data.get("urls", [])

    if not urls:
        print("No seen URLs found.")
        return

    endpoint = f"{SUPABASE_URL}/rest/v1/public_seen_urls"

    rows = [{"url": url} for url in urls if url]

    response = requests.post(
        endpoint,
        params={"on_conflict": "url"},
        headers=HEADERS,
        json=rows,
        timeout=30,
    )

    if not response.ok:
        print("\nFailed seen URL migration")
        print(response.status_code)
        print(response.text)
        response.raise_for_status()

    print(f"Uploaded seen URLs: {len(rows)}")


def upsert_scheduled_state(key, value):
    url = f"{SUPABASE_URL}/rest/v1/public_scheduled_state"

    payload = {
        "key": key,
        "value": value,
    }

    response = requests.post(
        url,
        params={"on_conflict": "key"},
        headers=HEADERS,
        json=payload,
        timeout=30,
    )

    if not response.ok:
        print(f"\nFailed scheduled state: {key}")
        print(response.status_code)
        print(response.text)
        response.raise_for_status()

    print(f"Uploaded scheduled state: {key}")


def main():
    print("Reading backup files...")

    config = read_json("config_backup.json")
    seen = read_json("seen_backup.json")
    update_state = read_json("update_state_backup.json")
    scheduled_state = read_json("scheduled_state_backup.json")

    print("Backup files loaded.")

    upsert_app_state("config", config)
    upsert_app_state("update_state", update_state)

    migrate_seen_urls(seen)

    upsert_scheduled_state("daily_update", scheduled_state)

    print("\nState migration finished successfully.")


if __name__ == "__main__":
    main()