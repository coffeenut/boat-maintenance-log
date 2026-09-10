# Boat Maintenance Log

A standalone, local-first maintenance app for M/V Trickster, a Nordhavn 40. Imported from the latest saved prototype, **v0.21**.

## Start using it

1. Download and extract this repository.
2. Open `maintenance.html` in a modern browser.
3. Choose **Open Data ZIP** and select `trickster-maintenance-data.zip`.
4. Use **Save Data ZIP** (or **Download Data ZIP**) to keep an updated backup after making changes.

There is no build step, server, account, or hosted service required. The app keeps a working copy in browser storage. The portable ZIP remains your backup and transfer format; browser storage can be cleared. Safari uses file import/download where direct file overwrite is unavailable.

## Features

- Upcoming maintenance with expandable procedures and notes
- Calendar and meter-hour maintenance schedules
- Equipment registry and hour meters
- Work logging and service history
- Portable ZIP import/export and work-history CSV export

## Repository contents

- `maintenance.html`: the complete app, including its JavaScript and CSS
- `trickster-maintenance-data.zip`: the verified Trickster baseline supplied with v0.21
- `dataset/`: the same baseline extracted as readable JSON, JSONL, schemas, and source notes for version control
- `SCHEMA.md`: data semantics and scheduling rules
- `DESIGN_REVIEW.md`: design considerations

The supplied records are the historical baseline from August 29, 2026, not a live copy of subsequent browser edits. To preserve newer records, export your current Data ZIP from the app.

The ZIP and `dataset/` are equivalent snapshots at initial import; editing one does not automatically update the other. The app reads the ZIP chosen through its interface.

## Development

Edit `maintenance.html` directly. No dependencies need to be installed. Keep the interface understandable to nontechnical boaters, use the verified Trickster data as the default working dataset, and do not add labor or service-cost accounting fields.

This repository contains the actual Trickster baseline maintenance records supplied with v0.21.
