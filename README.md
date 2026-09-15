# Amplifier TUI

New here? Start with the [first-conversation guide](docs/GETTING-STARTED.md).
Already installed? `amplifier-tui --getting-started` works offline, and `--check`
explains local setup blockers without opening a session. In the app, **Actions →
Getting started** opens task-based help without sending anything.
For a problem report, see [safe troubleshooting](docs/SUPPORT.md).

**Current status:** Ratatui is the working integration client: discoverable actions,
focused decisions, structured questions, read-only Git review, active corrections, scoped model selection, Markdown, line scrollback, editor history/completion and saved
Amplifier conversations. OpenTUI remains the earlier comparison
candidate; Textual remains a regression harness. Neither a final architecture decision
nor complete CLI parity is claimed.
Read [current direction](docs/VISION.md), [derived work](notes/PLAN.md), and
[what the comparison evaluates](notes/FRONTEND-EVALUATION.md).
The [workflow coverage map](notes/PARITY.md) separates working paths from remaining parity gaps.

## Work with Amplifier

### Install the native product

Linux ARM64 has interactive PTY/tmux and installed-live verification. Candidate native
unit/build/install gates also pass on Linux x86-64 and both macOS architectures; broader
terminal/live-runtime coverage there remains open. Windows needs WSL2.
Git installation requires **uv, Git, Rust/Cargo (tested
with Rust 1.93), and a C linker**. The build embeds the native executable in a
platform-specific wheel; normal launches need neither a source checkout nor Cargo.

