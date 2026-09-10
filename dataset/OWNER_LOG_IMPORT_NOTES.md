# Data provenance — owner maintenance log update

This dataset was updated from the owner's maintenance/activity log supplied on 2026-08-29.

Conservative import rules used:
- Only actual maintenance, repair, installation, inspection, and useful diagnostic entries were imported.
- Administrative/contact/social entries were not imported.
- Equipment was added only when the owner log itself established that the equipment/system exists.
- Unknown manufacturers/models were left null rather than guessed.
- An existing recurring task was marked completed only when the logged work clearly matched that task.
- Ambiguous "Racor fuel filter" work was NOT assigned to a particular engine.
- Cleaning the Naiad sea strainer was NOT treated as completion of the entire annual stabilizer service.
- The verified June 2, 2026 house-bank installation date is used as the calendar baseline for the battery maintenance tasks.
- No engine/generator meter reading was invented for historical work.

## Owner clarifications added after initial import

- Apr 16, 2026: both Warn 1000 davit hoists were replaced/installed together.
- Apr 20, 2026: the single Racor replacement was the generator Racor.
- Jan 4, 2026: the wing-engine Racor and dual main-engine Racors were replaced/serviced.
- The former generic Racor equipment record was split into separate main-engine, wing-engine, and generator Racor records so future maintenance can be tracked correctly.

## Current meter readings supplied by owner on 2026-08-29

- Main Engine: 7,236 operating hours.
- Generator: 6,473 operating hours.
- Wing Engine (Yanmar 3YM30AE): 20 operating hours.

The 20-hour wing-engine reading places the engine inside Yanmar's verified initial 50-hour break-in period,
so the manufacturer's one-time 50-hour maintenance items were added with a due meter value of 50 hours.
