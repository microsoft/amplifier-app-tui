# Amplifier TUI

This codebase is yours: what it's for and how it's built are your call, and you'll keep building on it.

Read docs/VISION.md, contracts/, notes/CONVERGE.md, notes/PLAN.md, notes/ENGINE-BOUNDARY.md and SMOKE_TESTS.md before changing behavior.
Keep runtime imports in host/composition and their app-policy adapters; widgets consume identified events only.
Independent modules may import kernel contracts, but never the host package or widgets.
Prefer independent host/module replacements; honor each upstream repo's rules if a demonstrated seam fix is needed. Never put UI policy in the thin kernel.
Contracts are DRAFT. User authorized implementation; no formal verdict rows until ratification.
Run `PYTHONDONTWRITEBYTECODE=1 uv run --no-sync pytest -q`, `uv run --no-sync ruff check .`, and SMOKE_TESTS.md.
Use real Foundation/core integration in tests; deterministic providers are explicitly fixtures.
Record evidence and remaining scope in notes/ACCEPTANCE.md, never as vision status.
Do not include private handoff archives, credentials, user transcripts, or machine paths in commits.
Before publishing, review unpublished ancestors as well as the working diff. Deleting a private handoff in a later commit does not remove it from published history. Preserve local work and publish a reviewed clean snapshot on upstream ancestry when necessary; never rewrite or discard the user's private history.
Use `uv sync --inexact --no-sources` so dynamic module dependencies survive and canonical main dependency declarations win over the CLI dependency's development source table. Use `--no-sources` for tool installation too. Keep source HEAD and runtime release evidence distinct.
Amend direction before deriving changed work; cite promise IDs in notes/PLAN.md. Use scripts/check_direction.py; it validates structure, not behavior or ratification.
Keep design and user guidance current: replace obsolete descriptions instead of adding change logs, migration layers or compatibility promises for disposable test sessions. Retain source-control history and truthful current verification evidence.
Textual is a retained harness, not the target. Compare Ratatui/OpenTUI using notes/FRONTEND-EVALUATION.md and notes/PERFORMANCE.md before selecting frontend or topology.
Developer-run captures and checks precede a specific steward review question. No fixture-as-product review and no unmeasured speed claim.
Native candidates live under frontends/; build both before TUI_TEST_CANDIDATES=1. See SMOKE_TESTS.md for locks, PTY capture, benchmark and live gates.
CLI helpers are upstream app policy, not a kernel API. Establish the host's CLI home/cwd before importing them (CLI bootstrap reads its key store); never retarget those process globals while another session is live. Compare against the actual installed resolver when updating dependencies. Resolve Amplifier main branches afresh during qualification; lockfile commits record evidence, not an update freeze.
Keep scene, fixture-runtime and live-runtime labels distinct. Preserve the installed CLI's foreign-home guard; baseline environments belong under this project's .state, never the daily shared environment.

## Ecosystem maps

Keep this repository's README and product-page maps aligned with the
[Constellation map guide](https://github.com/microsoft/amplifier-constellation/blob/main/docs/ecosystem-maps.md)
and its canonical registry; start with this repository's
`docs/ecosystem-map.json`. When creating, renaming, splitting, retiring, or
changing a role, interface, parent, or dependency, inspect incoming and outgoing
relationships and update every affected parent/consumer map and link, including
the centralized product pages. Regenerate from source data and synchronize local
records/images rather than hand-editing generated images. Describe actual
boundaries and optional choices; a role highlight is not a compatibility claim.
Documentation work does not authorize deployment or resume paused product work.
