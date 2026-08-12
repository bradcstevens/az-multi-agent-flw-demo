# Corrections to the superseded build-requirements document

The **superseded requirements document** —
`.reference/Circle-K-Frontline-Store-Assistant-Demo-Build-Requirements-v1.md`, v2.1, 31 July
2026 — is the reference material this build started from. It is untracked (`.reference/` is
`.gitignore`d), so nothing recorded only there survives a fresh clone.

Ten of its statements are **factually wrong**. Each is recorded below with the claim as the
document makes it and the correct position, so that a later reader who does still have the
document does not act on a claim this build has already disproved. The decisions those
corrections led to are recorded separately as ADRs — see [docs/ADR/README.md](ADR/README.md).

Corrections are **append-only for the ten below**: they are a historical record of what the
reference document got wrong, not a live list. A new finding about the reference document goes
in as correction 11 or later.

---

### 1. The plan-review flag is hardcoded, not configurable

**Claimed:** Human-in-the-loop approval is "built in — `enable_plan_review=True`", implying a
configuration value the build can set per request.

**Correct:** It is **hardcoded**. `enable_plan_review=True` is a literal argument to the
Magentic builder at `src/backend/orchestration/orchestration_manager.py:193`, and
`src/tests/backend/orchestration/test_orchestration_manager.py:350` asserts that literal. Both
must change to make **Plan review** a per-request value — see
[ADR-013](ADR/013-per-request-plan-review-over-orchestrator-bypass.md).

### 2. The Fast lane cannot bypass the orchestrator

**Claimed:** "Fast lane bypasses `MagenticBuilder` and calls the agent directly through the
existing `agent_factory`."

**Correct:** **No single-agent invocation path exists.** The request endpoint into the
orchestration builder is the only door; `agent_factory` produces the agent pool a Workflow is
built from, not an invocable entry point. The instruction is not implementable as written.
The build keeps the orchestration builder for both lanes and varies Plan review instead —
[ADR-013](ADR/013-per-request-plan-review-over-orchestrator-bypass.md).

### 3. The sample team definition would be rejected on upload

**Claimed:** A team JSON block presented as conforming to `content_packs/README.md` — offered as
a starting file to copy.

**Correct:** **Upload is strictly validated and the sample would be rejected**, for concrete
reasons worth knowing before copying it. `src/backend/services/team_service.py` requires
top-level `name` and `status`; a **non-empty** `agents` array in which **every agent carries
`input_key`, `type` and `name`** — the sample omits `type` on three of its four agents; and a
**non-empty** `starting_tasks` array in which every task carries `id`, `name`, `prompt`,
`created`, `creator` and `logo` — the sample's `starting_tasks` is empty. The sample is also
JSONC, and `//` comments are not parseable JSON. `src/backend/api/router.py` then returns
**400** if any referenced **model deployment** or **search index** does not already exist.

One detail cuts the other way and is worth recording so nobody engineers around it: **`id` and
`team_id` in the uploaded JSON are ignored and regenerated** as fresh UUID4 values
(`team_service.py:56,94,96`). Supplying a well-formed UUID neither helps nor hurts — it is
discarded. Treat the sample as illustrative prose, never as a starting file.

### 4. A wrong model deployment name silently drops the agent

**Claimed:** Per-agent model assignment is "built in — `deployment_name` per agent in team
JSON", with no failure mode noted.

**Correct:** Per-agent assignment is genuinely honoured, but the failure mode is **split, and
one half is silent**:

- **At upload**, the API returns **400** listing every referenced model that is not deployed in
  the Foundry project (`router.py:1024-1041`).
- **At agent-pool build time**, `AgentFactory` checks `deployment_name` against the
  `SUPPORTED_MODELS` environment allowlist and raises `UnsupportedModelError` on a miss — which
  the pool builder catches and **logs as a warning while skipping the agent**
  (`agent_factory.py:103-108, 215-222`). Nothing fails. The roster just comes up short.

