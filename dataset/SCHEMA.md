# Boat Maintenance Data v1.2 — Semantic Specification

## Core rule

Store facts. Calculate status.

The files store what equipment exists, what maintenance is required, meter readings, and what work was completed. Labels such as **Due Soon** and **Overdue** are calculated by the app and are not authoritative stored facts.

## Equipment

Each equipment item has a permanent `id`, a human-readable `name`, a `category`, and optional manufacturer/model details.

Equipment may have a `parent_equipment_id`, allowing simple hierarchies such as:

- Main Engine
  - Cooling System
  - Fuel System

Use a parent system when one maintenance item naturally applies to several physical components. This keeps ordinary tasks simple.

When equipment is removed, keep its record so old service history still makes sense. Mark it `removed`. If useful, `replaced_by_equipment_id` can point to the new item.

## Meters

A meter is a logical maintenance counter such as:
- engine hours
- generator hours
- pump cycles
- distance

The canonical `value` in a meter reading is the cumulative value used for maintenance calculations.

If a physical hourmeter is reset or replaced, the app can still preserve a continuous lifetime counter:

```json
{
  "value": 7100.0,
  "displayed_value": 100.0,
  "event": "meter_replacement",
  "quality": "corrected"
}
```

This means the dashboard can continue using 7100.0 hours even though the new gauge happens to display 100.0.

Normal users should not need to understand this. A future UI should expose it as a simple **Meter replaced/reset** workflow.

## Maintenance tasks

There are two task kinds:

- `recurring` — repeats after completion
- `one_time` — completed once and then becomes complete

### Recurring examples

Every 250 hours:

```json
{"type":"meter","meter_id":"mtr_...","interval":250,"unit":"hours"}
```

Every 12 months:

```json
{"type":"calendar","interval":12,"unit":"months"}
```

A task may contain both. With `logic: "any"`, whichever comes first makes it due.

### One-time examples

Due on a specific date:

```json
{"type":"date","due_date":"2026-09-15"}
```

Due at a specific meter value:

```json
{"type":"meter_value","meter_id":"mtr_...","due_value":8000,"unit":"hours"}
```

## Completed work

Each line in `service_history.jsonl` is one service event.

One service event may:
- involve several pieces of equipment
- satisfy one or several maintenance tasks
- record meter values
- record parts used
- include notes and attachments

This handles a single yard visit that completes many maintenance items without creating duplicate work records.

## Maintenance completed without exact meter hours

If the service event contains an exact meter value, use it.

If the value is only approximate, store it with:

```json
"quality": "estimated"
```

If no meter value was recorded:

1. use the latest trustworthy meter reading at or before the service date as an estimated basis, if one exists;
2. otherwise the calendar schedule can still be calculated, but the meter-based next-due point is **unknown** until a reasonable basis is supplied.

Do not invent precision.

## Deferring a task

A task may contain an optional `defer_until` with a date and/or meter value plus a reason.

Deferral does **not** change the actual maintenance due point. It only tells the UI that the user intentionally postponed the reminder.

A good UI should distinguish:

- **Overdue**
- **Deferred until Sept 15**

rather than pretending the maintenance was never due.

## Inspection creates follow-up work

When an inspection discovers another job, create a `one_time` maintenance task. `origin_service_event_id` may reference the inspection that created it.

Example:

> Stabilizer inspection completed → cracked hose discovered → one-time task “Replace cracked stabilizer hose.”

## Due calculation

For each active task:

### Recurring task

1. Find the latest service event that lists the task in `completed_task_ids`.
2. If none exists, use the task baseline.
3. Calculate each trigger independently.
4. With `logic: "any"`:
   - any passed trigger = overdue
   - any trigger inside its warning window = due soon
   - otherwise = not due

### One-time task

1. Evaluate its absolute date/meter trigger.
2. Once a service event completes the task, its status is complete.

## Attachments

Attachments are ordinary files and use paths relative to the dataset root, for example:

`attachments/main-engine/2026-07-oil-change-invoice.pdf`

Do not store absolute computer-specific paths.

## User-interface principle

The schema may be rigorous, but the UI should stay plain-language.

Users should see:

> Change engine oil and filter  
> Every 250 hours or 12 months  
> Last done July 1 at 7,125 hours  
> Due at 7,375 hours or July 1, 2027

They should not normally see IDs, JSON, trigger objects, or schema terminology.

## Versioning

`schema_version` uses semantic versioning.

v1.1 adds only backward-compatible optional capabilities to v1.0:
- one-time tasks
- equipment replacement linkage
- meter reset/replacement support
- estimated meter values
- task deferral
- follow-up task linkage
