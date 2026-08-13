from api.index import canonical_event_type, canonical_work_title, normalize_search_key, normalized_programme, search_match_score


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


if __name__ == "__main__":
    test_accent_insensitive_search()
    test_opera_classification()
    test_paris_opera_programme_rejects_editorial_and_media_rows()
    test_work_titles_use_the_original_language()
    print("normalized event rules: ok")
