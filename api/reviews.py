from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler

from api.index import (
    SCHEDULE_COUNTRY_NAMES, _cached_supabase_get, _event_internal_id,
    _schedule_venue_directory, authenticated_user, canonical_event_type,
    load_public_article_list, schedule_event_detail, schedule_events, supabase_service,
)


PERSONAL_STATUSES = {"want_to_go", "going", "attended", "not_attended"}
COMPONENT_TYPES = {"conductor", "soloist", "orchestra", "stage"}
CONDUCTOR_ROLES = {
    "conductor", "dirigent", "music_director", "musical_director", "dirección",
}
ORCHESTRA_ROLES = {
    "orchestra", "ensemble", "choir", "chorus", "orquesta", "orchestre",
}
NON_PERFORMER_ROLES = {
    "stage_director", "director", "lighting_designer", "costume_designer",
    "set_designer", "production_designer", "video_designer", "dramaturg",
    "choreographer", "chorus_master", "extras", "composer", "librettist",
    "livret", "musique",
}
STAGED_EVENT_TYPES = {"opera", "operetta", "ballet", "musical", "dance"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _ids(values):
    return [str(value) for value in values if value]


def _in_filter(values):
    clean = list(dict.fromkeys(_ids(values)))
    return f"in.({','.join(clean)})" if clean else "in.()"


def _country_code(value):
    raw = str(value or "").strip().casefold()
    for code, names in SCHEDULE_COUNTRY_NAMES.items():
        if raw == code or raw in {str(name).casefold() for name in names}:
            return code.upper()
    return ""


def _top_venue_countries(available):
    counts = Counter()
    offset = 0
    while True:
        rows = _cached_supabase_get(
            "/rest/v1/venues",
            {"select": "id,country_code", "limit": "1000", "offset": str(offset)},
            ttl=600,
        )
        for row in rows:
            code = _country_code(row.get("country_code"))
            if code:
                counts[code] += 1
        if len(rows) < 1000:
            break
        offset += 1000
    return [
        code for code, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if code in available
    ][:5]


def _related_press(event):
    titles = [
        str(value or "").strip().casefold()
        for value in (event.get("title"), event.get("source_title"), event.get("original_title"))
        if len(str(value or "").strip()) >= 6
    ]
    titles.extend(
        str(row.get("title") or "").strip().casefold()
        for row in event.get("programme") or []
        if len(str(row.get("title") or "").strip()) >= 6
    )
    if not titles:
        return []
    matches = []
    try:
        articles = load_public_article_list()
    except ValueError:
        return matches
    for article in articles:
        url = str(article.get("canonical_url") or article.get("url") or "")
        if not url.startswith(("https://", "http://")):
            continue
        headlines = [
            article.get("title"), article.get("original_title"),
            *(article.get("titles") or {}).values(),
        ]
        if not any(title in str(headline or "").casefold() for title in titles for headline in headlines):
            continue
        matches.append({
            "title": article.get("title") or article.get("original_title"),
            "source": article.get("source"),
            "published_at": article.get("published_at"),
            "url": url,
        })
        if len(matches) == 6:
            break
    return matches


def _rating(value, *, required=False):
    if value in (None, ""):
        if required:
            raise ValueError("Overall rating is required.")
        return None
    number = int(value)
    if number < 1 or number > 5:
        raise ValueError("Ratings must be between 1 and 5.")
    return number


def _event_rows(event_ids):
    event_ids = list(dict.fromkeys(_ids(event_ids)))
    if not event_ids:
        return []
    rows = supabase_service(
        "GET",
        "/rest/v1/events",
        params={
            "id": _in_filter(event_ids),
            "select": "id,event_key,organization_id,venue_id,date,start_time,end_time,event_type,title,original_title,room,status,ticket_url",
            "limit": str(max(100, len(event_ids))),
        },
    ) or []
    organization_ids = _ids(row.get("organization_id") for row in rows)
    venue_ids = _ids(row.get("venue_id") for row in rows)
    organizations = supabase_service(
        "GET", "/rest/v1/organizations",
        params={"id": _in_filter(organization_ids), "select": "id,name", "limit": str(max(100, len(organization_ids)))},
    ) if organization_ids else []
    venues = supabase_service(
        "GET", "/rest/v1/venues",
        params={"id": _in_filter(venue_ids), "select": "id,name,city,country_code", "limit": str(max(100, len(venue_ids)))},
    ) if venue_ids else []
    organization_by_id = {str(row["id"]): row for row in (organizations or [])}
    venue_by_id = {str(row["id"]): row for row in (venues or [])}
    result = []
    for row in rows:
        organization = organization_by_id.get(str(row.get("organization_id")), {})
        venue = venue_by_id.get(str(row.get("venue_id")), {})
        result.append({
            **row,
            "organization": organization.get("name") or "",
            "venue": venue.get("name") or "",
            "city": venue.get("city") or "",
            "country_code": venue.get("country_code") or "",
        })
    return result


def _relation_rows(user_id):
    params = {
        "user_id": f"eq.{user_id}",
        "select": "id,event_id,intent_status,is_planned,attendance_status,ticket_status,personal_status,created_at,updated_at",
        "order": "updated_at.desc",
        "limit": "5000",
    }
    try:
        return supabase_service("GET", "/rest/v1/user_event_relations", params=params) or [], True
    except ValueError as error:
        if "personal_status" not in str(error):
            raise
        params["select"] = "id,event_id,intent_status,is_planned,attendance_status,ticket_status,created_at,updated_at"
        rows = supabase_service("GET", "/rest/v1/user_event_relations", params=params) or []
        return rows, False


def _derived_personal_status(row):
    if row.get("personal_status") in PERSONAL_STATUSES:
        return row["personal_status"]
    attendance = row.get("attendance_status")
    if attendance == "attended":
        return "attended"
    if attendance == "missed":
        return "not_attended"
    if row.get("intent_status") == "must_go" or attendance == "planned":
        return "going"
    return "want_to_go"


def my_schedule(headers):
    user = authenticated_user(headers)
    relations, schema_ready = _relation_rows(user["id"])
    event_ids = _ids(row.get("event_id") for row in relations)
    events = _event_rows(event_ids)
    event_by_id = {str(row["id"]): row for row in events}

    reviews = []
    try:
        if event_ids:
            reviews = supabase_service(
                "GET", "/rest/v1/event_reviews",
                params={
                    "user_id": f"eq.{user['id']}",
                    "event_id": _in_filter(event_ids),
                    "select": "id,event_id,overall_rating,final_score,comment,identity_mode,visibility,updated_at",
                    "limit": "5000",
                },
            ) or []
    except ValueError as error:
        if "event_reviews" not in str(error):
            raise
        schema_ready = False
    review_by_event = {str(row.get("event_id")): row for row in reviews}

    schedules = supabase_service(
        "GET", "/rest/v1/schedules",
        params={
            "user_id": f"eq.{user['id']}",
            "select": "id,title,status,start_date,end_date",
            "order": "updated_at.desc",
            "limit": "500",
        },
    ) or []
    schedule_by_id = {str(row["id"]): row for row in schedules}
    schedule_ids = list(schedule_by_id)
    memberships = supabase_service(
        "GET", "/rest/v1/schedule_events",
        params={
            "schedule_id": _in_filter(schedule_ids),
            "select": "schedule_id,event_id",
            "limit": "10000",
        },
    ) if schedule_ids else []
    trips_by_event = defaultdict(list)
    for membership in memberships or []:
        trip = schedule_by_id.get(str(membership.get("schedule_id")))
        if trip:
            trips_by_event[str(membership.get("event_id"))].append(trip)

    items = []
    for relation in relations:
        event_id = str(relation.get("event_id") or "")
        event = event_by_id.get(event_id)
        if not event:
            continue
        items.append({
            "relation_id": relation.get("id"),
            "personal_status": _derived_personal_status(relation),
            "intent_status": relation.get("intent_status"),
            "attendance_status": relation.get("attendance_status"),
            "event": event,
            "review": review_by_event.get(event_id),
            "trips": trips_by_event.get(event_id, []),
            "updated_at": relation.get("updated_at"),
        })
    items.sort(key=lambda row: ((row["event"].get("date") or ""), (row["event"].get("start_time") or "")), reverse=True)
    return {"items": items, "schema_ready": schema_ready}


def set_personal_status(headers, event_key, status):
    user = authenticated_user(headers)
    status = str(status or "").strip()
    if status not in PERSONAL_STATUSES:
        raise ValueError("Invalid My Schedule status.")
    event_id = _event_internal_id(str(event_key or "").strip())
    compatibility = {
        "want_to_go": {"intent_status": "interested", "attendance_status": None},
        "going": {"intent_status": "must_go", "attendance_status": "planned"},
        "attended": {"intent_status": "must_go", "attendance_status": "attended"},
        "not_attended": {"intent_status": "interested", "attendance_status": "missed"},
    }[status]
    payload = {
        "user_id": user["id"],
        "event_id": event_id,
        "personal_status": status,
        "is_planned": True,
        "updated_at": _now(),
        **compatibility,
    }
    try:
        rows = supabase_service(
            "POST", "/rest/v1/user_event_relations",
            params={"on_conflict": "user_id,event_id"}, payload=payload,
            prefer="resolution=merge-duplicates,return=representation",
        ) or []
        return {"relation": rows[0] if rows else payload, "schema_ready": True}
    except ValueError as error:
        if "personal_status" not in str(error):
            raise
        legacy = dict(payload)
        legacy.pop("personal_status", None)
        rows = supabase_service(
            "POST", "/rest/v1/user_event_relations",
            params={"on_conflict": "user_id,event_id"}, payload=legacy,
            prefer="resolution=merge-duplicates,return=representation",
        ) or []
        return {"relation": rows[0] if rows else legacy, "schema_ready": False}


def delete_personal_record(headers, event_key):
    user = authenticated_user(headers)
    event_id = _event_internal_id(str(event_key or "").strip())
    owner_filter = {"user_id": f"eq.{user['id']}", "event_id": f"eq.{event_id}"}
    # The review owns its component ratings through an ON DELETE CASCADE key.
    # Older installations may not have the review table yet.
    try:
        supabase_service("DELETE", "/rest/v1/event_reviews", params=owner_filter, prefer="return=minimal")
    except ValueError as error:
        message = str(error).lower()
        if "event_reviews" not in message or not any(text in message for text in ("could not find the table", "does not exist")):
            raise
    supabase_service("DELETE", "/rest/v1/user_event_relations", params=owner_filter, prefer="return=minimal")
    return {"deleted": True}


def _credits_for_event(event_id):
    credits = supabase_service(
        "GET", "/rest/v1/event_credits",
        params={
            "event_id": f"eq.{event_id}",
            "select": "id,event_id,artist_id,role,character,raw_character",
            "limit": "500",
        },
    ) or []
    artist_ids = _ids(row.get("artist_id") for row in credits)
    artists = supabase_service(
        "GET", "/rest/v1/artists",
        params={"id": _in_filter(artist_ids), "select": "id,artist_name,entity_type", "limit": str(max(500, len(artist_ids)))},
    ) if artist_ids else []
    artist_by_id = {str(row["id"]): row for row in (artists or [])}
    result = []
    for credit in credits:
        artist = artist_by_id.get(str(credit.get("artist_id")), {})
        role = str(credit.get("role") or "").strip()
        normalized = role.casefold().replace(" ", "_")
        if normalized in CONDUCTOR_ROLES:
            component = "conductor"
        elif normalized in ORCHESTRA_ROLES:
            component = "orchestra"
        elif normalized in NON_PERFORMER_ROLES:
            component = "team"
        else:
            component = "soloist"
        result.append({
            **credit,
            "artist_name": artist.get("artist_name") or "",
            "entity_type": artist.get("entity_type"),
            "component_type": component,
        })
    return result


def review_editor(headers, event_key):
    user = authenticated_user(headers)
    event_id = _event_internal_id(str(event_key or "").strip())
    event_rows = _event_rows([event_id])
    if not event_rows:
        raise ValueError("Event not found.")
    event = event_rows[0]
    credits = _credits_for_event(event_id)
    stage_applicable = (
        str(event.get("event_type") or "").casefold() in STAGED_EVENT_TYPES
        or any(row.get("component_type") == "team" and str(row.get("role") or "").casefold() in {"stage_director", "director"} for row in credits)
    )
    try:
        reviews = supabase_service(
            "GET", "/rest/v1/event_reviews",
            params={
                "user_id": f"eq.{user['id']}", "event_id": f"eq.{event_id}",
                "select": "id,event_id,overall_rating,final_score,comment,identity_mode,visibility,updated_at",
                "limit": "1",
            },
        ) or []
        review = reviews[0] if reviews else None
        ratings = supabase_service(
            "GET", "/rest/v1/user_event_component_ratings",
            params={
                "user_id": f"eq.{user['id']}", "event_id": f"eq.{event_id}",
                "select": "id,review_id,component_type,event_credit_id,artist_id,rating",
                "order": "component_type.asc",
                "limit": "500",
            },
        ) or []
        schema_ready = True
    except ValueError as error:
        if "event_reviews" not in str(error) and "user_event_component_ratings" not in str(error):
            raise
        review, ratings, schema_ready = None, [], False
    return {
        "event": event,
        "credits": [row for row in credits if row.get("component_type") != "team"],
        "stage_applicable": stage_applicable,
        "review": review,
        "ratings": ratings,
        "schema_ready": schema_ready,
    }


def _final_score(overall_rating, component_rows):
    grouped = defaultdict(list)
    for row in component_rows:
        grouped[row["component_type"]].append(row["rating"])
    category_scores = [sum(values) / len(values) for values in grouped.values() if values]
    if not category_scores:
        return float(overall_rating)
    component_average = sum(category_scores) / len(category_scores)
    return round((float(overall_rating) + component_average) / 2, 1)


def save_review(headers, data):
    user = authenticated_user(headers)
    event_key = str(data.get("event_key") or "").strip()
    event_id = _event_internal_id(event_key)
    overall = _rating(data.get("overall_rating"), required=True)
    identity_mode = str(data.get("identity_mode") or "anonymous").strip()
    if identity_mode not in {"anonymous", "public"}:
        raise ValueError("Invalid identity mode.")
    visibility = str(data.get("visibility") or "public").strip()
    if visibility not in {"private", "public"}:
        raise ValueError("Invalid visibility.")
    comment = str(data.get("comment") or "").strip()[:6000]

    credits = _credits_for_event(event_id)
    credit_by_id = {str(row["id"]): row for row in credits}
    component_rows = []
    seen = set()
    for raw in data.get("components") or []:
        component_type = str(raw.get("component_type") or "").strip()
        if component_type not in COMPONENT_TYPES:
            raise ValueError("Invalid review component.")
        rating = _rating(raw.get("rating"), required=True)
        if component_type == "stage":
            key = ("stage", "")
            if key in seen:
                continue
            seen.add(key)
            component_rows.append({
                "component_type": "stage", "event_credit_id": None,
                "artist_id": None, "rating": rating,
            })
            continue
        credit_id = str(raw.get("event_credit_id") or "").strip()
        credit = credit_by_id.get(credit_id)
        if not credit:
            raise ValueError("A rated performer does not belong to this event.")
        if credit.get("component_type") != component_type:
            raise ValueError("A rated performer has the wrong review component type.")
        key = (component_type, credit_id)
        if key in seen:
            continue
        seen.add(key)
        component_rows.append({
            "component_type": component_type,
            "event_credit_id": credit_id,
            "artist_id": credit.get("artist_id"),
            "rating": rating,
        })

    final_score = _final_score(overall, component_rows)
    now = _now()
    review_payload = {
        "user_id": user["id"], "event_id": event_id,
        "rating": overall, "overall_rating": overall,
        "review_text": comment, "comment": comment,
        "final_score": final_score, "identity_mode": identity_mode,
        "visibility": visibility, "updated_at": now,
    }
    reviews = supabase_service(
        "POST", "/rest/v1/event_reviews",
        params={"on_conflict": "user_id,event_id"}, payload=review_payload,
        prefer="resolution=merge-duplicates,return=representation",
    ) or []
    if not reviews:
        reviews = supabase_service(
            "GET", "/rest/v1/event_reviews",
            params={"user_id": f"eq.{user['id']}", "event_id": f"eq.{event_id}", "select": "id", "limit": "1"},
        ) or []
    if not reviews:
        raise RuntimeError("Review could not be saved.")
    review_id = reviews[0]["id"]

    supabase_service(
        "DELETE", "/rest/v1/user_event_component_ratings",
        params={"user_id": f"eq.{user['id']}", "event_id": f"eq.{event_id}"},
        prefer="return=minimal",
    )
    if component_rows:
        payload = [{
            **row, "review_id": review_id, "user_id": user["id"],
            "event_id": event_id, "created_at": now, "updated_at": now,
        } for row in component_rows]
        supabase_service(
            "POST", "/rest/v1/user_event_component_ratings",
            payload=payload, prefer="return=minimal",
        )

    set_personal_status(headers, event_key, "attended")
    return {
        "review": {
            "id": review_id, "overall_rating": overall,
            "final_score": final_score, "comment": comment,
            "identity_mode": identity_mode, "visibility": visibility,
        },
        "components": component_rows,
    }


def public_event_reviews(event_key):
    event_id = _event_internal_id(str(event_key or "").strip())
    event_rows = _event_rows([event_id])
    if not event_rows:
        raise ValueError("Event not found.")
    event = {**event_rows[0], "country_code": _country_code(event_rows[0].get("country_code"))}
    credits = [row for row in _credits_for_event(event_id) if row.get("component_type") != "team"]
    try:
        detail = schedule_event_detail(str(event_key or "").strip()).get("event") or {}
    except ValueError:
        detail = {}
    related_press = _related_press(detail or event)
    try:
        reviews = supabase_service(
            "GET", "/rest/v1/event_reviews",
            params={
                "event_id": f"eq.{event_id}", "visibility": "eq.public",
                "select": "id,user_id,overall_rating,final_score,comment,identity_mode,updated_at",
                "order": "updated_at.desc", "limit": "500",
            },
        ) or []
    except ValueError as error:
        if "event_reviews" in str(error):
            return {"event": event, "detail": detail, "related_press": related_press, "credits": credits, "summary": {"rating_count": 0, "average_rating": None, "average_final_score": None}, "reviews": [], "component_summary": [], "category_summary": [], "schema_ready": False}
        raise

    public_user_ids = _ids(row.get("user_id") for row in reviews if row.get("identity_mode") == "public")
    profiles = supabase_service(
        "GET", "/rest/v1/profiles",
        params={"id": _in_filter(public_user_ids), "select": "id,display_name", "limit": str(max(100, len(public_user_ids)))},
    ) if public_user_ids else []
    display_name_by_id = {str(row["id"]): (row.get("display_name") or "Member") for row in (profiles or [])}

    review_ids = _ids(row.get("id") for row in reviews)
    ratings = supabase_service(
        "GET", "/rest/v1/user_event_component_ratings",
        params={
            "review_id": _in_filter(review_ids),
            "select": "review_id,component_type,event_credit_id,artist_id,rating",
            "limit": "10000",
        },
    ) if review_ids else []

    sanitized = []
    for row in reviews:
        author = "Anonymous"
        if row.get("identity_mode") == "public":
            author = display_name_by_id.get(str(row.get("user_id")), "Member")
        sanitized.append({
            "overall_rating": row.get("overall_rating"),
            "final_score": row.get("final_score"),
            "comment": row.get("comment") or "",
            "author": {"mode": row.get("identity_mode") or "anonymous", "display_name": author},
            "updated_at": row.get("updated_at"),
        })

    overall_values = [float(row["overall_rating"]) for row in reviews if row.get("overall_rating") is not None]
    final_values = [float(row["final_score"]) for row in reviews if row.get("final_score") is not None]
    component_groups = defaultdict(list)
    review_category_groups = defaultdict(list)
    for row in ratings or []:
        review_category_groups[(row.get("review_id"), row.get("component_type"))].append(float(row["rating"]))
        key = (row.get("component_type"), row.get("artist_id"), row.get("event_credit_id"))
        component_groups[key].append(float(row["rating"]))
    component_summary = [{
        "component_type": key[0], "artist_id": key[1], "event_credit_id": key[2],
        "average_rating": round(sum(values) / len(values), 2), "rating_count": len(values),
    } for key, values in component_groups.items()]

    category_groups = defaultdict(list)
    for (_, category), values in review_category_groups.items():
        category_groups[category].append(sum(values) / len(values))
    category_summary = [
        {"component_type": category, "average_rating": round(sum(values) / len(values), 2), "rating_count": len(values)}
        for category, values in category_groups.items()
    ]

    return {
        "event": event,
        "detail": detail,
        "related_press": related_press,
        "credits": credits,
        "summary": {
            "rating_count": len(reviews),
            "average_rating": round(sum(overall_values) / len(overall_values), 2) if overall_values else None,
            "average_final_score": round(sum(final_values) / len(final_values), 2) if final_values else None,
        },
        "reviews": sanitized,
        "component_summary": component_summary,
        "category_summary": category_summary,
        "schema_ready": True,
    }


def my_reviews(headers):
    user = authenticated_user(headers)
    try:
        reviews = supabase_service(
            "GET", "/rest/v1/event_reviews",
            params={
                "user_id": f"eq.{user['id']}",
                "select": "event_id,overall_rating,final_score,comment,visibility,identity_mode,updated_at",
                "order": "updated_at.desc", "limit": "500",
            },
        ) or []
    except ValueError as error:
        if "event_reviews" in str(error):
            return {"reviews": [], "schema_ready": False}
        raise
    events = {str(row["id"]): row for row in _event_rows(row.get("event_id") for row in reviews)}
    return {
        "reviews": [
            {
                "event": events.get(str(row.get("event_id"))),
                "overall_rating": row.get("overall_rating"),
                "final_score": row.get("final_score"),
                "comment": row.get("comment") or "",
                "visibility": row.get("visibility"),
                "identity_mode": row.get("identity_mode"),
                "updated_at": row.get("updated_at"),
            }
            for row in reviews if events.get(str(row.get("event_id")))
        ],
        "schema_ready": True,
    }


def public_review_home():
    today = datetime.now(timezone.utc).date()
    featured = []
    seen = set()
    country_by_venue = {}
    try:
        rows = schedule_events({
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=30)).isoformat(),
        }).get("events") or []
        country_by_venue = _schedule_venue_directory()[1]
        for row in rows:
            signature = (row.get("title"), row.get("organization"), row.get("venue"))
            if signature in seen:
                continue
            seen.add(signature)
            featured.append({
                "event_key": row.get("event_id"), "title": row.get("title"),
                "date": row.get("date"), "start_time": row.get("start_time"),
                "event_type": row.get("event_type"),
                "organization": row.get("organization"), "venue": row.get("venue"),
                "city": row.get("city"),
                "country_code": _country_code(row.get("country_code") or country_by_venue.get(str(row.get("venue") or "").strip().casefold(), "")),
            })
            if len(featured) == 80:
                break
    except ValueError:
        pass

    press = []
    try:
        for row in load_public_article_list():
            category = str(row.get("category") or "").lower()
            if not any(word in category for word in ("opera", "concert", "music", "classical", "review", "歌剧", "音乐", "评论")):
                continue
            url = row.get("canonical_url") or row.get("url") or ""
            if not str(url).startswith(("https://", "http://")):
                continue
            press.append({
                "title": row.get("title") or row.get("original_title"),
                "source": row.get("source"), "published_at": row.get("published_at"),
                "url": url,
            })
            if len(press) == 6:
                break
    except ValueError:
        pass

    press_titles = [str(row.get("title") or "").casefold() for row in press]
    for row in featured:
        title = str(row.get("title") or "").strip().casefold()
        row["work_in_press"] = len(title) >= 6 and any(title in article for article in press_titles)
    featured.sort(key=lambda row: (not row["work_in_press"], str(row.get("date") or "")))
    featured = featured[:80]
    try:
        top_countries = _top_venue_countries({row["country_code"] for row in featured if row["country_code"]}) if featured else []
    except ValueError:
        venue_counts = Counter(_country_code(code) for code in country_by_venue.values())
        top_countries = [
            code for code, _ in venue_counts.most_common()
            if code and any(row["country_code"] == code for row in featured)
        ][:5]

    try:
        reviews = supabase_service(
            "GET", "/rest/v1/event_reviews",
            params={
                "visibility": "eq.public",
                "select": "event_id,overall_rating,final_score,updated_at",
                "order": "updated_at.desc", "limit": "1000",
            },
        ) or []
    except ValueError as error:
        if "event_reviews" in str(error):
            return {"featured": featured, "top_countries": top_countries, "press": press, "hot": [], "top_rated": [], "schema_ready": False}
        raise
    events = {str(row["id"]): row for row in _event_rows(row.get("event_id") for row in reviews)}
    grouped = defaultdict(list)
    for row in reviews:
        event = events.get(str(row.get("event_id")))
        if event:
            grouped[str(row["event_id"])].append(row)
    cards = []
    for event_id, values in grouped.items():
        event = events[event_id]
        scores = [float(row["final_score"]) for row in values if row.get("final_score") is not None]
        if not scores:
            scores = [float(row["overall_rating"]) for row in values if row.get("overall_rating") is not None]
        cards.append({
            "event_key": event.get("event_key"), "title": event.get("title") or event.get("original_title"),
            "date": event.get("date"), "organization": event.get("organization"),
            "venue": event.get("venue"), "city": event.get("city"),
            "country_code": _country_code(event.get("country_code")),
            "event_type": canonical_event_type(event.get("event_type")),
            "rating_count": len(values),
            "average_score": round(sum(scores) / len(scores), 1) if scores else None,
            "latest_review_at": max(str(row.get("updated_at") or "") for row in values),
        })
    hot = sorted(cards, key=lambda row: (row["rating_count"], row["latest_review_at"]), reverse=True)[:6]
    top_rated = sorted(
        (row for row in cards if row["rating_count"] >= 3),
        key=lambda row: (row["average_score"] or 0, row["rating_count"]), reverse=True,
    )[:6]
    return {"featured": featured, "top_countries": top_countries, "press": press, "hot": hot, "top_rated": top_rated, "schema_ready": True}


