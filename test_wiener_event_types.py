from season_ingestion.adapters.wiener_staatsoper import _event_type


def test_wiener_event_type_semantics():
    assert _event_type("", "Matinee: Mozart") == "matinee"
    assert _event_type("Oper", "Geheimmission Zauberflöte") == "children_family"
    assert _event_type("Oper", "Die Fledermaus") == "operetta"
