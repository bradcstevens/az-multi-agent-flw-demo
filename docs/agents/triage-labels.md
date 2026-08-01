# Triage Labels

The skills speak in terms of five canonical routing roles plus the additive `parallel-safe` marker. This file maps them to the actual label strings used in this repo's issue tracker.

| Canonical role | Label in our tracker | Meaning |
| --- | --- | --- |
| `needs-triage` | `needs-triage` | Maintainer needs to evaluate this issue |
| `needs-info` | `needs-info` | Waiting on reporter for more information |
| `ready-for-agent` | `ready-for-agent` | Fully specified, ready for an AFK agent |
| `ready-for-human` | `ready-for-human` | Requires human implementation |
| `wontfix` | `wontfix` | Will not be actioned |
| `parallel-safe` | `parallel-safe` | Can be worked independently alongside other issues |

`parallel-safe` is additive: apply it alongside a routing label rather than instead of one.

When a skill mentions a role, use the corresponding label string from this table.
