# Bring earlier work without replaying it

Upgrading the app does not import CLI configuration, credentials, queues or sessions.
Keep the original state directory and use one of these explicit paths.

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
active composer. There is no TUI login control yet, and no shared token/keychain
import or inferred authorization. Complete supported module login deliberately outside
the running TUI, using that module's documented entrypoint and storage scope, then
launch an explicit composition. Do not copy another client's credential files.

Source basis: the workspace study of CLI `provider_config_utils.py`, functions
`_maybe_login_provider` and `_run_provider_login`; this is not a claim that every
provider implements the seam or that OAuth is part of the kernel provider contract.

## Continue the same TUI conversation

Run `amplifier-tui --state-dir /path/to/existing/state --resume` and select it.
This restores its recorded composition and working directory. Missing sources, changed
configuration or uncertain checkpoints are reasons to refuse resume, not to edit the
checkpoint by hand. Old local-source conversations still need those source paths.

## Start a new composition with historical text

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
