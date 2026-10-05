"""
Operational notes for spreadsheet migration (Phase 4).

1. Collect the latest official NIMAR workbooks and freeze a reference copy
   outside the running app (e.g. `docs/frozen_source/`).
2. Inspect sheets/headers/merged cells/status & phase free-text values.
3. Use /import/ to upload → select sheet → map columns → map statuses/phases
   explicitly (never rely on auto-coercion for values like "Not implemented").
4. Preview must show CREATE / UPDATE / SKIP / FAIL before confirm.
5. Spot-check a sample of imported Point IDs against the frozen sheet.
6. Day-to-day tracking then continues in the app; Excel remains import/export only.
"""
