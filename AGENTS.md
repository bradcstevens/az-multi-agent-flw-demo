# AGENTS.md

Repository instructions for coding agents working in this repo.

## Agent skills

### Issue tracker

Issues live in GitHub Issues for `bradcstevens/az-multi-agent-flw-demo`, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles plus the additive `parallel-safe` marker. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Feedback loops

| What you changed | Command |
| --- | --- |
| SOP corpus (`content/sop/`) or its tooling (`tools/sop_corpus/`) | `python3 -m pytest tools/tests -q` and, after editing sources, `PYTHONPATH=tools python3 -m sop_corpus build` |
