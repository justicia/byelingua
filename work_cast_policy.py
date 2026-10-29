"""Shared Work-role display policy; no venue ownership or canonical identity writes.

The complete role schema remains in the existing global work_characters graph.
This module selects reviewed principal roles and joins performance credits to it.
"""
import re
import unicodedata
from work_cast_registry import WORK_CAST_POLICIES

GENERIC_PERFORMANCE_TYPES = {'performance'}
VERIFIED_WORK_STATES = {'verified', 'resolved', 'canonical'}


def normalize_role_label(value):
    value = unicodedata.normalize('NFKD', str(value or '')).casefold()
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return re.sub(r'[^\w]+', ' ', value.replace('_', ' ')).strip()


def work_role_policy(work_id, *, work_character_id=None, source_character=None):
    """Classify an existing Work-role reference, never assign an identity.

    A linked but unreviewed role must not be reinterpreted by its raw label.
    Source-only matches carry no canonical Character ID.
    """
    work_id = str(work_id or '')
    rule = WORK_CAST_POLICIES.get(work_id) or {}
    if not rule:
        return None
    if work_character_id:
        rank = (rule.get('characters') or {}).get(str(work_character_id))
        if rank is None:
            return None
        return {'work_id': work_id, 'work_character_id': str(work_character_id),
                'display_order': rank, 'character': source_character,
                'selection_basis': 'canonical_character', 'evidence': rule['evidence']}
    label_key = normalize_role_label(source_character)
    if not label_key:
        return None
    matches = [r for label, r in (rule.get('source_roles') or {}).items()
               if normalize_role_label(label) == label_key]
    choices = {(r['rank'], r['label']) for r in matches}
    if len(choices) != 1:
        return None
    rank, label = next(iter(choices))
    return {'work_id': work_id, 'work_character_id': None, 'display_order': rank,
            'character': label, 'selection_basis': 'reviewed_source_role',
            'evidence': rule['evidence']}


def eligible_for_principal_selection(event, work_id, verified_full_work_ids):
    rule = WORK_CAST_POLICIES.get(str(work_id)) or {}
    kind = str(event.get('event_type') or '').strip().casefold()
    raw = str(event.get('raw_event_type') or kind).strip().casefold()
    if kind in rule.get('event_types', []):
        return True
    # Generic source vocabulary is not evidence that a reviewed opera role is
    # inapplicable. Require the performed full Work to be independently verified.
    # Explicit ballet, concert, workshop, etc. never take this path.
    return (kind in {'other', 'performance', ''} and raw in GENERIC_PERFORMANCE_TYPES
            and str(work_id) in verified_full_work_ids)


def select_performance_principal(event, programme_rows, credit):
    work_ids = {str((r.get('works') or {}).get('id')) for r in programme_rows
                if (r.get('works') or {}).get('id')}
    verified = {str((r.get('works') or {}).get('id')) for r in programme_rows
                if (r.get('works') or {}).get('normalization_status') in VERIFIED_WORK_STATES
                and (r.get('works') or {}).get('work_kind') == 'work'}
    linked = credit.get('work_characters') or {}
    label = linked.get('canonical_name') or credit.get('raw_character') or credit.get('character')
    if credit.get('character_id'):
        work_id = str(linked.get('work_id') or '')
        if work_id not in work_ids or not eligible_for_principal_selection(event, work_id, verified):
            return None
        return work_role_policy(work_id, work_character_id=credit['character_id'], source_character=label)
    candidates = [match for work_id in sorted(work_ids)
                  if eligible_for_principal_selection(event, work_id, verified)
                  if (match := work_role_policy(work_id, source_character=label))]
    return candidates[0] if len(candidates) == 1 else None


def describe_work_cast_schema(work_ids, work_character_rows):
    """Reuse stored global Work-role slots, independently of current performers."""
    allowed = {str(w) for w in work_ids}
    result = []
    for row in work_character_rows:
        work_id = str(row.get('work_id') or '')
        if work_id not in allowed:
            continue
        selected = work_role_policy(work_id, work_character_id=row.get('id'),
                                    source_character=row.get('canonical_name'))
        result.append({
            'character_id': row.get('character_uid') or row.get('id'),
            'work_character_id': row.get('id'), 'work_id': work_id,
            'global_character_id': row.get('character_uid'),
            'canonical_name': row.get('canonical_name'),
            'artist_id': None, 'artist_name': None,
            'principal_display_order': selected['display_order'] if selected else None,
            'selection_status': 'reviewed_principal' if selected else 'unclassified',
        })
    return result
