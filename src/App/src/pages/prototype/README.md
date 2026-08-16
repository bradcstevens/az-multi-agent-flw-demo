# PROTOTYPE — what does a plan worth approving look like?

Throwaway. Issue [#85](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/85).
**This branch is not merged and must not be.** `main` keeps the decision, not the code.

## Run it

```bash
cd src/App && npm run dev
```

Then open <http://localhost:3001/prototype/plan-approval>.

Four variations of the same plan, switchable from the bar at the bottom of the screen or by
`?variation=rail|thread|sheet|relay`. Narrow the window past **900px** to see each one at the
**Stacking breakpoint**.

## What it is for

ADR-028 decided *which* requests earn a **Reviewable plan** and deliberately left this ticket the
question of what one looks like — including the part nothing in the system can express today:
**a step assigned to a person**. `MStep` carries `agent` and `action` and nothing else.

The plan on screen is the shift swap as ADR-028 left it: the associate **names** their partner,
so the plan carries three human steps — the associate's own confirmation, the named peer's
acceptance, and the shift lead's approval.

## The three controls

- **The variation bar** (bottom) — the same plan drawn four ways.
- **The phase chips** (top) — what the surface says *before* the plan exists, one chip per
  ADR-023 phase, each showing the signal that entitles it. There is no "agents selected" phase.
- **The plan itself** — approve, or send it back with a change. Sending back bumps the revision,
  quotes what you said, and re-derives the suggestions.

## The part worth keeping

`planApprovalModel.ts` — pure, no React, no DOM. The `Assignee` union, `ProposedStep.waitsOn`,
the `review` reducer and the `revise` half of the verdict are the answer; everything else on this
route is a page that gets deleted.
