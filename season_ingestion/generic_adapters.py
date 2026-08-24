from __future__ import annotations


GENERIC_ADAPTERS = {
    "JSON_LD": "generic_jsonld",
    "EMBEDDED_JSON": "generic_embedded_json",
    "PUBLIC_JSON_API": "generic_json_api",
    "ICS": "generic_ics",
    "STRUCTURED_HTML_LISTING": "generic_calendar_html",
    "MONTH_CALENDAR_HTML": "generic_calendar_html",
    "DETAIL_LINKED_LISTING": "generic_calendar_html",
}


def select_generic_adapter(structure_type: str) -> str | None:
    return GENERIC_ADAPTERS.get(structure_type)
