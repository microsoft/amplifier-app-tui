# Switch between CLI and TUI without migrating your conversation

Ordinary CLI-policy launches now use the CLI's canonical project/session store.
In the same working directory, run
`amplifier-tui --resume` and choose your CLI conversation, or use `--resume ID` /
`--resume latest`. `amplifier resume ID` or
`amplifier continue` uses the same identity and transcript. No import or conversion.
The in-app Resume list, saved-message search and Up/Down recall include CLI sessions
from that directory, not its parents, children or unrelated projects.

Configuration reads global/project/local and session-scoped CLI settings without
rewriting them. Credentials remain provider-owned. Canonical data stays under
`$AMPLIFIER_HOME/projects/<project-slug>/sessions/<session-id>` (normally in
`~/.amplifier`). The `.tui` child directory holds drafts and TUI controls, not a
second observation journal or authoritative copy of the conversation. Reopening
rebuilds the display from native history and configured shared observations.
Persisted injected reminders stay in
canonical context but do not appear as user messages or input recall.

This is the first bidirectional session slice, **not complete feature parity**:

- Foundation's common ownership lock refuses a second cooperating writer. A busy
  TUI opens read-only: **Continue here** asks the owner to finish current calls,
  save and clean up. A successful response still requires acquiring the real lock
  and validating fresh history before execution. It never sends a retained draft.
  The TUI accepts reciprocal release requests and stays open as a read-only view.
  Timeout or refusal cannot steal ownership; retry explicitly after checking the
  other app. A changed acquisition is shown before a new request can target it.
  Five minutes without runtime work or observed user activity release ownership
  automatically. Editing and inspection reset the timer, but background refreshes
  do not; external editing prevents auto-release. Native terminal/tmux-owned input
  cannot be observed. Explicit handoff remains immediate. Next Send can
  remount current modules/configuration, so it may take longer than a warm turn.
  Pending decisions, running work and unresolved dispatched follow-ups prevent
  idle release. Paused follow-ups stay paused and do not transfer to other apps.
  All clients must use the same `AMPLIFIER_SESSION_STATE_HOME` (or Foundation's
  platform default), working directory and session ID. Older clients can ignore
  this mechanism; it does not support simultaneous editing or fence remote jobs.
- TUI-only pending input, pins, modes, goals and child receipts are retained, but
  are not yet a shared CLI control format. Changed/incompatible controls can refuse
  native resume; do not edit their checkpoint by hand.
- Historical costs are read from shared recorded model-call receipts.
  Earlier usage contributes to Session, not the next Turn;
  inspect its receipts in Activity. Missing logs, uncorrelated observations and
  observation bounds disclose partial accounting rather than an invented complete total.
  The shared reader prefers context-intelligence capture, honors its configured base
  path and falls back to the root log only when CI is absent. Ordinary Activity reads
  bounded historical snapshots on demand, without a separate Shared view, replay or changing source logs.
- Unknown outcomes, incomplete tool pairing and uncertain checkpoints refuse native
  execution. Export for inspection; no prior call is automatically replayed.
- Foundation reads valid primary or backup history; corruption never becomes an
  empty conversation. Native loading has no TUI-only transcript/message/metadata quota;
  display previews and initial history replay are bounded independently. Arbitrary
  module-private state and cross-client persistent-context combinations still need
  individual verification. A successful context readback is required before Send.

All live conversations use the CLI session format. Explicit isolated policy selects
an isolated Amplifier home, not another storage format; resume with that `--cli-home`.
Deterministic developer fixtures use private test journals and never personal sessions.

## Credential and interactive-login boundaries

`--setup` writes only an explicitly named environment-variable reference into a new
YAML overlay, not a key or shared CLI configuration. It does not search keychains.
Choose a distinct variable for each intended credential binding; keep values out of
conversation input, overlays, source control and diagnostic reports.

The inspected CLI provider adapter supports module-declared `auth:*` capabilities
with public `auth_status()` and `login()` methods. A capability label alone does not
establish working login: both methods, terminal ownership, cancellation and the
module's credential-storage policy need verification. Synchronous login may print
device-code instructions and read the terminal; it must not run behind the TUI's
active composer. For an already mounted provider exposing asynchronous `login(print_fn=...)`
and `auth_status()`, send `/provider login NAME`, then open **Actions → Provider login
prompt**. Instructions are transient, not journaled or sent to a model. Stop cancels the
owned operation; the module owns credential storage and may already have written tokens.
Login has a cooperative ten-minute limit. `/provider status` reports allowlisted module
authentication states; authentication alone does not establish model access.
Synchronous/terminal-reading providers still require their external entrypoint. For the
inspected ChatGPT module, configure `login_on_mount: false` to mount without starting
interactive login during startup. Mount-time login remains unverified. No tokens are
copied from another client; existing credentials retain module ownership.

Source basis: the workspace study of CLI `provider_config_utils.py`, functions
`_maybe_login_provider` and `_run_provider_login`; this is not a claim that every
provider implements the seam or that OAuth is part of the kernel provider contract.

## Continue the same TUI conversation

