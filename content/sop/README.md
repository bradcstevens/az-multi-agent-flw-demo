# SOP corpus

The standard-operating-procedure knowledge the Copilot Studio SOP agent is grounded on. Every
procedure here is **invented**: a fictional site (Store 223), fictional roles and invented
procedures. No customer content is used anywhere. Only the banner is the customer's own — the
corpus is branded **Circle K** by [ADR-019](../../docs/ADR/019-rebrand-the-sop-corpus-to-circle-k.md),
which reversed the fictional banner (Brightpath Convenience) it carried before, so that the
Grounding panel's snippet reads coherently under the Circle K header at the cross-platform beat.
Rebranding changes whose name is on the procedures, not whether they are real: the presenter says
out loud that they are authored, not the customer's.

## Layout

| Path | What it is |
| --- | --- |
| `corpus.toml` | Corpus manifest: banner, store, the rehearsed out-of-corpus question and the rehearsed hit. |
| `src/*.md` | The editable source of truth — TOML front matter fenced by `+++`, then markdown. |
| `docx/*.docx` | The built, upload-ready files. Generated; never hand-edit. |

## Build and verify

```bash
PYTHONPATH=tools python3 -m sop_corpus build     # regenerate content/sop/docx from src/
PYTHONPATH=tools python3 -m sop_corpus verify    # check the built files only
python3 -m pytest tools/tests -q                 # the acceptance tests for this corpus
```

`verify` fails if any file breaks a Copilot Studio ingestion rule, if the corpus falls outside
8–12 documents, or if a document has drifted into answering the rehearsed out-of-corpus question.

## Ingestion rules these files are built to survive

Copilot Studio **silently** excludes files it will not read — nothing is reported, the agent simply
answers as though the file were never uploaded. The builder therefore emits:

- `.docx` only (`.doc`, `.ppt`, `.pptx` and `.pdf` are also accepted by Copilot Studio).
- No sensitivity label. A file labelled Confidential or Highly Confidential is dropped on ingest.
- No custom document properties, no macros, no images. Each file is a few kilobytes, far under the
  7 MB per-file ceiling.
- Numbered steps written as literal `1.` … `n.` text rather than Word auto-numbering, so the
  ordinal survives text extraction and the agent can answer in numbered steps.

## Answer shape this corpus is written for

Every document opens with its title and `Document ID`, and every document has a `Procedure` section
of numbered steps. That is what lets the agent answer as numbered steps and attribute the answer to
a named source document — the built filename (`SOP-102 Store Closing Procedure.docx`) is the
citation name the associate sees, so it has to read as a document title on its own.

Expect the citation **URL** to be absent for Dataverse-uploaded documents. Name plus snippet is the
citation; a link is not guaranteed.

## The corpus

| ID | Document |
| --- | --- |
| SOP-101 | Store Opening Procedure |
| SOP-102 | Store Closing Procedure |
| SOP-103 | Restroom Cleaning and Inspection |
| SOP-104 | Coffee Bar Setup and Shutdown |
| SOP-105 | Forecourt Emergency Stop and Fuel Spill Response |
| SOP-106 | Cash Handling and Safe Drops |
| SOP-107 | Hot Food Case Temperature Control |
| SOP-108 | Age-Restricted Sales Verification |
| SOP-109 | Delivery Receiving and Backroom Stocking |
| SOP-110 | Shift Handover and Task Board |

Store opening, store closing and restroom cleaning were named by the customer and must stay in the
corpus.

## The rehearsed honest miss

> **How do I restart the car wash after a vehicle stalls in the bay?**

Store 223 is written as a forecourt-and-shop site with no vehicle wash, so nothing in the corpus
answers this. The question is plausible store language and sits close to the forecourt procedures,
which is what makes it a fair test of retrieval rather than a straw man. The agent must say plainly
that the procedure is not in its library instead of improvising — that is the honest-miss beat.

`corpus.toml` lists the terms that must stay out of the corpus (`car wash`, `carwash`, `wash bay`,
`wash tunnel`, `bay conveyor`). `verify` fails if a future document starts using one of them, so the
beat cannot rot silently.

## The rehearsed hit

> **How do I close the store?** — answered by `SOP-102`.

The mirror image, added by #26 as `[rehearsed_hit]` in `corpus.toml`, and the walkthrough's opening
tap. The miss has always been guarded; the hit was not, and a **hit decays into a miss**. Rename or
delete `SOP-102` and the tap still resolves — honestly — as *that procedure is not in the library*,
nothing goes red, and the cross-platform beat the whole demonstration rests on becomes the
honest-miss beat played twice. `src/tests/ci/test_store_pack.py` reads the section and asserts both
that the identifier exists under `src/` and that the document it names is about closing the store.

## Uploading to Dataverse

Upload `docx/*.docx` as the agent's knowledge source in the Copilot Studio Default environment, with
no authentication. After publishing, **start a fresh Direct Line conversation** — new content only
reaches new conversations, and propagation can take up to an hour. Freeze the corpus at least two
hours before a demo.
