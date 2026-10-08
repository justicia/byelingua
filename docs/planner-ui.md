# News and Planner interface

The news homepage renders existing article records without images. Within each
article page, records are ordered by publication/processing date descending,
then article ID (or URL) ascending to resolve ties. The first three records form
Latest news, the next two form In focus, and the rest form More reporting.
Search and personal subscription results retain their linear feed. No article
is duplicated or removed by the column grouping.

The full Planner retains the existing Schedule API controller, pagination,
entity selection, venue normalization and date input semantics.
`planner-workspace.js` arranges its controls into three columns and adds a
calendar that writes the existing start/end inputs. Event details open in a
drawer. At narrow widths filters collapse and selected performances open in a
separate panel.

The homepage embeds `/schedule.html?embed=1` for its lightweight Planner. This
uses the same controller and data sources as the full page. Cities, dates and
the work/composer keyword are shown first; other controls are under More
filters. `planner-state.js` shares draft search fields, selected entity IDs,
location filters and selected event records in the browser's
`byelinguaPlannerDraft:v1` localStorage entry. Cross-document storage events
keep windows and the embedded frame synchronized. Closing the floating panel
does not unload it. Draft storage is browser-local and is not account or
server schedule storage. A page editing an existing `schedule_id` continues to
use the existing server membership controller independently.

## Browser regression checks

Use Node.js 18+ and install the pinned development dependency:

```sh
npm ci
npx playwright install chromium
npm test
```

If Chromium is already installed, skip the browser download and set
`SCHEDULE_CHROME_PATH` to its executable before `npm test`. No production
credentials are required: these tests serve static files and fixture APIs on
local ephemeral ports. They validate pagination, location reset and venue
aliases, draft synchronization, calendar ranges, details, schedule generation,
font families and desktop/mobile layouts in Chinese and English. Screenshots
from the integration check are written below the OS temporary directory in
`byelingua-ui-checks`.

Live schedule creation still uses the existing authenticated API. No database
schema or production ingestion behavior is changed by this interface work.
