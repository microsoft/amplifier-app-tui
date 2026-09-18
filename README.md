# Amplifier TUI

A native terminal workspace for conversations, tools and delegated work, powered by
Amplifier's bundles and swappable modules. Describe a task, review decisions, inspect
changes, and return to saved conversations. The normal view uses your terminal's
selection and scrollback; conversation output remains after exit.

This is an early product. Audited CLI workflows are available through native controls
or explicit pinned-CLI handoff, not a duplicate native wizard for every command. The
working frontend is Ratatui; Textual and OpenTUI are development/comparison harnesses. See the
[coverage map](notes/PARITY.md) and [verification record](notes/ACCEPTANCE.md).

## Install the native product

You need uv, Git and access to this private repository. Source installation also needs
Rust/Cargo and a C linker; ordinary launches do not need a compiler.

```sh
uv tool install --no-sources git+https://github.com/bkrabach/amplifier-app-tui
amplifier-tui --getting-started
amplifier-tui --check
```

Authenticate Git through your usual credential helper, never a token in the URL.
Keep `--no-sources`: it honors the packaged dependency pins instead of the CLI
dependency's development source table, which otherwise conflicts with the Foundation pin.
For compiler-free installation, download the matching wheel from the private
[release page](https://github.com/bkrabach/amplifier-app-tui/releases)
and run `uv tool install --no-sources ./<downloaded-wheel>.whl`. These published wheels do not
include later checkout changes; use the paired receipt to identify tested source.

| Machine | Published wheel / tested build floor |
|---|---|
| Linux ARM64 | `linux_aarch64` / Ubuntu 24.04 |
| Linux x86-64 | `linux_x86_64` / Ubuntu 22.04 |
| Apple Silicon Mac | `macosx_14_0_arm64` / macOS 14 |
| Intel Mac | `macosx_15_0_x86_64` / macOS 15 |

Linux ARM64 has interactive/live verification. Other listed platforms have native,
install and installed fixture gates at the released revision, not physical-terminal
certification. No musl/manylinux/universal2 claim; Windows requires WSL2.

## Start working

Open your project directory and run `amplifier-tui`. Ordinary new launches use your
Amplifier CLI settings, selected bundle, providers and configured behaviors. Those
hooks may contact their configured services during startup. Sources are executable
code; trust them before launching. First launch may download/install dependencies.
Model calls cost money; filesystem and shell tools are not an OS sandbox.

Use `--settings-policy isolated` to opt out of CLI configuration; its default preset
needs `ANTHROPIC_API_KEY`. Explicit `--preset`, `--bundle` or `--overlay` also defaults
to isolated policy. `--setup` creates a reviewed provider overlay, not a stored key.
No key yet? `--fixture` is a labelled scripted demo with a real digest tool, not AI.

Type a task and press Enter. Alt+Enter adds a newline; paste never sends. Tab reaches
visible controls or completes text. Open **Actions** to browse Write and attach,
Current task, Conversations, Review and copy, or Tools and setup. Typing searches
across all groups; familiar slash commands remain available. Escape keeps your draft.

While work runs, **Queue** saves a later task. **Change task** sends a separate
correction at its next input boundary; it does not interrupt a running tool.
Pending follow-ups lets you pause, edit, remove and
explicitly release queued work. Stop requests cancellation, not rollback. Questions
and permissions require distinct, explicit answers; neither is submitted for you.
An uncooperative module can delay cancellation; stopping does not undo tool effects.
Ctrl-C while working is **graceful Stop and stay**, retaining your draft: current
model/tool calls finish and nested agents wind down before their parents. The
indicator shows “Finishing current calls”; Ctrl-C again (or Force stop) interrupts
immediately. Graceful Stop never escalates on a timer. Ctrl-C while idle asks whether
to quit, defaulting to **No**; Enter or Escape stays. Ctrl-Q or Actions → Quit
explicitly exits even during work. A selected
transcript region still gives Ctrl-C its copy behavior. Cleanly stopped turns can
resume normally without replaying tools. If completion cannot be verified or saved
context is incomplete, Resume offers explicit recovery into a new conversation,
preserving the original and disclosing unknown effects.
Configured session naming supplies automatic titles after enough conversation context;
an explicit Rename always takes precedence.

Use normal terminal selection or tmux copy mode (usually prefix then `[`) to copy
conversation text. Actions → Transcript offers reflowed inspection and exact source
copy; native history cannot reflow already committed rows. Exit leaves history intact.

Tools and public thinking use compact summaries. Open **Activity** beside Actions
(Tab to focus, then Enter, or `/activity`) to inspect them. Click a row or press Enter
to open its preview, child agents/tools, and source evidence; Back goes up a level,
Escape returns to your draft. Activity updates while work runs without submitting
anything. Missing observations and bounded excerpts are not a complete private trace.
Native terminal/tmux history stays selectable: its old rows do not become clickable.
Agent summaries lead with a short task title, followed by identity and progress.
Titles come from an instruction heading or opening excerpt, with no extra model call.
Expand the row for the original request; continuing an agent starts a new task title.

For inline expansion, use **Interact** (Tab to the control, then Enter, or `/interact`).
Click a tool/thinking/usage summary, or use Up/Down and Enter, to open its preview in the
conversation. Its **Activity** link opens child agents, tools and full observed evidence.
Escape leaves interaction and restores native copying; your unsent draft is retained.
Mouse capture is explicit, never enabled over ordinary terminal history.

Todo updates show reported done/total, active and pending counts plus the current
task. Expand for a checklist; Activity retains the exact request/result. A successful
todo update does not mean its tasks are done. Composer input wraps by words, with
grapheme fallback for long paths; display wraps never add newlines to your message.

Startup shows the preparation phase while you can type. Active delegate summaries
identify their task and latest observed child activity. Per-call usage is one line,
directly below activity; only an assistant response keeps a blank line before usage;
expand it for full routing, time, duration, cache-aware input/output/total and cost. Turn and
session costs include observed child calls; absent cost is unknown, not zero. Older
conversations without per-call accounting disclose unavailable earlier usage.
While a turn runs, its working indicator shows elapsed time, reported call count,
cumulative **Turn usage**, turn cost and session cost, including agents. Repeated
inputs count again per call: this is usage, not the current context size. Time advances during
quiet waits and cancellation draining, including live delegate durations; hour-long
turns retain seconds. Tokens and dollars update when calls report usage. Narrow views wrap
the totals above the composer. Pending/partial accounting is labelled explicitly.

Choose a colour treatment at launch: `AMPLIFIER_TUI_THEME=light amplifier-tui`,
`AMPLIFIER_TUI_THEME=terminal amplifier-tui`, or `NO_COLOR=1 amplifier-tui`.
The default follows muxplex's brand: blue-black transcript, charcoal composer/user
messages, cool white conversation, muted secondary text, cyan actions and amber
activity, with red stopping/stopped states and Stop/Force controls. Cancellation
explanations stay solid red while the stopping label shimmers. Code highlighting
uses the same palette; image previews keep their own
colours. Running tools and observed Thinking/Responding/model-wait, Working/Stopping
and background labels have a gentle brighter sweep. Completed thinking stays muted
and static. `AMPLIFIER_TUI_REDUCED_MOTION=1 amplifier-tui` disables the sweep without
stopping elapsed-time updates. Waiting for your answer is static; idle does not animate.
`terminal` uses your terminal's colours; `NO_COLOR` also disables explicit colours
and shimmer. These options change presentation, never saved content.

If `write_file` or `edit_file` refuses an out-of-scope directory, creating it with
`mkdir` does not grant access. Review `/allowed-dirs` and `/denied-dirs`, then, only
if intended, use `/allowed-dirs add /path/to/narrow-directory`. Denied paths still
win. This persists for the current root session, not children, shell commands or
shared settings, and is not an OS sandbox.

Resume shows only conversations from the directory you launched in (or explicitly
selected with `--cwd` for a new launch), matching the CLI's directory-local behavior.
Parents, children and siblings are separate; symlink aliases of the same resolved
directory agree. Picker search/pages, `--list-sessions`, `--resume latest` and explicit
resume IDs share that scope. No matches never falls back to other directories.
Launch from an old conversation's directory to return to it; its saved composition
and policy remain unchanged. Changing your shell directory never expands its access.

## Return, upgrade, or get help

`amplifier-tui --resume` opens a picker. Reopening does not replay tools or release
queued work. Installed state defaults to `$XDG_DATA_HOME/amplifier-tui` (usually
`~/.local/share/amplifier-tui`); `--state-dir` selects another store. Saved conversations
retain their recorded composition. CLI import is deliberate and creates a new identity.

Upgrade with `uv tool install --no-sources --reinstall git+https://github.com/bkrabach/amplifier-app-tui`.
The first launch afterward may reinstall module dependencies; omit `--no-install` then.
Saved conversation state is separate from the tool environment.

- [Your first conversation and controls](docs/GETTING-STARTED.md)
- [Resume, migration, provider login and session controls](docs/MIGRATION.md)
- [Troubleshooting and safe reports](docs/SUPPORT.md)
- [Account and service verification boundaries](docs/SERVICE-VERIFICATION.md)

`--check` is local only. `--support-report` prints allowlisted, path-free diagnostics;
review before sharing. `--doctor`, exports, screenshots and raw state can contain
private paths or work; they are not public bug-report attachments.

## Develop

Read [AGENTS.md](AGENTS.md), [vision](docs/VISION.md), [plan](notes/PLAN.md) and
[verification guide](SMOKE_TESTS.md). Bundles/modules own runtime policy; the TUI does
not add UI policy to Amplifier's thin kernel. The [historical walkthrough](HISTORICAL-README.md)
retains source bootstrap, advanced commands and earlier evidence. Use `uv sync --inexact --no-sources`
to preserve dynamic module dependencies.

An explicitly installed development symlink to `scripts/dev-launch` follows this
checkout and incrementally builds the native client on launch. Relaunch to see changes;
running conversations are not hot-reloaded. It preserves your launch directory and uses
workspace state unless overridden. Keep the checkout while using that link; do not
overwrite another installed command. No release publication is implied by local changes.