def public_artist_rating(artist_id):
    artist_id = str(artist_id or "").strip()
    if not artist_id:
        raise ValueError("Artist id is required.")
    try:
        ratings = supabase_service(
            "GET", "/rest/v1/user_event_component_ratings",
            params={"artist_id": f"eq.{artist_id}", "select": "review_id,event_id,rating,component_type", "limit": "10000"},
        ) or []
    except ValueError as error:
        if "user_event_component_ratings" in str(error):
            return {"artist_id": artist_id, "average_rating": None, "rating_count": 0, "schema_ready": False}
        raise
    review_ids = _ids(row.get("review_id") for row in ratings)
    public_reviews = supabase_service(
        "GET", "/rest/v1/event_reviews",
        params={"id": _in_filter(review_ids), "visibility": "eq.public", "select": "id", "limit": "10000"},
    ) if review_ids else []
    allowed = {str(row["id"]) for row in (public_reviews or [])}
    values = [float(row["rating"]) for row in ratings if str(row.get("review_id")) in allowed]
    return {
        "artist_id": artist_id,
        "average_rating": round(sum(values) / len(values), 2) if values else None,
        "rating_count": len(values),
        "schema_ready": True,
    }


class handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            action = str(data.get("action") or "").strip()
            if action == "my_schedule":
                self.send_json(200, my_schedule(self.headers)); return
            if action == "set_personal_status":
                self.send_json(200, set_personal_status(self.headers, data.get("event_key"), data.get("status"))); return
            if action == "delete_personal_record":
                self.send_json(200, delete_personal_record(self.headers, data.get("event_key"))); return
            if action == "review_editor":
                self.send_json(200, review_editor(self.headers, data.get("event_key"))); return
            if action == "save_review":
                self.send_json(200, save_review(self.headers, data)); return
            if action == "my_reviews":
                self.send_json(200, my_reviews(self.headers)); return
            if action == "public_review_home":
                self.send_json(200, public_review_home()); return
            if action == "public_event_reviews":
                self.send_json(200, public_event_reviews(data.get("event_key"))); return
            if action == "public_artist_rating":
                self.send_json(200, public_artist_rating(data.get("artist_id"))); return
            self.send_json(400, {"error": "Unknown review action."})
        except PermissionError as error:
            self.send_json(401, {"error": str(error)})
        except ValueError as error:
            self.send_json(400, {"error": str(error)})
        except Exception as error:
            self.send_json(500, {"error": str(error)})
