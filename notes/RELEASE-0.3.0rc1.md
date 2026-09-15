# Amplifier TUI 0.3.0rc1

Private early-access candidate, not a claim of complete CLI/Codex parity.
Built from `b4a491d79df5a80295db02247e3d9237701764e5`.

## What is new

- Full-height-looking native primary screen, retained terminal/tmux history, edge-to-edge
  borderless input, compact controls and syntax-coloured Markdown/code inspection.
- Paged conversation pickers and bounded content search across saved conversations.
- Explicit immutable PNG/JPEG attachment, observed instruction sources, advisory model
  discovery and an offline provider/model setup wizard.
- Guarded completed/nested/routed child continuation, independent persistent child storage,
  refreshing child lists and recipe review/recovery improvements.
- Shorter completion messages, input-preserving resize fallback, owned partial-startup
  cleanup, truthful Resume readiness and explicit uncertain-follow-up resolution.

## Install

Access to this private repository, uv and Git are required. Authenticate GitHub without
putting credentials in URLs. Download the wheel matching your architecture from the
release assets, then run `uv tool install ./<downloaded-wheel>.whl`. No Rust/Cargo is
needed for wheel installation. Git source installation remains available and needs Rust
and a linker: `uv tool install git+https://github.com/bkrabach/amplifier-app-tui@v0.3.0rc1`.

Linux candidates are built on Ubuntu 24.04 for ARM64 and x86-64; they are not manylinux
or musl portability claims. macOS wheels are separate ARM64/Intel binaries, not universal2;
their deployment floors are macOS 14 and 15 respectively. Windows uses WSL2.

Run `amplifier-tui --getting-started`, then `amplifier-tui --check`. Supply the selected
provider's environment credential for live work, or use `--fixture` for a clearly labelled
scripted smoke test. First launch resolves executable bundle/module dependencies; load
only trusted sources. Model calls incur charges. The app is not an OS sandbox.

Upgrades do not import shared CLI settings/credentials, rewrite old compositions or replay
tools. Conversation state is separate from the installed environment. Relaunch to load
changes. Existing development-command symlinks continue to use their checkout, not this wheel.

## Evidence and limits

Acceptance, live receipts, source fingerprints and benchmark scope are in
[ACCEPTANCE](https://github.com/bkrabach/amplifier-app-tui/blob/main/notes/ACCEPTANCE.md).
Release receipts accompany each wheel. Native unit/install
checks on a platform are not terminal-emulator or live-provider certification there.
Linux ARM64 has the interactive PTY/tmux and installed-live evidence.

Known residuals include cancellation callback warnings and uncooperative cleanup,
interrupted/custom-orchestrator/subprocess child recovery, multiple/clipboard images,
semantic references, large-store indexing, causal Git/test attribution and matched
CLI-policy performance. Contracts remain DRAFT; no formal Converge verdict is implied.
