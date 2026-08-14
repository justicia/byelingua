# Venue ingestion batch report

Generated: 2026-08-13T20:31:33.431477+00:00

## Summary

- TOTAL venues attempted: 16
- SUCCESS: 0
- PARTIAL: 14
- FAILED: 2
- Production database modified: no

## Venue results

| Venue | Status | HTTP | Extracted | Programme review | Errors |
|---|---:|---:|---:|---:|---|
| Théâtre des Champs-Élysées | PARTIAL | 200 | 0 | 0 | detail endpoint / JSON-LD mapping still required before READY FOR IMPORT |
| Maison de la Radio et de la Musique / Auditorium de Radio France | PARTIAL | 200 | 0 | 0 | detail endpoint / JSON-LD mapping still required before READY FOR IMPORT |
| Salle Gaveau | PARTIAL | 200 | 2 | 2 | detail endpoint / JSON-LD mapping still required before READY FOR IMPORT |
| Château de Versailles Spectacles / Opéra Royal de Versailles | PARTIAL | 200 | 2 | 2 | detail endpoint / JSON-LD mapping still required before READY FOR IMPORT |
| La Seine Musicale | PARTIAL | 200 | 2 | 2 | detail endpoint / JSON-LD mapping still required before READY FOR IMPORT |
| Salle Cortot | PARTIAL | 200 | 2 | 2 | detail endpoint / JSON-LD mapping still required before READY FOR IMPORT |
| Wiener Musikverein | PARTIAL | 200 | 3 | 3 | detail endpoint / JSON-LD mapping still required before READY FOR IMPORT |
| Wiener Konzerthaus | PARTIAL | 200 | 19 | 19 | detail endpoint / JSON-LD mapping still required before READY FOR IMPORT |
| Theater an der Wien | PARTIAL | 200 | 3 | 3 | detail endpoint / JSON-LD mapping still required before READY FOR IMPORT |
| Grafenegg | PARTIAL | 200 | 14 | 14 | detail endpoint / JSON-LD mapping still required before READY FOR IMPORT |
| MuTh | FAILED | 200 | 7 | 7 | detail endpoint / JSON-LD mapping still required before READY FOR IMPORT |
| Festspielhaus St. Pölten | PARTIAL | 200 | 2 | 2 | detail endpoint / JSON-LD mapping still required before READY FOR IMPORT |
| Teatro de la Zarzuela | PARTIAL | 200 | 2 | 2 | detail endpoint / JSON-LD mapping still required before READY FOR IMPORT |
| Fundación Juan March | FAILED |  | 0 | 0 | HTTPError: HTTP Error 307: The HTTP server returned a redirect error that would lead to an infinite loop.
The last 30x error message was:
Temporary Redirect |
| Teatro Monumental / RTVE Orquesta y Coro | PARTIAL | 200 | 2 | 2 | detail endpoint / JSON-LD mapping still required before READY FOR IMPORT |
| Teatro Auditorio San Lorenzo de El Escorial | PARTIAL | 200 | 2 | 2 | detail endpoint / JSON-LD mapping still required before READY FOR IMPORT |

## READY FOR IMPORT

None. Generic extraction is intentionally staging-only until detail/API adapters and work normalization are reviewed.

## NOT READY / NEEDS REVIEW

- Théâtre des Champs-Élysées
- Maison de la Radio et de la Musique / Auditorium de Radio France
- Salle Gaveau
- Château de Versailles Spectacles / Opéra Royal de Versailles
- La Seine Musicale
- Salle Cortot
- Wiener Musikverein
- Wiener Konzerthaus
- Theater an der Wien
- Grafenegg
- MuTh
- Festspielhaus St. Pölten
- Teatro de la Zarzuela
- Fundación Juan March
- Teatro Monumental / RTVE Orquesta y Coro
- Teatro Auditorio San Lorenzo de El Escorial
