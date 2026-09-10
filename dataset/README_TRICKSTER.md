# Trickster maintenance data

This is a conservative, verified-source starter dataset for Trickster.

- Equipment: 8
- Maintenance tasks: 43
- Hour meters: 3
- Reference parts: 6
- Invented service history: none
- Invented meter readings: none

## First use
1. Open this ZIP in the Boat Maintenance Log app.
2. Enter current whole-hour readings for main engine, generator and wing engine on the Dashboard.
3. For each maintenance item, backfill a last-completed event only when you have a real receipt/log/date/hour basis. Otherwise leave it as Needs info until you actually perform it.
4. Save the ZIP back to the same file.

See VERIFIED_SOURCES.md for source and exclusion notes.


## Owner log update

Service history and several additional equipment records were added from `OWNER_MAINTENANCE_LOG.md`. See `OWNER_LOG_IMPORT_NOTES.md` for the conservative import rules.


## Schema v1.2

Service history does not track labor hours, labor cost, service cost, or currency. These fields were deliberately removed from the canonical format.
