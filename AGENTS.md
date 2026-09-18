# Amplifier TUI

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
Use `uv sync --inexact --no-sources` so dynamic module dependencies survive and published direct pins win over the CLI dependency's development source table. Use `--no-sources` for tool installation too. Keep source HEAD and runtime release evidence distinct.
Amend direction before deriving changed work; cite promise IDs in notes/PLAN.md. Use scripts/check_direction.py; it validates structure, not behavior or ratification.
Textual is a retained harness, not the target. Compare Ratatui/OpenTUI using notes/FRONTEND-EVALUATION.md and notes/PERFORMANCE.md before selecting frontend or topology.
Developer-run captures and checks precede a specific steward review question. No fixture-as-product review and no unmeasured speed claim.
Native candidates live under frontends/; build both before TUI_TEST_CANDIDATES=1. See SMOKE_TESTS.md for locks, PTY capture, benchmark and live gates.
CLI helpers are pinned app policy, not a kernel API. Establish the host's CLI home/cwd before importing them (CLI bootstrap reads its key store); never retarget those process globals while another session is live. Compare against the actual resolver when changing the pin.
Keep scene, fixture-runtime and live-runtime labels distinct. Preserve the installed CLI's foreign-home guard; baseline environments belong under this project's .state, never the daily shared environment.