The private [0.3.0rc1 prerelease](https://github.com/bkrabach/amplifier-app-tui/releases/tag/v0.3.0rc1)
provides compiler-free wheels. Authenticate with an account that has repository access,
download the matching wheel, then run `uv tool install ./<downloaded-wheel>.whl`.

| Machine | Wheel platform suffix | Build/install gate |
|---|---|---|
| Linux ARM64 | `linux_aarch64` | Ubuntu 24.04 |
| Linux x86-64 | `linux_x86_64` | Ubuntu 24.04 |
| Apple Silicon Mac | `macosx_14_0_arm64` | macOS 14 |
| Intel Mac | `macosx_15_0_x86_64` | macOS 15 |

Linux wheels are not manylinux/musl or older-distribution compatibility claims. macOS
wheels contain one architecture each, with the named deployment floor, not universal2.
Each asset has an adjacent SHA-256/install receipt. `scripts/release_wheel.py` and the
manual four-platform workflow verify isolated installation with Cargo absent and native
executable loading. This is an early candidate, not complete cross-platform certification.

The repository is private. Authenticate GitHub/Git with an account that has access
(for GitHub CLI users, `gh auth login` then `gh auth setup-git`), then:

```sh
uv tool install git+https://github.com/bkrabach/amplifier-app-tui
amplifier-tui --version
amplifier-tui --doctor
amplifier-tui
```

Set `ANTHROPIC_API_KEY` in your environment for the default live preset. No credentials
are imported from the shared CLI. `--fixture` is a credential-free scripted-provider
smoke test, not an AI assistant. First launch resolves the real bundle/module sources
and installs their declared dependencies into the app's isolated tool environment.
It requires network access and can be slower than subsequent cached starts. Bundles
and modules are executable code: only select sources you trust.

For Anthropic or OpenAI configuration, run `amplifier-tui --setup`: choose a provider,
exact model ID and **new** overlay path, review the configuration, then confirm creation.
The offline wizard writes a private environment-reference overlay, never a key or shared
CLI settings. Launch with the printed `--overlay` command. It does not validate model
availability/credentials; review or pin the declared module source before trusting it.

State defaults to `$XDG_DATA_HOME/amplifier-tui` (normally
`~/.local/share/amplifier-tui`), separately from the CLI. Override with `--state-dir`
or `AMPLIFIER_TUI_STATE_DIR`. Use `amplifier-tui --resume` for the picker. Existing
workspace conversations stay in their original state directory: opt in with
`--state-dir /path/to/project/.state/work --resume`; their saved local composition
paths must still exist and configuration/history guards still apply. Upgrading does
not silently add new overlays to old conversations, migrate credentials, or replay work.

Upgrade explicitly:

```sh
uv tool install --reinstall git+https://github.com/bkrabach/amplifier-app-tui
```

Reinstallation rebuilds the isolated tool environment. The next normal launch may
reinstall bundle/module dependencies; allow network access and do not use `--no-install`
for that first post-upgrade launch. Conversation state lives outside that environment.

`--check` explains local prerequisites and returns exit 1 for blockers (0 may include
warnings). It does not validate API keys, download modules or certify live readiness.
`--support-report` emits allowlisted, path-free JSON for sharing, with the same exit codes.
It does not read configuration files or conversations; review it before sharing.
`--doctor` is a local, read-only installation report: app/interpreter/native binary,
state path and source policy, with no credential values or model calls. System in the
TUI also names the running app version. `amplifier-tui-host` retains the diagnostic
headless/bridge/historical harness entrypoint; ordinary `amplifier-tui` is Ratatui.

### Development workspace

To track uncommitted changes through the ordinary command, a developer can explicitly
symlink `scripts/dev-launch` into a directory on PATH as `amplifier-tui` (do not overwrite
an existing command). The link resolves this checkout's `.venv` and workspace state,
preserves the directory you launch from, and runs an incremental locked Cargo build before
interactive native launch. Relaunch to pick up changes; running sessions are not hot-reloaded.
Help/version/doctor/check/report commands do not build. Python dependency changes still
need `uv sync --inexact` in the checkout. `--state-dir` can explicitly select another store.
Remove only that development symlink before switching to a Git-installed release; do not
delete conversation state. The link depends on the checkout remaining at its current path.

From this project directory, after the source/dependency setup below:

```sh
cargo build --release --locked --manifest-path frontends/ratatui/Cargo.toml
uv run --no-sync python scripts/run.py
```

This is **live execution**, not the design scene. It loads the actual `anchors` preset
and the explicit `examples/anthropic.yaml` overlay (Haiku 4.5), requiring
`ANTHROPIC_API_KEY` in your environment. Model calls incur charges. It does not import
your daily CLI settings or stored credentials. Use `--preset anchors-amp-dev` for the
development preset, `--overlay path/to/provider.yaml` for another provider, or `--bundle`
plus ordered overlays for a custom composition. `--cwd` selects the tool workspace.

For a credential-free real-kernel check with a scripted provider and an actual approval/tool:

```sh
uv run --no-sync python scripts/run.py --fixture --overlay examples/fixture-approval.yaml
```

Type a request and use **Send** or Enter. **Actions** opens searchable local choices;
Tab completes an eligible query; otherwise Tab/Shift+Tab focus visible controls and
Enter activates them. The normal view leaves mouse selection/scrolling to your terminal;
mouse controls are enabled inside fullscreen menus and inspection views. F4 opens Actions.
Slash in an empty composer opens Actions; pasted slash text never does. Escape returns
to the unchanged draft. Alt+Enter inserts a newline; F4 is an optional Actions shortcut.

**Review decision** opens the actual question and runtime-provided options. Type to filter,
use arrows to choose and Enter to answer; PageUp/PageDown scroll a long question and
its exact option descriptions. A new approval does not steal typing focus. Actions also
provides evidence/copy, sent-message recall, stop, help, and quit. Closing history without
selecting keeps the current draft; selecting replaces it explicitly. Nothing in an action
search goes to the model. Older Ctrl accelerators remain optional compatibility bindings.

**System** shows mounted tools/providers and authored agent definitions; **Skills** in
Actions shows the module's startup discovery catalog without loading a skill. Ask the
assistant to invoke `load_skill`, `delegate` or `recipes` when mounted. **Actions → Modes**
(`/mode`) selects discovered session policy with explicit Apply.
Assistant mode requests needing consent use **Review decision**, not an unanswerable retry.
Conversation-provider selection and steering use supported public module capabilities.
Use **Insert text file** for UTF-8 snapshots and **Attach image** for one PNG/JPEG up to
2 MiB. The image dialog shows path, size and digest, not a rendered thumbnail. Confirm
the captured bytes, add your prompt, then Send explicitly. File changes after capture do
not change the attachment. All mounted providers must advertise vision support; actual
format/model limits can still reject a request. Images enter Amplifier's public context
format, without replacing the orchestrator. **Attached image** inspects/removes the
reference. Attaching pauses the queue; queued image turns are not supported. Unsent
images survive ordinary resume; dispatched images never silently become unsent again.
Historical recovery does not copy attachments, and removing a reference is not rollback.
Full presets retain authored shell/file tools and permissions: **this is not a sandbox**.
The workspace launcher stores state in this project's `.state/work`; the installed
launcher uses the separate user-data directory described above.

### Reading, editing and returning

- **Actions → Delegated work** (`/agents`) lists observed child work, including running,
  waiting for permission/answers, and terminal outcomes. Open a child, then **Inspect this
  child's tool and text observations** for scoped evidence. The list refreshes once a second
  while open, preserving selection/filter; detail pages remain explicit snapshots. A restored
  row is historical, not a running agent. Parent completion never proves every child tool
  succeeded. This is observed session activity, not an OS process monitor.
- **Actions → Recipe activity** lists observed recipe tool calls. Open a receipt and
  **Prepare recipe review request** to append a review request to your draft; it does not
  execute or approve anything. After reviewing completed/unfinished steps, explicitly ask
  the assistant to resume the chosen session. The real v2 runner's completed-step skip
  behavior is tested across reopening; unfinished steps can be retried and may have partial effects.
- **Actions → Search saved conversations** searches saved titles/IDs/directories and recent
  user/assistant message text, without opening sessions or calling a model. Previous/Next
  pages inspect 100 conversations each; partial scans are disclosed. Startup Resume uses
  PgUp/PgDn for pages and typing filters the visible page.
- **Actions → Instruction sources** shows last-observed Foundation mention resolutions,
  with source paths and content hashes where supplied. It is not a complete current
  provider request or proof that the model used a source; inspection does not rebuild context.
- **Actions → Model catalog** explicitly queries mounted providers' reported model IDs
  (possibly network-backed or static). Enter copies an ID for `--setup`/an overlay;
  it does not select a model, validate access or alter routing. Missing/failed catalogs
  remain visible. Conversation provider selection retains its existing mounted-instance guards.
- **Actions → Activity evidence** (`/activity`) consolidates tool, approval, question and
  correction observations with conversation, turn, call and sequence identities. It is not
  Git authorship or proof of test coverage. Inspection indexes the latest 256 identities,
  returns up to 100 rows / 1 MiB, and labels detail excerpts over 16 KiB. Full root tool
  results remain in ordinary evidence/export; child observations are bounded excerpts.
- **Actions → Context intelligence** (`/context`) shows observed provider usage/compaction
  and the configured local-capture/remote-dispatch policy. Missing observations mean
  unavailable, not zero usage. This is not an exact current context meter and does not
  call a provider, compact context, or connect to a server. Composition detail stays separate.
- **Actions → Saved local drafts** (`/drafts`) retains copies of answer/correction editor
  text with original request scope, separate from model context. Open to copy or explicitly
  remove. Text may already have been submitted; its saved copy is not an admission record.
  It never auto-submits or retargets after restart/recovery. Limits: 32 drafts / 2 MiB total,
  65536 characters each; autosave after a 250 ms input pause, plus editor dismissal/submission
  and normal quit. Sudden death before a save can lose the latest edit. Storage errors are
  visible; copy the text before exiting. Recovered drafts retain their original conversation ID.
- **Actions → Insert text file** (`/attach`) reads one explicitly named workspace-relative
  UTF-8 file, up to 64 KiB, then previews its captured content, path and SHA-256. Choose
  **Insert captured text** to add it to the unsent composer. Sending shares those captured
  bytes with the configured model; later file changes do not silently update them. This is
  text, not a live attachment. Symlinks, parent traversal, binary/control content and files
  changing during the read are refused. Completion still reads filenames only.
- **Actions → Edit in external editor** (`/editor`) runs your `VISUAL`, then `EDITOR`, or
  `vi` while work is idle and the queue is empty/paused. Commands may include arguments;
  these are your shell commands, never model-supplied editor commands. A private temporary
  file is removed afterward. Successful UTF-8 text (up to 256 KiB) returns to the unsent
  composer; editor failure retains the original. Terminal history is preserved.

- The ordinary conversation uses **native terminal history**. Select/copy with your
  terminal or enter tmux copy mode (normally prefix then `[`) and scroll across pages.
  Completed output remains after exit; the composer stays compact beside recent output.
  No `/scrollback` detour or tmux configuration change is required. Terminal history
  limits still apply. Completed Markdown blocks accumulate while streaming; the unfinished
  block remains a live preview until stable or finalized. Terminal rows are not the
  canonical conversation store, and are not rewritten to reflow old text on resize.
  Initial history replay prints the latest 1,000 items with an explicit notice when
  older items are omitted. The full retained source remains in Transcript/export;
  this replay bound does not cap new output emitted during the open conversation.
  **Actions → Transcript** opens full-source, width-aware inspection. There, drag plus
  wheel/edge scrolling selects a snapshot (up to 20,000 lines / 2 MiB), and **Copy selection**
  or Ctrl+C copies it through OSC52. Resize clears that local selection.
  Escape returns from inspection; **Native scrollback** (`/scrollback`) also returns to
  the normal composer without emitting another snapshot. Enter there sends/queues text
  normally—it is no longer a read-only snapshot mode. Paste alone never submits.
  **Actions → Export conversation** (`/export`) saves the full retained transcript as
  private Markdown (16 MiB journal bound), including interrupted text and tool outcomes.
  Clipboard delivery uses OSC52 and depends on terminal support; export does not.
- A waiting question has a visible **Answer question** button above the composer,
  including narrow terminals. Choose/write an answer, then **Submit reviewed answers**.
  This is separate from granting tool permission and preserves the main draft.
- **Actions → Modes**, `/mode NAME`, and `/mode clear` use the composed mode module.
  Human choices require confirmation while idle; model requests retain tool hooks and
  explicit approval for warn/confirm gates. Mode definitions are checked on resume.
  The header persistently shows **Mode: plan** (or the current mode / default), including
  after reopening. **Modes** above the composer opens its controls; unavailable means
  the current composition does not provide the supported mode module.
- **Actions → Code blocks** (or `/code`) lists code from retained assistant replies.
  Open a block to inspect its message/block identity, copy its parsed code content without
  Markdown fences, or jump to its source message. Copy never executes code or edits a file.
  The view is a captured snapshot—even if a response is still growing. Reopen the catalog
  to refresh it. Limits: 100 blocks / 16 MiB recent assistant source, 12000-character preview,
  1 MiB copy; oversized blocks explicitly disable copy. Source-message Markdown remains
  separately available through **Assistant replies**. Recognized languages are syntax-coloured
  in the snapshot; copying still uses the original code, not styled terminal cells.
- **Answer questions** appears when the assistant asks for clarification. Open it (or
  **Actions → Questions**), choose an offered answer or **Write my own answer**, then
  **Submit reviewed answers**. Selecting an option alone sends nothing. Enter in the
  answer editor saves locally for review; Alt+Enter adds a newline. Escape retains local
  answers while the request is live; F2 copies editor text. The main composer stays yours.
  Explicit cancellation, timeout, or Stop supplies no answer and grants no permission.
  Completed outcomes are inspectable/copyable through Questions after resume.
  Limits: 1–3 questions/request, 6 choices/question, 65536 characters/text answer,
  4 concurrent requests, 20 requests/turn, up to 10 minutes waiting. Unsent answers
  are retained as separately scoped local drafts, never automatically delivered after
  recovery. `/questions` opens the same view.
  New launches automatically compose `examples/user-questions.yaml` before your explicit
  overlays. `--no-questions` omits it when your bundle supplies another implementation.
  Resume and in-app New retain the recorded composition; old conversations are not
  silently upgraded. Start a fresh launcher session to get the default question tool.
  To exercise this without AI:

  ```sh
  uv run --no-sync python scripts/run.py --fixture --overlay examples/fixture-questions.yaml
  ```

- **Actions → Workspace changes** (or `/changes`) reads Git status for the active
  workspace. Staged and unstaged entries open separate, labelled comparisons; PageUp/
  PageDown scroll the diff and **Copy observed diff text** copies it. Untracked paths
  are listed without reading their contents. This view never stages, reverts, commits,
  calls a model, or attributes existing changes to the agent. It is not test evidence.
  Limits: 500 rows, 1 MiB per Git output/decoded diff, 5 seconds per Git command.
  Ignored files and submodule contents are omitted; untracked directories are grouped.
  Binary diffs are summarized by Git. Changes during inspection are not an atomic
  snapshot; detected status/HEAD changes require refresh. External helpers and content
  filters are disabled, so comparisons can differ from your usual filtered Git output.
  Additions/removals use distinct colours; **Browse hunks in this snapshot** navigates
  up to 100 observed hunks without another Git read. Copying a hunk preserves that snapshot,
  not the latest file contents, and is labelled as an excerpt rather than a complete patch.
- **Actions → Correct active turn** opens a separate multiline correction editor;
  the main draft stays intact. Available after the first provider request in a supported
  orchestrator. Enter submits to that exact active turn; Alt+Enter adds a newline.
  **Pending** means admitted, **applied** means the runtime confirmed context insertion,
  not that the model obeyed or the task succeeded. Stop/failure or missing acknowledgement
  leaves **unconfirmed** text; it is never retried or queued automatically. A turn that
  finishes while you edit rejects the correction and keeps the editor text.
  **Actions → Corrections** inspects/copies the latest 100 corrections, including restored
  observations. Limit: 20 corrections per turn, 65536 characters each. `/steer` opens
  the editor. This does not promise to cancel or replace an already-running tool.
- **Actions → Conversation provider** (or `/providers`) lists mounted instances and
  provider-reported model defaults. Choose, then explicitly Apply while idle. This
  pauses queued follow-ups and saves the selection across resume. **Automatic** restores
  module priority selection. **Selection history** inspects/copies the latest 100 changes
  from a record capped at 1000 changes per conversation. Cross-vendor changes are refused
  by the selected orchestrator; model-role routing, goal utilities and delegated agents
  are unaffected. Unsupported orchestrators say so rather than simulating a switch.
  The default launch has one provider. To offer two actual models, use:

  ```sh
  uv run --no-sync python scripts/run.py --overlay examples/anthropic-models.yaml
  ```

  This explicitly mounts Haiku 4.5 and Sonnet 4.5, with Haiku first by priority. Both
  use your existing environment credential and bill at their respective provider rates.
  Author distinct provider `id` values in bundles (especially recursive includes);
  this host bridges them to the kernel's `instance_id`. The adapter also normalizes
  `instance_id` on the root and explicit overlays before composing them. It cannot
  recover instances already collapsed inside a recursively composed upstream bundle.
- **Pending N** above the composer (or **Actions → Pending follow-ups**) shows queued work and provides pause/run, edit,
  remove and copy controls. While a turn runs, Send changes to **Queue** and Enter
  queues the draft as a separate next turn—not a correction to active work. An enabled
  queue advances only after successful turn completion. Stop, failure, switching, mode/provider changes and
  reopening hold waiting work until you explicitly choose **Run pending follow-ups**.
  Editing also pauses the queue; Escape keeps the original queued text. Already-admitted
  work rejects edit/remove; use Stop instead. Queues retain up to 20 messages, each up
  to 65536 characters. `/queue` or `/pending` opens the same controls.
  To change the **current** turn instead, click **Steer** (or `/steer`), write the correction
  in its separate editor, then Enter. It targets that active turn, not the queue; the main
  draft stays untouched. The selected orchestrator must support steering, and work must
  have reached its first provider request. Applied means inserted into context, not obeyed.
- **Actions → Rename conversation** changes its display name without changing identity
  or context. **Find in conversation** searches retained message text locally, newest
  first; open a result to jump to it or copy its source. Search is bounded to 200 matches
  / 16 MiB of recent source and labels partial results. It does not search tool-detail
  JSON or another conversation. `/rename` and `/find` open the same dialogs.
- **Actions → Assistant replies** lists the latest 100 assistant blocks. Open one to
  read its source or copy Markdown via your terminal's OSC52 clipboard permission.
  Previews stop at 12000 characters; copy uses the complete original block, up to 1 MiB,
  and rejects larger blocks without silently truncating. `/replies` opens this list.

- Assistant Markdown renders headings, emphasis, lists/tasks, quotations, links and
  fenced code. Tables align and wrap cells at usable widths, then switch to labelled
  row/column values on narrow terminals; inline formatting stays intact. Completed code blocks
  and code inspection use bundled syntax highlighting (including Python, Rust, JavaScript,
  shell and JSON). Unfinished streaming code, unknown languages, `NO_COLOR`, and blocks beyond
  highlighting limits stay plain, without omitting source. Limits are 16 KiB per render,
  256 lines per block and 1024 bytes per line; oversized blocks are not partially coloured.
  Image loading and HTML execution are not implemented. Original source is retained.
- In transcript inspection, mouse wheel scrolls three **visual lines**; PageUp/PageDown move a viewport with
  overlap. Reading above the tail pins an item/line anchor while new output arrives.
  **Latest** (or Actions → Latest) returns to following output. Resize reflows from
  source and retains the anchored item, not an exact source-character position.
  In the normal view, PageUp opens source inspection; terminal/tmux scrolling stays native.
- The ordinary composer starts at one text row and grows to six, including soft wrapping.
  Launch opens a fresh full-height primary-screen workspace with the composer at the bottom;
  earlier shell output remains in native scrollback. Exit leaves the conversation behind.
  Transcript and composer use every column, without outer side padding. Input has no side
  borders or repeated prompt characters to contaminate terminal copying.
  Idle controls stay compact; Queue, Steer and Stop appear when work is active. Mode stays
  visible above the input. Renderer/live-runtime labels stay out of ordinary conversation;
  simulated/fixture runs still carry explicit warnings. Actions provides Work, Review and System.
  Startup accepts typing, but Enter before readiness does **not** send now or later.
  If a saved draft arrives after you started typing, your current editor stays untouched;
  **Saved draft → startup** exposes the original text for copying. Storage failures refuse
  to overwrite that original; copy your new text before exiting if saving fails.
- Up at the first visual editor line recalls the previous sent message; Down at the last
  line advances history. Down past the newest restores your original draft and cursor;
  Escape cancels recall. Within multiline text, arrows still move the cursor.
  Recall includes saved submissions from this app's other conversations in the **same
  resolved working directory and state directory**, loaded on open/switch. It does not
  import their model context. Up to 1000 entries / 2 MiB are retained, scanning at most
  16 MiB total and 1 MiB per journal; History labels a partial result. Older journals have
  no per-message timestamps, so sessions are ordered by recent activity, then their
  submission order—not a globally interleaved timeline. The current session comes last.
- Tab completes `./workspace-paths`, `/commands` and discovered `@skill` names at the current token,
  preserving surrounding text. Multiple matches open local choices; Tab/Enter inserts,
  Escape cancels. Skill names are **plain text suggestions**, not attached or auto-loaded
  skills. In Actions, Tab fills the selected search choice; Enter activates it.
  Path completion lists one directory (up to 2000 inspected names / 80 suggestions),
  quotes spaces, and never reads file contents or loads an attachment. Directory
  completions end in `/`; press Tab again to see their children. Hidden names require
  an explicit dot prefix. Parent traversal, escaping symlinks and nonprinting names
  are rejected; no shell expansion or recursive project indexing is performed.

Conversations and drafts are saved automatically in real bridge launches. To return:

```sh
uv run --no-sync python scripts/run.py --resume
uv run --no-sync python scripts/run.py --resume latest
uv run --no-sync python scripts/run.py --list-sessions
uv run --no-sync python scripts/run.py --resume CONVERSATION_ID
```

Use the same `--state-dir` if you customized it. Resume restores the recorded bundle,
ordered overlays, working directory, sent history, unsent text and canonical model
messages into a fresh engine. Credentials still come from your environment. It does
not submit the draft or replay old tools/approvals.
Bare `--resume` opens a searchable startup chooser before mounting a runtime. Escape
cancels without changing saved state; explicit `latest` or an ID skips the chooser.
An interrupted conversation offers a separate recovery confirmation, never silent replay.

Inside the app, **Resume** above the composer (or **Actions → Resume**) opens the saved-conversation picker. Search by
title or ID; arrows show the selected conversation's full directory/identity, and
PageUp/PageDown scroll those details. **New conversation** starts fresh with the current
bundle and working directory. `/resume` and `/new` are local command alternatives.
The picker shows up to 100 recent records in the same state directory; it does not
search other apps or import CLI conversations. New records use the first message as
their title; older records get a bounded journal preview when available.

Switching saves the source draft and pauses editing while the target is prepared.
**Cancel** or Escape cancels preparation; failed preparation leaves the source intact.
Active work must finish or be explicitly stopped before switching. The actual change
requires target readiness, then closes the source engine and replaces the view. Module
mounts still run normally, but target mount-time approvals are denied rather than
silently granted or shown against the source conversation. Cancellation is unavailable
during the brief final cleanup/commit step; an exceptional cleanup failure is reported,
not treated as a rollback. Editor undo/selection history never crosses conversations.
No old provider/tool operations are replayed.

Exact resume is intentionally **completed-checkpoint only**. A stopped,
failed, unknown, corrupt or interrupted-in-flight conversation refuses continuation;
its private journal remains for inspection. No automatic orphan-tool repair or rollback
is claimed. Concurrent writers and changed effective module configurations also refuse
resume. To continue from interrupted history, select the conversation in **Resume** and
confirm **Create recovered conversation**, or run `python scripts/run.py --recover ID`
through `uv run --no-sync`. This creates a new identity with historical reference context
and the saved draft; it does not replay tools, release queued work, or change the original.
It is not exact canonical-context/module-private-state restoration. Partial external
effects may remain. Uncertain policy-control records still refuse automatic recovery.
For inspection without a runtime, use `uv run --no-sync python scripts/run.py --export ID`.
Bundle/module/context files remain live sources, not archived code snapshots.
Pending follow-ups are stored separately and reopen paused. An admission interrupted
between persistence and execution is marked dispatched/uncertain and never automatically
retried. Such an entry blocks queue release until **Resolve uncertain delivery** is explicitly
confirmed while idle. This preserves a dismissed receipt and keeps the queue paused;
it neither retries work nor proves whether effects occurred. Ordinary queued entries can
be edited or removed; removal does not undo already admitted work.
Provider controls use a separate atomic record. A missing, corrupt or interrupted
provider-control save refuses resume; no fallback model or automatic repair is guessed.
Unacknowledged dialog text remains accessible after a disconnect: the dialog shows
**F2 copy text / Esc close**. Copy depends on terminal OSC52 support; closing does not
retry the uncertain request or overwrite the main draft. Answer/correction text saved before
disconnect remains in Saved local drafts; other dialog kinds are not crash-durable.
Draft text autosaves after a 250 ms input pause and flushes on normal quit; sudden process
death can lose the most recent unsaved edits. Cursor/selection retention across history
navigation is in-memory; only text is restored across process exit. Store directories are
private (0700), files 0600, **not encrypted**; transcripts/tool output may contain secrets.
Old runs made before this storage implementation cannot be retroactively resumed.

See [interaction reconciliation](notes/INTERACTION-RECONCILIATION.md) and
[functional verification](notes/ACCEPTANCE.md). The review now concerns the everyday
flow—writing, choosing, inspecting and continuing—not which engine renders the same scene.

## Historical design comparison

For the visual preview, run this from the project directory:

```sh
uv run --no-sync python scripts/compare.py ratatui
```

This shows a **SIMULATED** design scene, not a live assistant. The layout uses the
terminal's full width without outer side padding, including the composer and approval card.
It does not edit files or execute the displayed command. The initial decision asks
you to allow or deny a synthetic test; allowing deliberately reveals a failed test.
See [the review packet](notes/TERMINAL-REVIEW.md) for actual captures, measurements,
tradeoffs and the specific review question. Nothing here uses Textual.

For the original engine comparison, substitute `opentui` for `ratatui`. They began as
two implementations of one design. Ratatui now has the interaction work above; OpenTUI
retains the earlier controls below. They are no longer a matched interaction comparison.
Their original benchmark receipts identify historical source fingerprints.

Older OpenTUI comparison controls (not the primary Ratatui interaction model):

- F1/F2/F3: Work / Review / System; the draft remains mounted.
- Enter: send; Alt+Enter or Ctrl+J: newline. Bracketed paste never submits.
- Ctrl+Y / Ctrl+N: allow once / deny the pending request.
- Ctrl+E: expand selected evidence; Ctrl+T: next tool; Escape: close detail.
- PageUp/PageDown: scroll transcript or open evidence. Ctrl+P: copy exact evidence
  through OSC52, subject to your terminal's clipboard permission.
- Ctrl+X: stop; Ctrl+Q: quit. Busy sends retain the draft; queue/steer are unavailable.

For a fresh checkout, install Python dependencies as below, then build/install:

```sh
cargo build --release --locked --manifest-path frontends/ratatui/Cargo.toml
bun install --frozen-lockfile --cwd frontends/opentui
```

Rust 1.93 and Bun 1.3.14 were exercised on Linux ARM64. Runtime package locks are
in each frontend directory. The comparison launchers are workspace developer tools;
the Python wheel alone does not install these native candidates.

### Real execution through either candidate

After the source bootstrap below, connect to the real kernel with deterministic
provider/tool modules (not live AI):

```sh
uv run --no-sync python scripts/compare.py ratatui --runtime --fixture --sources ../tui-sources.json --no-install
```

For a live model, supply `ANTHROPIC_API_KEY` through your usual secret mechanism:

```sh
uv run --no-sync python scripts/compare.py ratatui --runtime --bundle ../amplifier-foundation/bundles/anchors --overlay examples/anthropic.yaml --sources ../tui-sources.json --require-tool read_file
```

Substitute `opentui` for the frontend or `anchors-amp-dev` for the preset. Live calls
incur provider charges. The full presets retain shell/file tools and their configured
permissions; **this is not a sandbox**. The shared host supports delegated execution. Bridge launches
now checkpoint canonical conversations; only Ratatui implements the new draft controls.
The transport remains experimental, without transparent reconnection or retry.

The retained first vertical slice is a Textual terminal over real Foundation bundle
preparation, Amplifier core, and independently loaded providers/tools/hooks.
No upstream kernel, orchestrator, context or CLI source changes are required.

Work, Review and System share one in-memory conversation and multiline composer.
Tool results remain distinct from assistant claims. The same host exposes a headless
JSONL client. See [acceptance evidence and limitations](notes/ACCEPTANCE.md).

## Run the existing developer smoke test

Purpose: inspect runtime wiring and regression behavior, not evaluate the finished
experience. The fixture is scripted, not a live assistant. No user acceptance review
is requested by this command; developer-run captures and an explicit question precede one.

Python 3.11+ and `uv` are required; verification used Python 3.13 on Linux.
Keep this project in its own git directory inside a development workspace.
From this project directory:

```sh
uv sync --locked --inexact
uv run --no-sync python scripts/bootstrap_sources.py --workspace ..
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync amplifier-tui --fixture --sources ../tui-sources.json --no-install
```

The bootstrap adds the two pinned upstream loop/context repos as workspace
submodules, or verifies existing clean checkouts. It never resets local changes.
`--fixture` uses a clearly labeled deterministic provider and a real SHA-256 tool,
not a live model. No credential is needed. First preparation without a local source
map may download module sources through Foundation.

- Enter inserts a newline; Ctrl+S sends when idle.
- Ctrl+X stops the active turn; partial effects may remain.
- Ctrl+Q closes the session and exits. Unsent text is **not durable** across exit.
- Tab/Shift+Tab move focus. Click Work, Review or System to change views.
- Approval buttons apply only to the identified pending request; expiry denies it.

During startup and execution, the composer remains mounted and editable. Busy
submissions are rejected without clearing the draft. Queue and steer are unavailable.

## Live provider and presets

Supply `ANTHROPIC_API_KEY` in the environment through your normal secret mechanism.
The host does not read or migrate CLI settings or stored provider credentials.
The examples select Anthropic Haiku 4.5; live calls incur provider charges.

```sh
uv run --no-sync python scripts/bootstrap_sources.py --workspace .. --all
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync amplifier-tui --bundle examples/live.yaml --sources ../tui-sources.json --require-tool read_file
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync amplifier-tui --bundle ../amplifier-foundation/bundles/anchors --overlay examples/anthropic.yaml --sources ../tui-sources.json --require-tool read_file
```

Replace `anchors` with `anchors-amp-dev` for the ecosystem preset. The preset adds
agent/skill definitions, not a running DTU or Gitea service. The app provides public
`session.spawn` / `session.resume` capabilities for delegation and in-process agent
recipe steps, including v2 declared dependencies. Each child gets its own real session,
context, scoped transcript card, approval/question routing and cleanup. Limits: four
active children, three nested levels, 32 retained children per open root. Completed
children can resume within that open root. After restarting, explicit `delegate` continuation
with the original full `session_id` supports completed children whose agent definition,
effective configuration and inherited mode reconstruct unchanged. No child starts on inspection
or root resume. Nested continuation requires the actual parent to be active following
its own explicit continuation. Recorded provider preferences are reconstructed and the
effective fingerprint must match. Arbitrary custom orchestrator overrides, changed/unknown
definitions, older unsupported receipts, interrupted children and subprocess isolation are refused.
Persistent-context children use identity-scoped storage separate from their parent/siblings.
Stop cancels active children; it
does not undo their effects. Active parent mode restrictions are restored in children.
**System** reports local event/context-intelligence capture and disabled external dispatch;
delegation preserves that storage policy. No context-intelligence server is provisioned.

The minimal `live.yaml` denies filesystem writes. Full presets retain their authored
tools and permissions, including shell/file writes; they are **not read-only or
sandboxed**. Review a bundle before loading it: modules are executable Python.

## Configuration and state

`--bundle` is explicit, with repeatable ordered `--overlay` options. `--cwd` selects
tool/mention working directory. `--require-tool NAME` requires an actual exported
tool mount; module names do not necessarily equal tool names. Source-map values are
resolved relative to that JSON file. Overrides are deliberate and reported; the
runtime does not enforce the source snapshot against edited checkouts. Use bootstrap
verification when reproducing acceptance evidence.

Root module configs expand `${VAR:default}`; an unset `${VAR}` becomes empty.
Explicit missing provider credential references fail startup instead of falling
through to another credential. Prompt text and deferred child configs are not expanded.
Provider configs/credentials are excluded from the composition report.

`--state-dir` defaults to `.state` under the launch directory. The CLI process sets
`AMPLIFIER_HOME` and context-intelligence storage to that location before imports.
Known logging/recipe paths are redirected there; context-intelligence starts with
external dispatch destinations empty. Runtime tools can change module policy; this
is not a security boundary. Logs may contain prompts and tool output: do not share
the state directory or raw headless events without inspecting/redacting them.
No general safe diagnostic-export feature is claimed.

Known terminal-writing hooks are excluded and named in System; other policy hooks
stay composed. A required mount failure, or a warning from the pinned core initializer,
refuses readiness. System separates authored modules, observed tool/provider names,
registered hook handlers, host exclusions and unsupported controls.

Foundation can install module dependencies into the environment at preparation time.
Use `--no-install` only after dependencies are available. `uv sync --inexact` preserves
those dynamic packages; an exact sync can remove them. `uv.lock` pins host dependencies;
[sources.lock.json](sources.lock.json) separately records inspected bundle/module sources.

## Headless and development

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync amplifier-tui --fixture --sources ../tui-sources.json --no-install --headless 'Compute a digest'
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync pytest -q
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
```

Headless stdout carries identified JSONL events; Python-level module prints go to
stderr. Approvals are denied, never implicitly allowed. Exit 0 means the orchestrator
reported a completed turn, **not** that every tool or requested task succeeded.

Read [vision](docs/VISION.md), [composition contract](contracts/composition.v1.md),
[engine decision](notes/ENGINE-BOUNDARY.md), and [smoke tests](SMOKE_TESTS.md).
The [Converge practice note](notes/CONVERGE.md) pins the adopted method and explains
amendment, work derivation and the boundary with the future Converge app.
Contracts are draft targets, not claims that continuity and later slices are shipped.
This repo is local-only until explicitly published or backed up.
