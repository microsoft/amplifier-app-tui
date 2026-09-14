# Converge practice for this repository

This is a worked reading of the supplied method, not another contract or an implementation
of the future Converge app. Where this note and the source method disagree, the method wins.
This project's direction lives in [VISION](../docs/VISION.md) and [contracts](../contracts/composition.v1.md).

## Source and scope

The newly supplied archive is byte-identical to the original method archive in the handoff,
despite its different filename. It was re-read for this amendment. Its README, family/app
visions, relevant family/service/reader seams, method vision and all eight method contracts
were inspected. [method-source.json](method-source.json) pins the archive, method commit
and individual file hashes without publishing the private source documents or URLs.

The archive intentionally omits the method's referenced templates, DOCUMENT-SHAPES and
published manager-mode body. We do not invent their contents. This repo's existing shape
and the supplied contracts are enough to amend its documents; a full template/wake-mode
implementation would need those sources. In wake.v1, the reference to operation P7 is
historical: the moved stall rule is in lanes.v1 P4. It is not a second rule to copy here.

## Reading and amendment loop

1. Read the repo conventions, vision, affected contracts and current [plan](PLAN.md).
   Derive work from a named promise or the steward's recorded words (method operation P1–2).
2. Record the observation and amend direction before changing its implementation.
   Preserve history and apply the state-specific editing path (documents P2; settling P2–4).
   [DIRECTION-REVIEW](DIRECTION-REVIEW.md) records the authority for this amendment.
3. Keep the vision as a present-tense destination, the contract as numbered observable
   obligations, and evidence/sequencing in notes (documents P1, P3–6, P14–15).
   Delegate to a promise's owning document rather than restating it in a sibling.
4. Keep the work record visible and continue independent work when a decision is pending
   (operation P2–3). If lanes are introduced, follow lanes P1–5 and wake P1–6;
   a shared-working-copy subagent is not a conforming lane. No lanes exist in this wave.
5. Re-run the relevant checks and reconcile observations after changes, including newly
   satisfied promises as well as regressions (operation P10; lanes P2).
6. Hand off proof and residuals, not an unexplained executable or a worker's unsupported
   claim (lanes P5–6). Presentation P8 applies that principle to UI review requests.

## State and future contract checks

These details follow method documents P2 and settling P1–4; they do not create a new state.
All our direction files currently remain DRAFT. The steward approved the change of direction,
not every new quantitative bound or newly written sentence. Ratification is a distinct
recorded word; locking has additional conditions. A ratified document can be amended in
place with its changelog; a locked one needs a candidate beside it. Keep promise identities
stable, including retired numbers; unchanged split-out promises carry their prior state.

Under ledger P10 a draft seeds no formal row. On actual contract ratification, establish
a real judged revision and the check header/rows prescribed by ledger P1–2 and P9, with
the five verdicts and evidence duties in verdicts P1–6. Do not turn a draft work table into
that ledger. Publication establishes a real source revision, not a formal judged verdict.

## Compatibility boundary

The checks here validate document structure, source fingerprints and work references.
They do not certify visual quality, latency, method-wide operational conformance or future
Converge ingestion. The archive does not specify a final import/wire schema. We retain
ordinary paths, stable promise numbers, state headings, changelogs and source provenance
so a future adapter has explicit inputs; we do not claim it already exists.

The future service owns its records and store (family principle "API is the truth";
service store P1 and P3). Do not create its database, invent routes, or mutate its records
from this project. Local PLAN and ACCEPTANCE notes are readable work/evidence artifacts,
not pretend service records or a parallel control plane. Future attachment goes through
the service's actual supported interface when available.

Run `uv run --no-sync python scripts/check_direction.py` for structural checks. Add
`--archive amplifier-converge-vision-contracts-20260909T213649Z.zip` for local source verification.
Keep that private archive untracked and out of distributions. Runtime evidence is separate.
