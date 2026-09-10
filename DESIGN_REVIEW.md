# v1.1 Design Review

The schema was checked against common awkward maintenance cases.

| Scenario | v1.1 handling | Extra complexity exposed to normal user? |
|---|---|---|
| One service job satisfies several maintenance items | One service event lists several completed task IDs | No |
| Equipment is replaced | Old item remains in history; optional pointer to replacement | No |
| Physical hourmeter resets/replaced | Logical cumulative meter value continues; raw display may also be recorded | Only through a simple reset/replacement workflow |
| Maintenance done but exact hours unknown | Allow estimated basis or unknown meter due point | No |
| One task touches several components | Prefer a parent “system” equipment item | No |
| One-time repair/reminder | `one_time` task with fixed date/meter target | Small, understandable |
| User intentionally postpones work | Optional deferral does not rewrite the real due point | Small, understandable |
| Inspection discovers another job | Create a one-time follow-up task linked to the inspection event | No |
| Historical data references deleted item | Prefer deactivate/remove status rather than deleting records | No |
| AI / automation writes readings | Same meter-reading format, with source metadata | No |

## Complexity intentionally NOT added in v1.1

- work-order subsystem
- inventory purchasing workflow
- dependency graphs
- task-template inheritance
- multi-vessel fleet management
- permissions/users/roles
- accounting
- arbitrary boolean scheduling expressions
- database migrations visible to users

Those can be added later only if real usage demonstrates a need.
