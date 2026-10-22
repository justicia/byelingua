"""Read-only schedule summaries. Rules select existing global IDs, never create identities."""
import re
import unicodedata
from schedule_summary_registry import PRINCIPAL_ROLES, PROGRAMME_EXPECTATIONS

# Editorial selection reviewed against the work's synopsis, not cast billing order.
# Unlisted characters remain unclassified, not automatically supporting.
ARABELLA_WORK = '414c32ba-9e40-4260-ab4c-c1fb84993ee5'
ARABELLA_EVIDENCE = 'https://www.wiener-staatsoper.at/en/calendar/detail/arabella/2027-06-01/'
REVIEWED_PRINCIPAL_ROLES = {
    ARABELLA_WORK: {
        'reviewed_on': '2026-10-22', 'evidence': ARABELLA_EVIDENCE,
        'basis': 'Synopsis: the Arabella/Mandryka and Zdenka/Matteo relationships; editorial summary selection, not an exhaustive ranking.',
        'event_types': ['opera'],
        'characters': {
            'c55729ad-c7f0-4efa-8c2f-d4f810077112': 1,  # Arabella
            '74f7bcfc-0b3b-410e-8fbd-e26ef7d27c04': 2,  # Mandryka
            '4248f680-1b96-4292-a626-537dcce7eb56': 3,  # Zdenka
            'f2025f27-f6ac-4ac3-a470-94293e3abe58': 4,  # Matteo
        },
    }
}
# Shared display policy, keyed by global Work; source spellings never create aliases.
REVIEWED_PRINCIPAL_ROLES.update(PRINCIPAL_ROLES)
REVIEWED_PROGRAMME_EXPECTATIONS = PROGRAMME_EXPECTATIONS

# Source observations only; these do not substitute for missing production relations.
KNOWN_PARTIAL_PROGRAMMES = {
    'wiener_konzerthaus:pdf:53779919bb8487728696ebec': {
        'expected_count': 3, 'evidence': 'https://konzerthaus.at/en/program-and-tickets/bamberger-symphoniker-bayerische-staatsphilharmonie-hrusa/63791'},
    'wiener_konzerthaus:pdf:d853a9e55afa22c825a24202': {
        'expected_count': 2, 'evidence': 'https://konzerthaus.at/en/program-and-tickets/bamberger-symphoniker-bayerische-staatsphilharmonie-hrusa/63792'},
    'wiener_musikverein:pdf:41c4ec7f63cbb5c83b78d623': {'expected_count': 2, 'evidence': 'https://spielplan.musikverein.at/spielplan?abo=&dcode=MEII2627&subpage='},
}


KNOWN_PARTIAL_SOLOISTS = {'wiener_konzerthaus:pdf:15d2abc1a9d1218a7cd5daf2': {'expected_count': 4, 'reviewed_on': '2026-10-22', 'evidence': 'https://konzerthaus.at/en/program-and-tickets/bamberger-symphoniker-bayerische-staatsphilharmonie-wiener-singakademie-hrusa/63794'}}


def _key(value):
    value = unicodedata.normalize('NFKD', str(value or '')).casefold()
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return re.sub(r'[^\w]+', ' ', value.replace('_', ' ')).strip()


CONDUCTOR_ROLES = {'conductor', 'dirigent', 'dirigentin', 'musikalische leitung', 'direction musicale', 'direttore', 'direttore d orchestra'}
CAST_ROLES = {'cast', 'performer', 'singer', 'actor', 'soprano', 'mezzo soprano', 'contralto', 'alto', 'tenor', 'baritone', 'bass', 'bass baritone', 'countertenor', 'singer countertenor'}
SOLO_ROLES = {'soloist', 'soloist piano', 'soloist violin', 'soloist cello', 'piano solo', 'violin solo', 'soprano solo', 'tenor solo'}
# Instrument/voice labels alone do not establish soloist billing.
REVIEWED_SOLOIST_CREDITS = {
    'wiener_musikverein:pdf:41c4ec7f63cbb5c83b78d623': {
        'artist_ids': {'7c6e9b0d-a9eb-4bfb-a7ef-9348a386c1bb'},
        'evidence': 'https://spielplan.musikverein.at/spielplan?abo=&dcode=MEII2627&subpage=',
    },
    'wiener_konzerthaus:pdf:15d2abc1a9d1218a7cd5daf2': {
        'artist_ids': {'a1139be0-38d1-4c4d-8832-cd53a55411ce', '7327b8fb-623f-47ec-81f3-e29de7382ae5'},
        'evidence': KNOWN_PARTIAL_SOLOISTS['wiener_konzerthaus:pdf:15d2abc1a9d1218a7cd5daf2']['evidence'],
    },
}


