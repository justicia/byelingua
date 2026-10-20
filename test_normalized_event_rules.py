from api.index import canonical_event_type, canonical_work_title, normalize_search_key, normalized_programme, search_match_score
from unittest.mock import patch
from api.index import schedule_event_detail


def test_accent_insensitive_search():
    assert search_match_score("francois", "François") >= 0.8
    assert search_match_score("opera", "Opéra") >= 0.8
    assert search_match_score("theatre", "Théâtre") >= 0.8
    assert search_match_score("oeuvre", "œuvre") >= 0.8


def test_opera_classification():
    assert canonical_event_type("Festival RING") == "opera"
    assert canonical_event_type("Opéra") == "opera"
    assert canonical_event_type("Concert et Récital") in {"concert", "recital"}


def test_paris_opera_programme_rejects_editorial_and_media_rows():
    event = {"title": "Le Crépuscule des dieux (Festival RING)", "event_type": "Festival RING"}
    rows = [
        {"order": 1, "works": {"title": "Troisième journée en trois actes de L'Anneau du Nibelung", "composer": None}},
        {"order": 2, "works": {"title": "1876", "composer": None}},
        {"order": 3, "works": {"title": "Le Crépuscule des dieux 4:13 min", "composer": None}},
        {"order": 4, "works": {"title": "Richard Wagner", "composer": None}},
        {"order": 5, "works": {"title": "Siegfried 3:21 min", "composer": None}},
        {"order": 6, "works": {"title": "Les leitmotive du Ring #4", "composer": None}},
        {"order": 7, "works": {"title": "Le Crépuscule des dieux", "composer": "Richard Wagner"}},
        {"order": 8, "works": {"title": "Le Crépuscule des dieux (Festival RING)", "composer": "Richard Wagner"}},
    ]
    assert normalized_programme(event, rows) == [
        {"order": 1, "title": "Götterdämmerung", "composer": "Richard Wagner"}
    ]


def test_work_titles_use_the_original_language():
    assert canonical_work_title("Le Crépuscule des dieux") == "Götterdämmerung"
    assert canonical_work_title("Le Barbier de Séville") == "Il barbiere di Siviglia"
    assert canonical_work_title("Hamlet") == "Hamlet"


def reviewed_work(title, composer, **changes):
    work = {"id": "work-1", "title": title, "composer": composer,
            "composer_id": "composer-1", "normalization_status": "verified", "work_kind": "work"}
    return {**work, **changes}


def test_reviewed_opera_programme_survives_official_marketing_titles():
    for title, work_title, composer in [
        ("Wagner: Siegfried / Daniel Harding", "Siegfried", "Richard Wagner"),
        ("Daniel Harding / Leoncavallo: Pagliacci", "Pagliacci", "Ruggero Leoncavallo"),
        ("Jan Willem de Vriend mit Rossini", "La scala di seta", "Gioachino Rossini"),
    ]:
        rows = [{"order": 1, "works": reviewed_work(work_title, composer)}]
        assert normalized_programme({"title": title, "event_type": "opera"}, rows) == [
            {"order": 1, "title": work_title, "composer": composer}
        ]


def test_reviewed_opera_programme_preserves_multiple_works_and_unicode():
    rows = [
        {"order": 2, "works": reviewed_work("Леди Макбет Мценского уезда", "Dmitri Shostakovich")},
        {"order": 4, "works": reviewed_work("Царская невеста", "Nikolai Rimsky-Korsakov", id="work-2")},
    ]
    assert normalized_programme({"title": "Operatic double bill", "event_type": "opera"}, rows) == [
        {"order": 2, "title": "Леди Макбет Мценского уезда", "composer": "Dmitri Shostakovich"},
        {"order": 4, "title": "Царская невеста", "composer": "Nikolai Rimsky-Korsakov"},
    ]


def test_reviewed_path_rejects_unresolved_and_nonwork_rows():
    rows = [{"order": 1, "works": reviewed_work("Siegfried", "Richard Wagner")}]
    for position, changes in enumerate([
        {"normalization_status": "review_required"},
        {"composer_id": None},
        {"id": None},
        {"work_kind": "programme_container"},
        {"work_kind": "composite_programme"},
        {"work_kind": "production_title"},
    ], 2):
        rows.append({"order": position, "works": reviewed_work("Editorial or media title", None, **changes)})
    assert normalized_programme({"title": "Wagner evening", "event_type": "opera"}, rows) == [
        {"order": 1, "title": "Siegfried", "composer": "Richard Wagner"}
    ]
    assert normalized_programme({"title": "Wagner evening", "event_type": "opera"}, rows[1:]) == []


def test_concert_programme_is_unchanged():
    rows = [{"order": 3, "works": {"title": "Programme announced later", "composer": None}}]
    assert normalized_programme({"title": "Concert", "event_type": "concert"}, rows) == [
        {"order": 3, "title": "Programme announced later", "composer": None}
    ]


def test_event_detail_requests_the_canonical_work_evidence():
    event_key = "santa-cecilia:official:1649"
    def cached(path, params=None, ttl=60):
        if path == "/rest/v1/event_catalog_v1":
            return [{"event_id": event_key, "title": "Wagner: Siegfried / Daniel Harding", "event_type": "opera"}]
        if path == "/rest/v1/event_programme":
            assert params["event_id"] == "eq.event-1"
            assert params["select"] == '"order",works(id,title,composer,composer_id,normalization_status,work_kind)'
            return [{"order": 1, "works": reviewed_work("Siegfried", "Richard Wagner")}]
        assert path == "/rest/v1/event_credits"
        return []
    def service(method, path, params=None, **kwargs):
        assert method == "GET"
        if path == "/rest/v1/events":
            return [{"id": "event-1", "room": "Sala Santa Cecilia"}]
        assert path == "/rest/v1/work_characters"
        return []
    with patch("api.index._cached_supabase_get", side_effect=cached), patch("api.index.supabase_service", side_effect=service):
        event = schedule_event_detail(event_key)["event"]
    assert event["title"] == "Wagner: Siegfried / Daniel Harding"
    assert event["programme"] == [{"order": 1, "title": "Siegfried", "composer": "Richard Wagner"}]
    assert event["room"] == "Sala Santa Cecilia"


if __name__ == "__main__":
    test_accent_insensitive_search()
    test_opera_classification()
    test_paris_opera_programme_rejects_editorial_and_media_rows()
    test_work_titles_use_the_original_language()
    test_reviewed_opera_programme_survives_official_marketing_titles()
    test_reviewed_opera_programme_preserves_multiple_works_and_unicode()
    test_reviewed_path_rejects_unresolved_and_nonwork_rows()
    test_concert_programme_is_unchanged()
    test_event_detail_requests_the_canonical_work_evidence()
    print("normalized event rules: ok")
