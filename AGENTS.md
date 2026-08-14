# FRONTEND UI LOCK

The Byelingua frontend is a user-approved product surface.

Do not modify page layout, global navigation, headers, typography, spacing,
colors, component hierarchy, interaction structure, Schedule Builder UI,
User Center UI, Event Detail UI, My Schedules UI, Schedule Editor UI,
responsive layout, or visual design during data ingestion, scraper, adapter,
backend, database, API, email, or maintenance tasks.

Frontend changes are allowed only when the user explicitly requests a
frontend/UI/layout change.

Data-source incompatibilities must be solved in adapters, normalizers,
schemas, APIs, or ingestion logic, never by silently redesigning the
frontend.
