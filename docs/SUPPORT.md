# Troubleshooting without sharing your conversation

Start with `amplifier-tui --check`. This is a local inspection, not a connection test.
Exit 1 means a known local blocker; exit 0 may include warnings or unverified custom
provider requirements. No check proves the bundle, network or API account will work.

| Symptom | Next step |
|---|---|
| Private repository not found / authentication fails | Confirm repository access and Git authentication; never embed a token in the URL |
| Build asks for Cargo or a linker | Install a Rust/Cargo toolchain and your platform's C build tools, then reinstall |
| Installed command not found | Follow uv's PATH instructions and open a new terminal |
| Native binary missing or not executable | Reinstall; workspace developers must build Ratatui explicitly |
| Default provider key missing | Supply ANTHROPIC_API_KEY through the environment; do not paste it into chat |
| Custom provider still fails despite passing checks | Local checks do not resolve custom configurations or validate credentials; review the trusted overlay and provider's error |
| First startup is slow | It may be resolving sources/installing dependencies; cached starts differ from cold starts |
| First launch after upgrade installs modules again | Reinstallation rebuilds the isolated tool environment; allow network access and omit --no-install for that launch |
| App says it needs a terminal | Launch from an interactive terminal, not a redirected pipe; diagnostics do work in pipes |
| Saved conversations are missing | Check which --state-dir you selected; the installed and workspace launchers use different defaults |
| Resume refuses changed/missing configuration | Preserve original state and recorded paths; do not edit checkpoint files to bypass validation |
| Assistant appears to wait forever | Look for Review decision or Answer question; use the Help topic “When the assistant waits” |
| Copy/scroll behaves differently in a menu | Escape to normal conversation for terminal-owned selection, or use Transcript inspection |

## A useful, limited report

Run `amplifier-tui --support-report`. It prints allowlisted JSON: app/Python version,
platform/architecture and local check statuses with fixed guidance. It intentionally
omits paths, environment values, usernames, hostnames and conversation content. It does
not read saved conversations or configuration files. Review it before sharing, and add:

1. What you expected and what actually happened.
2. The smallest reproduction steps, with private prompt/file content replaced.
3. Whether this is a live preset, custom composition, or scripted fixture.
4. Terminal/tmux versions if relevant, without machine names or full configuration dumps.

Share with the maintainer through an agreed channel. Nothing is uploaded automatically.
Do not attach API keys, raw state directories, transcripts, full environment dumps or
unreviewed screenshots. `--doctor` contains local paths and is **not** the path-free
support report. Exports and screenshots can contain private work even without a key.

The app is still early: cancellation warnings, uncooperative module cleanup, multiple or
clipboard image input, broader state migration and matched CLI performance remain open.
Single confirmed workspace PNG/JPEG attachment is supported. See the maintained
[coverage map](../notes/PARITY.md) and [verification evidence](../notes/ACCEPTANCE.md).