def build_summary(event, programme_rows, credit_rows, normalized_items):
    kind = event.get('event_type')
    work_ids = {str((r.get('works') or {}).get('id')) for r in programme_rows if (r.get('works') or {}).get('id')}
    conductors, soloists, principal, seen = [], [], [], set()
    has_cast = False
    reviewed_solo = (REVIEWED_SOLOIST_CREDITS.get(event.get('event_id') or event.get('event_key')) or {}).get('artist_ids', set())
    for row in credit_rows:
        name = (row.get('artists') or {}).get('artist_name')
        if not name:
            continue
        role = _key(row.get('role'))
        character = row.get('work_characters') or {}
        character_name = character.get('canonical_name') or row.get('raw_character') or row.get('character')
        item = {'artist_id': row.get('artist_id'), 'artist_name': name}
        if role in CONDUCTOR_ROLES:
            signature = ('conductor', row.get('artist_id') or name)
            if signature not in seen:
                conductors.append(item); seen.add(signature)
            continue
        # Explicitly exclude production functions even if old rows contain a character.
        if any(marker in role for marker in ('director', 'designer', 'choreograph', 'lighting', 'orchestra', 'chorus', 'dramaturg', 'assistant', 'coach')):
            continue
        if character_name:
            has_cast = True
            selection = None
            if row.get('character_id'):
                work_id, char_id = str(character.get('work_id') or ''), str(row.get('character_id'))
                rule = REVIEWED_PRINCIPAL_ROLES.get(work_id) or {}
                rank = (rule.get('characters') or {}).get(char_id)
                if work_id in work_ids and kind in rule.get('event_types', []) and rank is not None:
                    selection = (work_id, char_id, rank, character_name, 'canonical_character')
            elif role in CAST_ROLES:
                # Exact reviewed source spelling within the performed Work only.
                # This classifies a source credit without assigning canonical identity.
                candidates = []
                for work_id in sorted(work_ids):
                    rule = REVIEWED_PRINCIPAL_ROLES.get(work_id) or {}
                    if kind not in rule.get('event_types', []):
                        continue
                    matches = [value for label, value in (rule.get('source_roles') or {}).items() if _key(label) == _key(character_name)]
                    if matches and len({(m['rank'], m['label']) for m in matches}) == 1:
                        chosen = matches[0]
                        candidates.append((work_id, None, chosen['rank'], chosen['label'], 'reviewed_source_role'))
                if len(candidates) == 1:
                    selection = candidates[0]
            if selection and role in CAST_ROLES:
                work_id, char_id, rank, label, basis = selection
                signature = ('cast', work_id, rank, row.get('artist_id') or name)
                if signature not in seen:
                    principal.append({**item, 'character_id': char_id, 'work_id': work_id, 'character': label, 'display_order': rank, 'selection_basis': basis})
                    seen.add(signature)
        elif kind in {'concert', 'chamber_music', 'recital', 'matinee'} and (role in SOLO_ROLES or str(row.get('artist_id')) in reviewed_solo):
            signature = ('solo', row.get('artist_id') or name, role)
            if signature not in seen:
                soloists.append({**item, 'function': row.get('role')}); seen.add(signature)
    principal.sort(key=lambda r: (r['display_order'], r['character'], r['artist_name']))
    programme = [dict(r) for r in normalized_items]
    observation = KNOWN_PARTIAL_PROGRAMMES.get(event.get('event_id') or event.get('event_key')) or {}
    expected = REVIEWED_PROGRAMME_EXPECTATIONS.get(event.get('event_id') or event.get('event_key')) or {}
    required = set(expected.get('work_ids') or [])
    missing_work_ids = sorted(required - work_ids)
    partial = bool((observation and len(programme) < observation['expected_count']) or missing_work_ids or (required and len(programme) < len(required)))
    solo_observation = KNOWN_PARTIAL_SOLOISTS.get(event.get('event_id') or event.get('event_key')) or {}
    return {
        'conductors': conductors, 'soloists': soloists, 'programme': programme,
        'principal_cast': principal, 'cast_status': 'reviewed_selection' if principal else 'unclassified' if has_cast else 'not_available',
        # All stored relations are read; this is not a claim about official-source coverage.
        'programme_status': 'partial' if partial else 'unknown',
        'soloists_status': 'partial' if solo_observation and len(soloists) < solo_observation['expected_count'] else 'unknown',
        'relation_coverage': 'all_stored_rows',
        'programme_expected_work_ids_missing': missing_work_ids,
        'principal_rule_work_ids': sorted(work_ids & REVIEWED_PRINCIPAL_ROLES.keys()),
    }