Run `amplifier-tui --state-dir /path/to/existing/state --resume` and select it.
This restores its recorded composition and working directory. Missing sources, changed
configuration or uncertain checkpoints are reasons to refuse resume, not to edit the
checkpoint by hand. Old local-source conversations still need those source paths.
Different CLI homes, policies or working directories require relaunching with `--resume`;
this keeps process-scoped module paths and credentials in their original scope.

## Start a new composition with historical text

In a CLI-policy conversation, **Resume → CLI sessions** (or `/cli-sessions`) lists
bounded metadata for CLI sessions in this exact working directory. Select a session,
review the warning and confirm import. This captures up to 1 MiB of transcript text
into a new TUI conversation; originals remain unchanged, and no model call or historical
tool runs. This is reference import, not canonical CLI resume: private context, pending
work, modes and provider pins do not transfer. The next explicit Send can share that
reference with the selected provider. A partial catalog is labelled, not exhaustive.

The same confirmation offers **Adopt paired public context**. This preserves structured
assistant/tool messages under a new identity, validates complete call/result pairing,
and requires exact portable-message readback by the target context module. Incomplete
calls or incompatible modules refuse without changing the source conversation. This
is not original-identity CLI resume: original policy, credentials and module-private
state are unavailable. Configured startup hooks can still run when the new session mounts.

## Session controls and deliberate shared saves

Actions can insert goal, tool-configuration, directory and login commands into an empty
composer. Insertion is unsent; review arguments, then Send. Local controls cannot be queued.

| Command | Effect |
|---|---|
| `/goal --max-turns 5 CONDITION` | Sets the streaming loop's goal; no turn starts until the next Send. Omitting the limit means unlimited continuation and possible charges. |
| `/goal` / `/goal clear` | Inspect or clear; active goals retain their cap across supported TUI resume. |
| `/config CATEGORY disable NAME` / `enable NAME` | Changes supported tool/provider/context/agent/behavior policy through Foundation; persists for this conversation. Leave modes first. Hooks remain inspection-only. |
| `/config diff` / `/config set PATH VALUE` | Shows edited paths without values; `set` stages scalar module metadata, not live reinitialization. Credentials use provider-owned setup. |
| `/config save --scope SCOPE --confirm` | Choose `project`, `local` or `global` explicitly to save configurator policy for new conversations. Existing conversations retain their own policy. |
| `/allowed-dirs add PATH` / `remove PATH` / `list` | Changes the supported root filesystem write/edit allowlist. Quote paths containing spaces. |
| `/denied-dirs add PATH` / `remove PATH` / `list` | Changes the corresponding denylist; deny wins. Neither list restricts bash or children. |
| `/provider use NAME` / `auto` / `status` | Existing conversation pin capability, with durable selection and same-vendor limits. |
| `/provider models` / `test NAME` | Explicit catalog request or standalone billed access probe; no conversation content sent by the probe. |
| `/mode NAME on` / `off`, `/mode off`, `/mode info NAME` | Module-enforced transition or authored definition. `/mode NAME` toggles. |
| `/mode NAME PROMPT` or `/NAME PROMPT` | Applies a discovered mode through its policy, then sends the trailing prompt only if activation succeeds. |

Controls affect the current conversation unless you explicitly save shared policy.
They are not an OS sandbox. Delegated sessions, routing and other tools keep their
own policy. Re-enable locally disabled tools before changing mode; the two policies
must not silently undo each other. Missing or uncertain saved controls refuse resume.
Metadata edits do not reinitialize running modules. A shared save uses the CLI's
settings paths and may change YAML formatting/comments. See the
[loaded-configuration and session-operation guide](GETTING-STARTED.md) for exact
guards, context clearing, turn branches, direct tools and reversible archival.

`amplifier-tui resume`, `amplifier-tui continue` and `amplifier-tui session …` still
open pinned-CLI workflows. Native `--resume` now discovers the shared CLI project
store; it does not copy private state.

Export a readable UTF-8 transcript from the old client. For this app,
`amplifier-tui --export` prints the location of a private Markdown export. Review that
file locally: transcripts may include private work, tool output or credentials.

Create a trusted provider overlay with `amplifier-tui --setup`, then launch:

```sh
amplifier-tui --overlay ./new-provider.yaml --import-transcript ./old-conversation.md
```

The import copies at most 1 MiB into a **new** conversation. Its SHA-256 and reference
notice are retained. It never modifies the original file or sends an initial model
request. Review the notice before your next explicit Send: the new provider can then
receive the imported text.

This is deliberately **not canonical resume**. Images, provider pins, modes, pending
decisions, queued work, executable tool calls and private module state are not restored.
Historical instructions are reference material, not work to replay. Choose this path
when changing providers/compositions; it does not bypass a module's compatibility guard.
The import cannot be combined with `--resume`.

## Check a provider without sharing the conversation

For an exposed mounted provider, open **Actions → Conversation provider → Validate
access**, review the confirmation, then send the standalone probe. Charges may apply.
The probe sends only “Reply OK.”, with no conversation, workspace content or tools. It
requests 16 output tokens and has a cooperative 20-second timeout; provider configuration
and retries may affect actual cost/time. Stop requests cancellation, not remote rollback.

A response proves only that this configured request worked at that time. It does not
validate every model, delegated route, tool, quota or future request. Error/response text
is withheld from the result display. Offline `--check` remains strictly offline.
