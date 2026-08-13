# The Direct Line client, and the SOP tool above it

Issue #18. [ADR-011](../ADR/011-direct-line-over-a2a-for-the-copilot-studio-sop-agent.md) chose
Direct Line 3.0 as the transport to the published Copilot Studio SOP agent. This is what that
decision cost to implement against the live agent [#17 authored](./sop-agent.md), and the four
things it got wrong.

## Where the code lives, and why not where the ADR says

ADR-011 says the client is "wrapped as an MCP service in `src/mcp_server/services/`". The tool is
there. **The transport is not** — it is in the backend, at `src/backend/sop/`, and the MCP tool
reaches it over `POST /api/v4/sop/ask`.

Two facts force that split, and neither was visible when the ADR was written:

- The MCP container's `Dockerfile` copies **only `src/mcp_server`**, and its `pyproject.toml` ships
  `httpx` but not `aiohttp`. `BaseAPIService` — which the ticket names as the seam the client must
  be testable through, and which every other outbound call in this repo already uses — is an
  aiohttp module under `src/backend/services/`. Importing it inside that image is not a dependency
  bump; it is a second copy of the backend.
- The citation is wanted **on the backend anyway**. #23's server-side "source used" event is what
  proves the answer travelled Foundry → Copilot Studio → Dataverse; an event emitted from inside
  the MCP container would be proving it from the wrong side of the hop.

So the MCP tool relays, which is the pattern `ask_user` already uses and the one #21 declares for
this container. The refactor that made that possible — `BackendClient`, with `_request` as the
patchable seam — replaced the inline `httpx.AsyncClient` `AskUserService` was building, so there is
now one way for this container to call the backend rather than two.

## Findings

| # | Finding | Evidence |
| --- | --- | --- |
| 8 | **This environment serves no regional channel settings.** `PvaGetDirectLineEndpoint` returns a **legacy gateway** token endpoint — `powervamg.us-il102.gateway.prod.island.powerapps.com/api/botmanagement/v1/directline/directlinetoken?botId=…&tenantId=…` — which 404s on every `regionalchannelsettings` path. The environment's own `runtimeEndpoints["microsoft.PowerVirtualAgents"]` **is** that gateway, and the `<envid>.environment.api.powerplatform.com` host is **NXDOMAIN**. | Live probes of both hosts, 2026-08-13 |
| 9 | **The Direct Line token names its own service.** The JWT's `iss` and `aud` are both `https://directline.botframework.com/`. That is the second source for the base URL, and it is still resolution rather than assembly — the service told us, in the credential it issued. | Decoded live token |
| 10 | **A Copilot Studio Direct Line token is conversation-scoped.** It carries a `conv` claim. A token reused for a second `POST /conversations` **rejoins the first conversation** and the drain replays its transcript. | Live: the out-of-corpus probe answered with SOP-102's closing steps |
| 11 | **3600 seconds, confirmed from the token itself**, not just from the payload's `expires_in`: `exp - nbf` is 3600. ADR-011's correction of the superseded 30-minute figure holds. | Decoded live token |

## Resolving the base URL: two sources, then a refusal

ADR-011's rule is absolute and correct — *never assemble the default Direct Line hostname*. A
hardcoded `https://directline.botframework.com/v3/directline` is in Microsoft's own web-security
doc, and it is wrong for a non-default region. But finding 8 means the source the ADR names is not
always **there**.

So `direct_line_base()` has an order:

1. The **regional channel settings service**, built the way Microsoft's own working sample builds
   it: `new URL('/powervirtualagents/regionalchannelsettings?api-version=…', tokenEndpoint)`, with
   the `api-version` read **off the token endpoint's own query string** rather than pinned. Then
   `channelUrlsById.directline` + `v3/directline`.
2. Failing that, the **`aud`/`iss` claim of the token this environment just issued**.
3. Failing both, **raise** — which becomes the fixed failure message. It never falls through to a
   guessed hostname, because a guessed hostname in the wrong region produces a timeout, and a
   timeout reads exactly like the agent having nothing to say.

Live, this environment takes step 2 and resolves to `https://directline.botframework.com/v3/directline`
— the same string the doc hardcodes. That is the point: it is right *here*, and the code does not
know that until the service says so.

## A token per conversation

Finding 10 is the bug this ticket nearly shipped. The first implementation cached the token for its
3600-second life, which is what a Direct Line token's lifetime invites you to do, and every unit
test passed. Live, the second question came back with the first question's answer — the demo's
**honest miss** beat answering with SOP-102's closing steps, which is the single worst way for this
to fail, because it looks like the grounded agent working.

`token()` therefore never caches. A conversation costs one token, always. The 3600 seconds govern
how long *that* conversation's token stays good, which is why the client refuses to start at all
when its answer timeout would outlive the life the service reported: a conversation held open past
its token expires mid-drain, and an agent that stops answering halfway is indistinguishable from an
agent that had nothing to say.

Two mutations pin this: reinstating the cache, and dropping the timeout guard, each turn one
specific test red.

## Reading the answer

- **Filter to `from.role == "bot"`.** Direct Line replaces the sender identifier, so the echo of our
  own message comes back as an activity. The docs' own C# sample filters on `From.Name == botName`,
  which is precisely what ADR-011 forbids and would drop every bot activity here.
- **De-duplicate by activity id**, and carry the watermark. A poll that overlaps the previous one
  returns activities already seen.
- **Citations come from `entities`**, filtered to `type == "https://schema.org/Message"` and sorted
  by `position`. The markdown reference form in the text (`[1]: cite:1 "Citation-1"`) is the
  parallel representation ADR-011 warns against parsing.
- **`snippet()` truncates `text`, never `abstract`** — `abstract` is the filename (the correction
  [#17 recorded](./sop-agent.md#the-citation-shape-for-the-orchestrator-18)), and `text` is the whole
  document as HTML. R6's Grounding panel renders `Citation.snippet()`.

## Failure

One fast retry, then `DIRECT_LINE_FAILURE` — a fixed sentence, with no citations. There is **no**
fallback to model knowledge and **no** fallback to a local copy of the SOP corpus. A fallback would
make the transport's failure invisible, and the whole claim being demonstrated is that this answer
came from Dataverse through Copilot Studio; an answer that arrives when that path is broken is
evidence of the opposite.

## Configuration

| Setting | Meaning |
| --- | --- |
| `COPILOT_STUDIO_DIRECT_LINE_TOKEN_ENDPOINT` | The endpoint `PvaGetDirectLineEndpoint` returned. Tenant-specific, so a bicep parameter rather than something the deployment creates. Unset, the SOP tool answers with its fixed failure message. |
| `COPILOT_STUDIO_AGENT_NAME` | Display name, for the Grounding panel. Defaults to `Store SOP Assistant`. |

Re-read the endpoint rather than storing it long-term — it is what
`PvaGetDirectLineEndpoint` says today:

```bash
bash scripts/copilot_studio/check-sop-agent.sh --probe
```

## Scope

Verified live, 2026-08-13: base URL resolved from the token claim, an anonymous conversation, the
procedure question answered in numbered steps with a `SOP-102 Store Closing Procedure.docx`
citation carrying `url=None` and a working snippet, and — after the per-conversation token fix — a
second question in a **distinct** conversation producing the honest miss.

Not verified: concurrent conversations, behaviour against an environment that *does* serve regional
channel settings (step 1 is exercised only in tests), and R6's rendering of these citations.
