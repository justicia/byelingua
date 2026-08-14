# Teatro Real 2026–27 import adapter

The adapter combines two official sources without writing to the database:

- the Teatro Real calendar supplies performance date, time, category and official detail URL;
- the official season PDF supplies composers, programme works, cast and artistic-team credits.

It emits the shared normalized event shape used by Byelingua. Opera cast rows contain
`character_role → person`; production credits use `artistic_function`; concerts and
oratorios do not receive synthetic character roles. Original source spelling is retained,
while `search_key` is accent- and ligature-insensitive.

Generate a local preview from already downloaded official source files:

```powershell
python scripts/import_teatro_real.py `
  --calendar-html work/teatro-real/calendar.html `
  --season-pdf work/teatro-real/teatro-real-2026-27.pdf `
  --output work/teatro-real/teatro-real-2026-27-preview.json
```

The command only creates a JSON preview. It has no database-write or deployment mode.

Run the adapter regression suite with:

```powershell
python test_teatro_real_adapter.py
```
