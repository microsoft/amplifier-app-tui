# Your first Amplifier TUI conversation

Amplifier TUI is an early native terminal app powered by Amplifier bundles and modules.
It can read files, run commands and delegate work using your selected composition.
It is not an OS sandbox. Linux ARM64 is verified; macOS is untested and Windows needs WSL2.

## Install

You need access to the private repository, uv, Git, Rust/Cargo and a C linker.
Rust is needed to build during installation, not for normal launches. If GitHub CLI
is your chosen Git credential helper, authenticate with `gh auth login` and
`gh auth setup-git`. Do not put a token in the install URL.

```sh
uv tool install git+https://github.com/bkrabach/amplifier-app-tui
amplifier-tui --getting-started
amplifier-tui --check
```

If the command is not found after installation, follow uv's printed PATH instructions
and open a new terminal. The checks explain local blockers; no model calls or downloads
occur. A missing provider key is expected before live setup, not a broken installation.

## Choose a first run

**Live AI:** provide `ANTHROPIC_API_KEY` through your environment or secret manager, open
the directory you want to work in, then run `amplifier-tui`. The default is the `anchors`
preset with Haiku. `--preset anchors-amp-dev` chooses the development preset; custom
providers use trusted `--bundle` / `--overlay` configuration. No CLI credentials are imported.
First launch downloads bundle/module code and installs dependencies; allow it time.
Only load sources you trust. Model calls incur charges.

Try a small request such as “Explain this project's structure without editing files
or running commands.” That request guides the assistant; it is not a permission barrier.
Review the actual tool evidence rather than relying only on the final answer.

**No key yet:** run `amplifier-tui --fixture` and send “Compute a digest”. This is a
labelled scripted provider with a real digest tool, **not an AI assistant**. It still
creates local state and may download dependencies. Use it to try the terminal controls.

## Learn the controls as you work

Tab focuses visible controls when it cannot complete text; Enter activates the focused
control or sends from the composer. Alt+Enter adds a newline. Pasting never sends.
Open Actions, search “Getting started”, then choose a help topic. Escape returns to the
same unsent draft. Optional shortcut: F4 opens Actions.

| You want to… | Where to go |
|---|---|
| Add work for later | Pending follow-ups: inspect, pause, edit, remove or run |
| Correct current work | Steer; inspect Corrections for actual insertion status |
| Supply missing information | Answer question; review and explicitly submit |
| Grant scoped permission | Review decision; inspect the actual offered options |
| See delegated work | Actions → Delegated work; old receipts are historical |
| Understand results | Review or Activity evidence; completion is not a test verdict |
| Copy or scroll | Normal terminal selection / tmux copy mode; Transcript for reflow |
| Change tool policy | Modes; the current mode stays visible |

Stop requests cancellation and holds queued work. It cannot undo effects already made.
The normal view leaves mouse selection to the terminal; menus and inspection own their
own mouse controls. In tmux, copy mode is normally prefix then `[`. No special scrollback
view is needed, and output stays in the terminal after exit.

## Return tomorrow

Quit through Actions, then run `amplifier-tui --resume` and choose a conversation.
Reopening does not repeat tools or automatically release queued work. Normal installed
state lives under `$XDG_DATA_HOME/amplifier-tui`, usually `~/.local/share/amplifier-tui`.
Use `--state-dir` to explicitly select another store. Shared CLI history/settings are not
migrated. Interrupted work can require an explicitly acknowledged historical recovery,
not exact restoration of arbitrary tool/context state.

To upgrade: `uv tool install --reinstall git+https://github.com/bkrabach/amplifier-app-tui`.
Keep recorded local bundle/overlay paths available for older conversations. An upgrade
does not silently add new overlays to them.

Need help? [Troubleshooting and safe reports](SUPPORT.md). Full advanced configuration
and developer setup remain in the [README](../README.md).
