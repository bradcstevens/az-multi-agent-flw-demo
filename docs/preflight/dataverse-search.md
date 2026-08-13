# Preflight: Dataverse search in the Default environment

**Verdict: Dataverse search is enabled and its index is synced.** A test document written to
Dataverse comes back from a search **by its file content**. Enabled and observed 2026-08-13
(issue #3).

Re-check with `scripts/preflight/check-dataverse-search.sh --probe` — it exits non-zero if the
index ever stops returning documents. A bare run (no `--probe`) reads the toggle and the index
status only; `--enable` turns search on if it is off; `--export <dir>` writes the solution backup;
`--environment <id>` checks the identifier **shown in the Copilot Studio URL** rather than the one
the tenant calls Default.

## Why this needed verifying rather than assuming

Documents-based knowledge — the grounding the Copilot Studio SOP agent depends on (#17) — is not
selectable until Dataverse search is on, and Dataverse search is **off by default** in a Default
environment. That much is a toggle.

The part that is not a toggle, and the reason this is the build's longest lead-time item, is that
**flipping the setting and having a document come back from a search are different facts**.
`isexternalsearchindexenabled` is `true` the instant the PATCH returns; the index sync behind it
runs afterwards on its own clock. A check that read the setting would have reported a pass minutes
before the environment could actually answer a knowledge question, and #17 would have been unblocked
against an index that returned nothing.

So the check probes rather than reads. It writes a uniquely marked document into Dataverse, queries
the search index for that marker, and passes only once the marker comes back **out of the file's
content** rather than out of the record's metadata.

## Findings

| # | Finding | Evidence |
| --- | --- | --- |
| 1 | The setting is `Organization.isexternalsearchindexenabled`, and it was **`false`**. It is now `true`. | `GET`/`PATCH /api/data/v9.2/organizations(d3c93f69-ac94-f011-8706-000d3a106522)` → 204 |
| 2 | **181 seconds** from enabling to the first successful search. | Toggle 06:31:21Z, document written 06:32:21Z, first hit 06:34:22Z (2026-08-13) |
| 3 | The hit highlighted the marker in **`documentbody`** — the uploaded file's own bytes — not merely in `subject` or `filename`. | `POST /api/search/v1.0/query` → `@search.highlights.documentbody` |
| 4 | 29 tables carry `SyncToExternalSearchIndex`, including `annotation` (where uploaded files live), `msdyn_kbattachment`, `botcomponent` and `knowledgearticle`. | `GET /EntityDefinitions?$filter=SyncToExternalSearchIndex eq true` |
| 5 | Tenant **file** capacity is **20480 MB with 1915 MB used** — about 18.5 GB free, not the 3 GB the ticket assumed. Database 5120 MB / 148 MB, Log 2048 MB / 0. | `GET https://licensing.powerplatform.microsoft.com/v0.1-alpha/tenants/{tid}/TenantCapacity` |
| 6 | The environment is exported: `Cr688e5` (Common Data Services Default Solution), 1.6 KB, 16 seconds. | `POST /api/data/v9.2/ExportSolution` |

## The measured lead time, and why it is a floor rather than a promise

**181 seconds**, cold, from toggle to first hit. Microsoft documents 15 minutes minimum propagation
with a full sync exceeding an hour, and the ticket was scheduled against those numbers.

The measurement does not contradict the documentation, and reading it as "the docs are wrong" would
be the wrong lesson to carry into #17. This environment holds **148 MB** of data. There is almost
nothing to index, which is exactly the condition under which an initial sync is fast. The documented
figures describe a populated org, and this one becomes populated as #8's SOP corpus and #19's
troubleshooting knowledge base land.

What the number is good for is scheduling *this* build: enabling Dataverse search is a three-minute
step on this tenant, not an hour-long one, so it does not have to be started a day ahead.

Per-document indexing after the initial sync was measured four times at **36s, 152s, 37s and 218s**.
So even a warm index is not instant, and the spread is wide — content uploaded during a rehearsal is not immediately searchable, which
is a rehearsal hazard for #17 rather than a defect.

## Why the check insists on a content hit

Dataverse indexes a record's metadata and an attached file's content on different clocks. There is a
real intermediate state where a document is findable by its `subject` and `filename` while its bytes
are not yet in the index.

A knowledge source retrieves against **content**. So a metadata-only hit is reported as a half-synced
index and fails, with its own detail line naming the fields that did match. Treating it as a pass
would hand #17 an environment where "how do I close the store?" finds the document and can quote
nothing from it.

## What the check deliberately will not do

- **A bare run does not probe.** A probe writes a document into Dataverse; asking "is search on?"
  should not leave litter in an environment that cannot be backed up, restored or deleted. A bare
  run therefore reports the document check as **`not probed`** — a failure, because the toggle is
  not evidence, but one whose remedy is "probe for it", not "wait". The two are different advice and
  conflating them sends an operator away to wait for something that was never started.
- **It deletes its own probe document,** in a `finally`, so a run that dies mid-poll does not leave
  a record behind in the tenant-wide file pool the same check reports headroom for.
- **It refuses to start the poll if it cannot read the created document's id.** Continuing would run
  the whole probe and then be unable to clean up after itself.
- **It refuses to touch an environment whose identity does not check out.** `--enable` and
  `--probe` are both skipped when the environment is not the tenant's Default one, for the same
  reason the admin-role preflight refuses to elevate there: default-environment routing can silently
  land a maker in a personal Developer environment, and a write that reports success somewhere the
  demo never runs is worse than no write. A wrong-environment run is a *verdict* with that remedy,
  not a traceback — an operator who passed the identifier their Copilot Studio URL showed them needs
  the report, and a traceback loses every other check.
- **A probe that cannot delete its document fails the run.** Cleanup failure is its own check
  (`probe-document-removed`) rather than a warning on stdout, because the caller that matters is an
  unattended loop that reads the exit code.
- **`--enable` is a no-op when search is already on,** and re-reads afterwards rather than assuming
  the write took. Needless writes against the organisation row of an unrestorable environment are
  the thing to avoid.

## Traps that cost time here

- **A create answers `204 No Content`.** Without `Prefer: return=representation` the new record's id
  is only in the **`OData-EntityId` response header**, as a full URL. Reading it from the body yields
  `None`, and a `None` id made the first version of the cleanup a silent no-op — caught by finding
  the probe document still in the tenant after a green run, not by a test. Cleanup now falls back
  to finding the document by its marker, because refusing to start the poll would orphan the very
  document it was trying not to leave behind — the create has already happened by then.
- **The two search API versions have different shapes.** `GET /api/search/v1.0/status` returns the
  status as a mapping under `value`; `v2.0` returns the *entire v1.0 payload double-encoded as a JSON
  string* under `response`. Reading the v2.0 shape as a mapping yields nothing, which reports a
  healthy index as unprovisioned.
- **`POST /api/search/v2.0/status` and `POST .../v1.0/status` are both wrong** — the endpoint is a
  `GET`, and the v2.0 POST fails with a misleading "no HTTP resource matches `/api/data/v9.0/searchstatus`".
- **Capacity is not on the BAP admin API.** `scopes/admin/tenant/capacity` is a 404 and
  `$expand=capacity` on the environment returns `null`. It is on the **licensing** service, which is
  a separate resource and therefore a separate token.

## The file capacity correction

The ticket recorded "3 GB, shared tenant-wide". The tenant actually carries **20 GB** of file
capacity (`LOCAL_PAYGO_SEEDED_DATAVERSE`), of which 1.9 GB is used. The 3 GB figure is the default
allotment for a Developer/trial environment, not this tenant's entitlement.

It is still **pooled tenant-wide**, so the caution the ticket was expressing survives the correction:
another environment can exhaust it, and an exhausted pool does not disable search — it refuses the
upload, which surfaces much later and looks like a Copilot Studio fault. The check therefore fails on
low headroom with that explanation rather than merely printing the number.

## The solution export

A Default environment cannot be backed up, restored or deleted, so a solution export is the only copy
of its customisations that exists. `--export <dir>` writes one, and exports **`Cr688e5`**
("Common Data Services Default Solution") — the unmanaged solution that holds customisations — not
`Default` ("Default Solution"), which is the system catalogue of every component in the org.

The export taken at 2026-08-13T06:43:06Z is 1.6 KB, which is correct and not a truncation: nothing
had been customised yet. It is a baseline. The export taken after #17 published the SOP agent is
**48 KB**, carrying the bot, its configuration and all thirteen components — see
[the SOP agent record](../copilot-studio/sop-agent.md). Re-export after any change worth being able
to restore; the zip is a build artifact rather than something to commit.

## Scope

Verified: the setting's live value, the search index's provisioned status, that a document written
to Dataverse comes back from a search by its file content, the elapsed time from enabling to first
hit, tenant storage capacity, and that a solution export succeeds. **Not** verified here: whether
Copilot Studio actually offers documents-based knowledge in its own UI (#17 exercised that and
[recorded it](../copilot-studio/sop-agent.md)), the SOP corpus's own content (#8), or anything about
Direct Line (#18).
