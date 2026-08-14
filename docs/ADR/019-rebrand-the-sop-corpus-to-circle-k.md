# ADR-019: Rebrand the SOP corpus to Circle K, reversing the Brightpath position

## Status

Accepted

## Date

2026-08-13

## Issue

#1 (spec #1)

## Context

The ten documents of the **SOP corpus** are owned by *"Brightpath Convenience — Northgate District
Operations"*, an invented chain, while the surface around them is branded the **Circle K Frontline
Store Assistant**. At beat 1 the **Grounding panel** renders a snippet of the retrieved document, so
the invented chain's name appears on screen at the demonstration's centrepiece moment, under a
Circle K header.

Brightpath was not an accident. It follows the rule the whole surface runs on — *label the invented
things, and only those* — and
[docs/superseded-requirements-corrections.md](../superseded-requirements-corrections.md) records
that **100% of the corpus is invented**, because no usable customer content exists. A future reader
finding that text will conclude the fictional chain was deliberate, and be right.

This ADR exists because that position has been **reversed by the presenter**, and without the
reversal recorded the next person will read the corrections document and quietly change it back.

The arguments against the rebrand were made and overruled, and are recorded here rather than lost:

- **It re-runs the only live-verified issue in the build.** #17 published the **Copilot Studio SOP
  agent** and proved it end to end over Direct Line. Rebranding means rebuilding all ten `.docx`
  files, re-uploading them as Dataverse documents, and waiting on the **Dataverse search** sync —
  measured at 181 seconds cold, against Microsoft's documented 15-minute minimum, which is a floor
  and not a promise.
- **A Circle K-branded procedure invites scrutiny nobody in the room can answer.** The
  demonstration is being handed to a presenter who did not author the content. A citation reading
  *"Circle K Store Closing Procedure"* reads as the customer's own procedure; when it does not match
  their real operation, the demonstration looks wrong rather than illustrative.
- **"What is Brightpath?"** is the best question the demonstration can be asked, because the honest
  answer is the sales point: *invented — we did not have yours; swapping yours in is a document
  upload.*

The argument for it is brand coherence in front of the customer, and it is the presenter's call.

## Decision

**Rebrand the SOP corpus to Circle K**, rebuild the `.docx` files, re-upload them to Dataverse and
re-verify retrieval before the demonstration.

Three conditions attach, and they are the reason this is acceptable rather than reckless:

1. **It happens first, not last.** The Dataverse search sync runs on its own clock and cannot be
   hurried. This is the longest-lead item in the plan and is scheduled accordingly.
2. **It is verified by probe, not by assumption.** `check-sop-agent.sh --probe` opens a real Direct
   Line conversation and retrieves by **file content**, which is the only evidence the sync has
   completed — the toggle returning true is not.
3. **The `SIMULATED` labelling does not change.** The documents become Circle K-branded; they do not
   become real. Everything the surface already badges stays badged, and the presenter says out loud
   that the procedures are authored, not the customer's.

## Considered Options

- **Keep Brightpath.** Recommended twice and overruled. Retained here in full because the reasoning
  is sound and may be worth reinstating after the demonstration.
- **Strip the chain name entirely** — *"Store 223 — District Operations"*. Neutral, avoids implying
  the customer's own procedures, and costs the same re-upload. Rejected as getting the cost without
  the brand coherence that motivated the change.
- **Rebrand only the document titles, not the `owner` field.** Rejected: the Grounding panel renders
  a snippet of the document body, so the half left unbranded is the half most likely to be on
  screen.

## Consequences

- **Positive:** The surface, the citation and the header all say one thing.
- **Negative:** The centrepiece beat's grounding is re-established the day before it is presented.
  The mitigation is condition 2 — probe, do not assume — and the fallback is that the previous
  documents can be re-uploaded.
- **Negative:** [docs/superseded-requirements-corrections.md](../superseded-requirements-corrections.md)
  now reads as though the fictional chain survives. Its *Section 6 is void* note remains true —
  100% of the corpus is still invented — but the chain named in it does not. That document is
  append-only by its own rule, so this ADR is the correction rather than an edit to it.
- **Risk:** If the sync has not completed by the demonstration, beat 1 degrades to the **honest
  miss** — answering, honestly, that the procedure is not in the library. That is the failure mode
  `[rehearsed_hit]` exists to guard against, and it is silent. The probe is not optional.

## References

- [ADR-012: Ground the SOP agent on Dataverse Documents only](./012-grounding-option-a-dataverse-documents-only.md)
- [docs/copilot-studio/sop-agent.md](../copilot-studio/sop-agent.md)
- [docs/preflight/dataverse-search.md](../preflight/dataverse-search.md) — the toggle and the sync
- [docs/superseded-requirements-corrections.md](../superseded-requirements-corrections.md) — *Section 6 is void*
- `CONTEXT.md` — **SOP corpus**, **Rehearsed hit**, **Honest miss**
