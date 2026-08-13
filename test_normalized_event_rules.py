from api.index import canonical_event_type, normalize_search_key, search_match_score


def test_accent_insensitive_search():
    assert search_match_score("francois", "François") >= 0.8
    assert search_match_score("opera", "Opéra") >= 0.8
    assert search_match_score("theatre", "Théâtre") >= 0.8
    assert search_match_score("oeuvre", "œuvre") >= 0.8


def test_opera_classification():
    assert canonical_event_type("Festival RING") == "opera"
    assert canonical_event_type("Opéra") == "opera"
    assert canonical_event_type("Concert et Récital") in {"concert", "recital"}


if __name__ == "__main__":
    test_accent_insensitive_search()
    test_opera_classification()
    print("normalized event rules: ok")
