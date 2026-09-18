# Your first Amplifier TUI conversation

Amplifier TUI is an early native terminal app powered by Amplifier bundles and modules.
It can read files, run commands and delegate work using your selected composition.
It is not an OS sandbox. Linux ARM64 has interactive/live verification. Native build/install
checks also pass on Linux x86-64 and both macOS architectures; Windows needs WSL2.

## Install

For compiler-free installation, download your machine's wheel from the private
[release page](https://github.com/bkrabach/amplifier-app-tui/releases)
and run `uv tool install --no-sources ./<downloaded-wheel>.whl`. See the [platform table](../README.md#install-the-native-product)
for the tested systems and limits. Repository access, uv and Git are still needed.

For installation directly from source, you also need Rust/Cargo and a C linker.
Rust is needed to build during installation, not for normal launches. If GitHub CLI
is your chosen Git credential helper, authenticate with `gh auth login` and
`gh auth setup-git`. Do not put a token in the install URL.

```sh
uv tool install --no-sources git+https://github.com/bkrabach/amplifier-app-tui
amplifier-tui --getting-started
amplifier-tui --check
```

If the command is not found after installation, follow uv's printed PATH instructions
and open a new terminal. The checks explain local blockers; no model calls or downloads
occur. A missing provider key is expected before live setup, not a broken installation.

## Choose a first run

### Shell completion and scripting

Enable completion for the current shell (no startup files are changed):

```sh
# Bash
eval "$(_AMPLIFIER_TUI_COMPLETE=bash_source amplifier-tui)"
# Zsh
eval "$(_AMPLIFIER_TUI_COMPLETE=zsh_source amplifier-tui)"
# Fish
_AMPLIFIER_TUI_COMPLETE=fish_source amplifier-tui | source
```

Completion covers native flags and the CLI-owned command tree using read-only local
candidates. It does not initialize providers or read conversation bodies. To script
the pinned CLI, use `amplifier-tui run "Your request" --output-format json` or pipe a
prompt into `amplifier-tui run --output-format json-trace`. These execute real model
work with your CLI settings and CLI session store; they do not launch the native UI.

### Keep the Resume list tidy

After closing a conversation, use `amplifier-tui --list-sessions` to find its exact ID,
then `amplifier-tui --archive ID --confirm`. This hides it from ordinary Resume,
search and input recall without deleting history, drafts or checkpoints. The command
refuses active conversations and sessions belonging to another working directory.
Use `amplifier-tui --list-archived` and `amplifier-tui --restore ID --confirm` to undo
archival. Run these from the original directory with the same `--state-dir` if used.
Restoring visibility does not repair an uncertain checkpoint or execute any work.

### Start a conversation

**Live AI:** open the directory you want to work in and run `amplifier-tui`. New launches
use your CLI's global/project/local settings, active bundle, configured behaviors and
providers. Settings are not rewritten; credentials remain with their provider modules.
Configured hooks retain their destinations and may contact services at startup.
Provider-owned asynchronous login is available through `/provider login NAME` and
Actions → Provider login prompt when the module supports it; terminal-reading login
still uses the provider's external entrypoint. See [login boundaries](MIGRATION.md).
To opt out of CLI settings, use
`--settings-policy isolated` (the default isolated preset needs `ANTHROPIC_API_KEY`).
Explicit `--preset`, `--bundle` or `--overlay` is isolated unless you also specify
`--settings-policy cli`. Old conversations retain their saved policy.
`amplifier-tui --setup` guides creation of a new private provider/model overlay without
storing a key or overwriting files. In an open app, **Actions → Model catalog** queries
reported model IDs for reference; it does not validate access or change the active model.
First launch downloads bundle/module code and installs dependencies; allow it time.
The welcome/composer appears immediately with the current preparation phase. You can
type while it loads; becoming ready never submits your draft automatically.
Only load sources you trust. Model calls incur charges.

Try a small request such as “Explain this project's structure without editing files
or running commands.” That request guides the assistant; it is not a permission barrier.
Review the actual tool evidence rather than relying only on the final answer.

**No key yet:** run `amplifier-tui --fixture` and send “Compute a digest”. This is a
labelled scripted provider with a real digest tool, **not an AI assistant**. It still
creates local state and may download dependencies. Use it to try the terminal controls.

## Learn the controls as you work

CLI administration and scripting are also available from this entrypoint:
`amplifier-tui provider list`, `amplifier-tui bundle list`,
`amplifier-tui routing list`, `amplifier-tui tool --help`, and
`amplifier-tui run --help`. Use `amplifier-tui cli --help` for the full CLI menu.
These commands run the pinned CLI directly, preserving its settings, credentials,
permissions, stdin and text/JSON output. They do not open the native interface.
`amplifier-tui session ...` uses CLI session commands; `amplifier-tui --resume`
opens a native directory-local picker including those same CLI conversations.
Close one client before opening the other. Shared canonical history is supported;
private controls still have [switching limits](MIGRATION.md).

Actions → Loaded configuration inserts `/config` without sending. Send it to inspect
loaded providers, tools, hooks, context entries, agent definitions and behaviors.
Use `/config agents` for definitions (not running agents), or `/config show tools NAME`
for an exact item's status and origins. Lists show at most 32 items per category;
exact-name inspection can reach omitted items. These metadata-only views omit values,
source URLs and instruction bodies; no model request or settings change occurs.
`/agents` and `/tools` inspect definitions and mounted tools; `/children` inspects
observed delegated work. `/config CATEGORY enable|disable NAME` changes tools,
providers, context entries, agents or behaviors for this conversation. Leave an
active mode first. Hooks are inspection-only; behavior toggles leave hooks unchanged
and refuse groups owning protected providers/mode control. Keep at least one provider;
return a pinned provider to Auto before disabling it.

`/config diff` shows disabled names and edited paths, omitting values. `/config set
PATH VALUE` edits bounded scalar module metadata beneath an existing `.config.`
dictionary; it does not reinitialize modules or promise that a running module reads
the value. Use provider-owned setup for credentials, not configuration commands.
Local controls survive resume. Shared settings remain unchanged unless you explicitly
send `/config save --scope project|local|global --confirm` (choose one scope).
This atomically saves configurator policy for new compatible conversations using
the CLI settings paths; YAML formatting/comments may change. Existing conversations
retain their own saved controls. Broader setup uses `amplifier-tui cli ...`.

In the composer, Tab completes command arguments such as `/provider use`,
`/provider models`, `/mode`, `/config tools`, `/goal`, and skill arguments from
cached module metadata. Selecting a choice inserts text; Send executes it.
`/provider models [NAME]` queries all mounted instances or one named instance;
`/provider test [NAME]` sends explicit standalone probes and can incur charges.

Actions also offers session operations:

- `/clear` asks before clearing active context and the goal. The default is No.
  The conversation identity, transcript, draft and settings remain; queued work is
  held. A private pre-clear context backup is retained. This does not undo files or
  service effects. `/clear --confirm` is the explicit typed equivalent.
- `/fork` lists captured context turns using the CLI/Foundation turn boundaries.
  `/fork N [name]` asks before opening a new public-context branch through turn N.
  Original history remains. Pins, modes, goals, local controls, queued work and module
  private state are not copied; the branch uses current launch configuration. A
  context module that cannot retain the captured history refuses the branch.
- `/export json` writes versioned displayed observations to a private local file.
  `/export` remains Markdown. Neither is executable resume data; review before sharing.
- `/tool list` and `/tool info NAME` inspect mounted tools and input schemas.
  `/tool invoke NAME JSON_OBJECT` executes an explicit tool request without a root
  model request, using normal hooks, approvals and cancellation. Tools themselves
  can change files, call services/models and incur charges. It never automatically
  retries, and naming/prompt-complete hooks are not run for this manual operation.

For example, inspect a tool's schema before constructing its JSON object. Completion
offers cached mounted tool names, not an automatic invocation or an inferred permission.

Delegated work waits for capacity instead of failing when many agents are requested.
The default is eight executing children per parent; set
`AMPLIFIER_TUI_CHILD_CONCURRENCY` to 1–64 before launch to change that limit.
Nested agents have their own capacity, and the delegate module keeps its configured
self-delegation policy. Completed history does not consume execution slots. Older
valid completed or safely stopped children can continue explicitly under the same
identity, including after restart. Their parent and non-routing policy must still
match. The delegate tool can supply new provider preferences/model roles; omitted
choices retain the saved routing. Unresolved choices show a warning. The child's
own approved mode is retained separately from its inherited parent mode. Uncertain
state still requires explicit recovery; reopening never starts an old call.
Agents declaring `spawn_mode: subprocess`, and recipe steps requesting subprocess
execution, run in a fresh interpreter. They keep the same approval/question surfaces,
Activity evidence, child accounting, nested delegation and explicit continuation.
First Stop asks current calls to finish; a second Stop can terminate an unresponsive
worker. A killed or lost worker is not silently retried or marked safely resumable.
This isolates a process; it is not an operating-system permission sandbox.

Tab focuses visible controls when it cannot complete text; Enter activates the focused
control or sends from the composer. Alt+Enter adds a newline. Pasting never sends.
Open Actions to browse Write and attach, Current task, Conversations, Review and copy,
or Tools and setup. Type to search across every group; “Getting started” opens task help.
Escape returns to the same unsent draft. Optional shortcut: F4 opens Actions.

| You want to… | Where to go |
|---|---|
| Add work for later | Pending follow-ups: inspect, pause, edit, remove or run |
| Correct current work | Change task (steer); inspect Corrections for actual insertion status |
| Supply missing information | Answer question; review and explicitly submit |
| Grant scoped permission | Review decision; inspect the actual offered options |
| See delegated work | Delegate summaries show distinct agents, current activity and warning counts; wider screens add call/cost totals. Activity opens child tools and every retained model-call record, with More/Earlier pages for long runs |
| Understand results | Interact expands tool/thinking previews inline; Activity opens full evidence. Completion is not a test verdict |
| Inspect module prints/logs | Actions → Runtime output shows a bounded private stdout/stderr tail. Refresh for new output; review before copying. It spans this app process, not a particular agent, and is not saved to conversation history |
| Copy or scroll | Normal terminal selection / tmux copy mode; Transcript for reflow |
| Change tool policy | Modes; the current mode stays visible |
| Find previous work | Resume, or Actions → Search saved conversations in this launch directory; ordinary CLI sessions retain their identity without import |
| Invoke a discovered skill | Type `/` and search its name/alias, e.g. `memory review`; Enter inserts the command, then Send invokes it. `/skill NAME arguments` also works |
| Find recipe files | Actions → Recipe files, or `/recipes`; choose a local candidate to append an unsent review request. Recipe activity is separate; the runtime's `list` operation lists active runs |
| Include images | Actions → Attach image; preview and confirm up to four workspace PNG/JPEG snapshots |
| Use a desktop clipboard image | Actions → Paste clipboard image; requires a supported clipboard on the host |
| Inspect saved model context | Actions → Stored context; public messages, not the exact wire request |
| Check provider access | Actions → Conversation provider → Validate access; separately confirmed remote probe, may bill |
| Inspect instruction provenance | Actions → Instruction sources; last observed resolutions, not a complete prompt |
| Look up model IDs | Actions → Model catalog; explicit advisory lookup, not a model change |

Stop requests cancellation and holds queued work. It cannot undo effects already made.
Ctrl-C during work requests a **graceful** Stop: finish current model/tool calls,
including nested agents, then return to the composer. The indicator explains the
wait; press Ctrl-C again or choose Force stop to interrupt immediately. Neither
stage clears your draft. There is no automatic escalation timeout. When idle,
Ctrl-C opens a quit confirmation with **No** selected; Enter or Escape stays.
Ctrl-Q or Actions → Quit explicitly exits during work too. Ctrl-C
copies a selected transcript region before handling Stop or exit.
Reported usage is module data, not a billing guarantee. A finished response is not proof
that tests passed: failed or unknown tool outcomes remain separately inspectable.
Long tool/progress previews are shortened in ordinary history; Actions → Review or
Transcript retains detail. Committed terminal rows are not rewritten to hide old activity.
The normal view leaves mouse selection to the terminal; menus and inspection own their
own mouse controls. In tmux, copy mode is normally prefix then `[`. No special scrollback
view is needed, and output stays in the terminal after exit.

Use Tab → Interact → Enter (or `/interact`) to enable conversation clicks. Click a
summary, or use Up/Down and Enter, to expand it. The Activity link opens nested agents,
tools and evidence. Typing returns keyboard focus to your composer; Escape leaves
interaction for native copying. Your draft is retained throughout.
Each observed model call has its own attributed usage row, including cache-aware token
counts and reported cost. Turn/session totals include child calls; missing values and
unavailable older usage are disclosed instead of being silently counted as zero.

Images stay attached when you queue a draft. Open Pending follow-ups to inspect the
captured set; selecting Run explicitly releases a paused queue. Changing the source file
does not change an already captured image. Each image is limited to 2 MiB; large dimensions
are rejected before thumbnail decoding. Over SSH, save an image into the workspace and
use Attach image—the host's desktop clipboard is not your remote terminal's clipboard.

## Return tomorrow

Quit through Actions, then return to the same directory and run `amplifier-tui --resume`.
The picker, search, listing and `--resume latest` only consider that resolved directory;
parent/child directories are separate, and an explicit ID cannot switch to another root.
No local matches never falls back to conversations elsewhere.
Reopening does not repeat tools or automatically release queued work. Normal installed
CLI-policy sessions live in the CLI's project/session store, with TUI-specific
sidecars. Close the TUI and use `amplifier resume ID` to continue in CLI, or close
CLI and use native `--resume` to return. `--state-dir` selects derived caches and
test-harness storage, not a second canonical live-conversation history.
Cleanly stopped work with validated saved context resumes normally. Unverified or
incomplete state requires inspection/export; see [switching limits](MIGRATION.md).
Unknown tool effects remain unknown; history never replays work automatically.

To upgrade: `uv tool install --no-sources --reinstall git+https://github.com/bkrabach/amplifier-app-tui`.
This rebuilds the tool environment, so the next normal launch may reinstall module
dependencies; allow network access and omit `--no-install` then. Saved state is separate.
Keep recorded local bundle/overlay paths available for older conversations. An upgrade
does not silently add new overlays to them.
For a new provider/composition, see [historical-text migration](MIGRATION.md): explicit
import preserves earlier reference text without importing credentials or replaying work.

Need help? [Troubleshooting and safe reports](SUPPORT.md). Full advanced configuration
and developer setup remain linked from the [README](../README.md).

## Colour and screen size

The reference layout is 175 columns × 50 rows total, with roughly five to six idle
composer/status rows. Smaller terminals wrap controls; Actions always has a keyboard
path. A 32 × 12 terminal is a safe-navigation stress case, not a comfortable workspace.
Normal text and the composer have no decorative side gutters. Source indentation remains.

Use `AMPLIFIER_TUI_THEME=light amplifier-tui` for a light background,
`AMPLIFIER_TUI_THEME=terminal amplifier-tui` for terminal-default colours, or
`NO_COLOR=1 amplifier-tui` for colour-free rendering. Dark is the default; this is an
explicit preference, not an unreliable automatic terminal-theme query. State labels
remain meaningful without colour. Physical font/contrast comfort still depends on
your terminal. Native soft wrapping and remote clipboard restrictions are terminal-owned;
exact source-copy and Markdown export are the fallback.
