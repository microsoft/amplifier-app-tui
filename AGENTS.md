# Amplifier TUI

Read docs/VISION.md, contracts/, notes/CONVERGE.md, notes/PLAN.md, notes/ENGINE-BOUNDARY.md and SMOKE_TESTS.md before changing behavior.
Keep runtime imports in host/composition; widgets consume identified events only.
Independent modules may import kernel contracts, but never the host package or widgets.
Prefer independent host/module replacements; honor each upstream repo's rules if a demonstrated seam fix is needed. Never put UI policy in the thin kernel.
Contracts are DRAFT. User authorized implementation; no formal verdict rows until ratification.
Run `PYTHONDONTWRITEBYTECODE=1 uv run --no-sync pytest -q`, `uv run --no-sync ruff check .`, and SMOKE_TESTS.md.
Use real Foundation/core integration in tests; deterministic providers are explicitly fixtures.
Record evidence and remaining scope in notes/ACCEPTANCE.md, never as vision status.
Do not include private handoff archives, credentials, user transcripts, or machine paths in commits.
Use `uv sync --inexact` so dynamic module dependencies survive. Keep source HEAD and runtime release evidence distinct.
Amend direction before deriving changed work; cite promise IDs in notes/PLAN.md. Use scripts/check_direction.py; it validates structure, not behavior or ratification.
Textual is a retained harness, not the target. Compare Ratatui/OpenTUI using notes/FRONTEND-EVALUATION.md and notes/PERFORMANCE.md before selecting frontend or topology.
Developer-run captures and checks precede a specific steward review question. No fixture-as-product review and no unmeasured speed claim.
Native candidates live under frontends/; build both before TUI_TEST_CANDIDATES=1. See SMOKE_TESTS.md for locks, PTY capture, benchmark and live gates.
Keep scene, fixture-runtime and live-runtime labels distinct. Preserve the installed CLI's foreign-home guard; baseline environments belong under this project's .state, never the daily shared environment.
