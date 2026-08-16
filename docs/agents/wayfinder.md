# Wayfinder sessions

How a `/wayfinder` session gets its model, reasoning effort and context window pinned, and why
each of those choices is load-bearing rather than a preference.

This document covers the **session configuration**. The tracker half — what a map is, how tickets
are created, blocked, claimed and resolved — lives in
[the issue tracker doc](issue-tracker.md#wayfinding-operations).

> **These artifacts are not in this repository.** They live in the developer's home directory
> (`~/.copilot/agents/` and `~/.zshrc`), because the `/wayfinder` skill itself is installed at
> `~/.copilot/skills/wayfinder` and is used across repositories. This document is a record of a
> setup each developer applies once, not a description of repository state. Nothing here is
> checked by CI, because CI has no home directory to check.

## Why any of this is needed

A skill cannot set the model, the effort level, or the context tier. A skill is markdown injected
into a session that has **already started** — by the time `SKILL.md` is read, the model has been
chosen and the context window sized. The skill's own `agents/openai.yaml` accepts only `interface`
and `policy` keys; there is no knob to add.

So determinism has to come from the layers underneath: the **agent definition** and the
**launcher flags**.

## Where each value can be set

| Layer | model | effort | context | Scope |
| --- | :---: | :---: | :---: | --- |
| `--model` / `--effort` / `--context` flags | yes | yes | yes | One process; outranks everything below |
| `.agent.md` frontmatter | `model:` | `reasoning-effort:` | — | One agent |
| `settings.json` → `subagents.agents.<name>` | `model` | `effortLevel` | `contextTier` | One subagent |
| `.github/copilot/settings.json` | yes | yes | yes | One repository, committed |
| `.github/copilot/settings.local.json` | yes | yes | yes | One repository, ignored by git |
| `~/.copilot/settings.json` | yes | yes | yes | Global fallback |

Two entries in that table are easy to get wrong:

- **Context tier cannot be expressed in an `.agent.md`.** The CLI's agent frontmatter accepts
  `name`, `description`, `model`, `tools`, `infer`, `disable-model-invocation`, `user-invocable`,
  `reasoning-effort`, `deferred-tool-loading`, `strict-tools-list`, `mcp-servers`,
  `github.toolsets` and `github.permissions` — and nothing for the context window. It has to come
  from a flag or from settings, which is the main reason a launcher exists at all.
- **VS Code flags `reasoning-effort` as unsupported, and is wrong about it.** VS Code and the
  Copilot CLI share the `.agent.md` file extension but not the schema. VS Code additionally knows
  `agents`, `argument-hint`, `handoffs`, `hooks` and `target`; the CLI additionally knows
  `reasoning-effort`, `infer`, `mcp-servers`, `deferred-tool-loading` and `strict-tools-list`.
  The CLI honours the key. Keeping the file outside a VS Code workspace avoids the warning.

## The agent

`~/.copilot/agents/wayfinder.agent.md`, user-level rather than repository-level so that it
resolves from any checkout — matching the launcher, which is also user-level.

```yaml
---
name: wayfinder
description: Chart and work a wayfinder map of decision tickets on the repo's issue tracker.
model: claude-opus-5
reasoning-effort: xhigh
user-invocable: true
disable-model-invocation: true
---
```

The body carries only the rules a long session drifts away from: plan rather than build, never
answer the human's side of a question, refer to maps and tickets by name, one ticket per session,
publish the continuation record before finishing. Everything procedural stays in the skill, which
loads on invocation.

### `tools:` is deliberately absent

An unset `tools:` means **every** tool category, and three of them are required: `skill` (to reach
`/grilling`, `/domain-modeling` and `/prototype`), `task` (to fire `/research` subagents), and
`ask-user`. Narrowing the list to tidy it up is the quiet way to break the skill — see below.

### `disable-model-invocation: true`

Stops the agent being spawned through the `task` tool. A delegated subagent has no human attached,
so a wayfinder running there would interview an empty room and answer itself. The trade-off is
that the agent no longer appears in the delegation list, which is the intended outcome, not a
symptom.

## The launcher

A zsh function in `~/.zshrc`. It calls the existing `copilot()` wrapper rather than
`command copilot`, so it still gets the auto-update pass.

```zsh
wayfinder() {
    local prompt="/wayfinder"
    [[ $# -gt 0 ]] && prompt+=" $*"

    copilot --agent wayfinder \
            --model claude-opus-5 \
            --effort xhigh \
            --context long_context \
            -i "$prompt"
}
```

Usage is `wayfinder <loose idea>` to chart a new map, or `wayfinder <map> [ticket]` to work
through an existing one.

Model and effort are repeated here even though the agent file already sets them. That redundancy
is intentional: the two launch paths fail differently. The flags cover the scripted path; the
frontmatter covers an interactive `/agent wayfinder`, where no flags are present.

### `-i`, never `-p`

This is the single most important line in the setup. Wayfinding is human-in-the-loop — grilling
tickets, prototype tickets and most task tickets resolve only through live exchange — and the
`ask_user` tool is gated on the session mode:

| Flag | Mode | `ask_user` |
| --- | --- | --- |
| `-i, --interactive <prompt>` | Starts interactive, auto-runs the prompt | registered |
| `-p, --prompt <text>` | Runs the prompt, then exits | **stripped** |

Under `-p` the tool is removed from the tool set entirely. The agent would still run, still read
the skill, and still believe it was interviewing someone — while supplying both halves of the
conversation. That failure is silent and produces a map full of decisions nobody made.

Passing the skill through `-i` also keeps it a **user** invocation, which matters because
`/wayfinder` is declared `disable-model-invocation: true` and cannot be invoked by the model.

## Verifying the setup

Run the launcher, then read the newest session log under `~/.copilot/logs/`:

```bash
cd ~/.copilot/logs && f=$(ls -t | head -1)
grep -aoE 'wayfinder|"model": ?"[a-z0-9.-]+"|xhigh|long_context|ask_user_tool_registered|"name": ?"ask_user"' "$f" \
  | sort | uniq -c
```

A correctly configured session shows all five: the agent name, `"model": "claude-opus-5"`,
`xhigh`, `long_context`, and both `ask_user_tool_registered` and `"name": "ask_user"`. The last
pair is the one worth checking after any change to `tools:` or to the launcher's flags — it is the
difference between an agent that interviews you and one that interviews itself.

## Choosing the numbers

| Phase | Model | Effort | Context |
| --- | --- | --- | --- |
| Charting a map | `claude-opus-5` | `xhigh` | `long_context` |
| Working a grilling or prototype ticket | `claude-opus-5` | `high`–`xhigh` | `default` |
| `research` subagents | `claude-sonnet-5` | `high` | `long_context` |
| `task` tickets | `claude-sonnet-5` | `medium` | `default` |

Charting earns the ceiling: it makes the irreversible judgements — the destination, the scope
boundary, whether something is a ticket or still fog — and every later ticket inherits them. It
also runs two grilling rounds on top of a ~36 KB skill file, the tracker doc, `CONTEXT.md` and
`AGENTS.md`, which is long-context territory before the conversation starts.

Ticket sessions do not need the long window: the skill sizes each ticket to one 100K-token
session by design.

Research subagents are the only `AFK-safe` ticket type. They read widely and decide nothing, so a
large window matters and deep reasoning does not. They are configured separately, under
`subagents.agents.research` in `~/.copilot/settings.json`.

> **`max` is not the safe default it looks like.** Higher effort makes the model more willing to
> anticipate the human's answers and carry on, which is precisely the failure the skill forbids.
> `xhigh` is the recommended ceiling for the human-in-the-loop phases.