So a name that exists in Foundry but is missing from the allowlist, or any team configuration
seeded by the post-provision script rather than uploaded through the API, loses the agent with
only a warning. **Verify the full roster is present after any content-pack change.**

### 5. `swedencentral` and `eastus` are invalid primary regions

**Claimed:** "Use a documented region — East US2, Sweden Central, UK South."

**Correct:** `swedencentral` is **not valid for the primary `location` parameter**, and neither
is `eastus`. The template enforces **two different region allowlists**, and only their
intersection is deployable: `australiaeast`, `eastus2`, `japaneast`, `uksouth`. `swedencentral`
appears in the `azureAiServiceLocation` allowlist only, which is what makes the claim look
right at a glance. See [ADR-009](ADR/009-eastus2-as-the-only-viable-primary-region.md).

### 6. `azd` 1.23.9 is usable, and a Bicep CLI minimum does apply

**Claimed:** "`azd` >= 1.18.0, **1.23.9 specifically excluded**", with no Bicep CLI version
named at all.

**Correct:** 1.23.9 is **not excluded**; from 1.23.9 upward it needs
`azd config set provision.preflight off` (no `alpha.` prefix — this is not an alpha feature).
The document also **omits a Bicep CLI minimum**, and there is one: **v0.36.1**, established by
bisection, because the deployer role grants in `infra/` use `deployer().userPrincipalName`. See
[ADR-004](ADR/004-fork-macae-at-pinned-upstream-commit.md).

### 7. A2A is GA, not Preview

**Claimed:** "**A2A (agent-to-agent) — PREVIEW.** Violates the GA-only constraint. Not used."

**Correct:** **A2A reached general availability in April 2026.** The GA-only constraint
therefore does not rule it out. **Direct Line is still the right choice**, but for different
reasons — see [ADR-011](ADR/011-direct-line-over-a2a-for-the-copilot-studio-sop-agent.md). Do
not repeat the "A2A is Preview" line in any walkthrough or write-up.

### 8. Direct Line tokens expire in 3600 seconds

**Claimed:** "Token lifetime is **30 minutes** — refresh, do not assume", repeated in the
constraints table as "Direct Line **token expires in 30 min**".

**Correct:** Direct Line tokens live **3600 seconds** — one hour. The 30-minute number in the
document conflates the token lifetime with the idle timeout after which an existing
conversation ends. Both exist; they are not the same clock.

### 9. An M365 Copilot licence alone does not permit publishing to Direct Line

**Claimed:** The licensing showstopper note lists an "**M365 Copilot license**" as one of three
alternatives that make an agent publishable.

**Correct:** **An M365 Copilot licence alone does not permit publishing to Direct Line in an
anonymous configuration.** The licence's zero-rating is conditioned on the agent operating
under an authenticated M365 Copilot user's identity, and a no-auth Direct Line session has no
such identity. This build publishes under **pay-as-you-go** — see
[ADR-012](ADR/012-grounding-option-a-dataverse-documents-only.md).

### 10. The Copilot Credit arithmetic is incomplete

**Claimed:** Published per-interaction credit rates for unlicensed users, presented as the
whole cost model for the Copilot Studio side.

**Correct:** The arithmetic is **incomplete in two ways that both move the number**:
**reasoning models bill a second premium meter** on top of the per-interaction rate, and
**prepaid overage at 125% of a zero-capacity allocation disables custom agents entirely** —
a kill switch, not a bill. Pay-as-you-go avoids the second and is the reason this build does
not use prepaid capacity.

---

## Section 6 is void

The reference document's section 6 instructs the build to use customer-supplied SOP material
("Sheena has already sent SOPs, training materials, and campaign examples. **Use those before
authoring from scratch**"). **No usable customer content exists.** **100% of the corpus is
invented** — fictional store, fictional employees, invented procedures throughout.
