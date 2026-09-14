"""Local onboarding only: no module loading, credential storage or conversation reads."""

import os
import platform
import shutil
import sys
from importlib.metadata import version
from pathlib import Path

GETTING_STARTED = """Amplifier TUI — your first conversation

1. Check this installation: amplifier-tui --check
   Checks are local only; they do not validate credentials or download modules.
2. Set ANTHROPIC_API_KEY in your environment for the default live provider.
   Never paste a key into chat or a bug report. CLI credentials are not imported.
   Another provider? Supply your trusted --bundle / --overlay configuration.
3. Open a project directory, then run amplifier-tui.
   First launch downloads trusted bundle/module code and installs dependencies.
   Model calls cost money. File and shell tools are NOT an OS sandbox.
4. Describe one task, then press Enter to send. Alt+Enter adds a newline.
   Try: Explain this project's structure without editing files or running commands.
   This is an instruction, not a permission restriction.
5. Tab to Actions and press Enter, then search Help for the local task guide.
   Queue = a later turn; Steer = a correction to current work. Stop is not undo.
   Review decision grants scoped permission; Answer question supplies information.
6. Quit through Actions. Return with amplifier-tui --resume and choose a conversation.
   Resume does not replay work. Use your terminal's selection and tmux copy mode
   for ordinary scrollback; Actions > Transcript offers reflowed inspection.

No AI credential yet? amplifier-tui --fixture runs a labelled scripted-provider
demo with a real digest tool, NOT an AI assistant. It still creates local state
and may download dependencies. Submit 'Compute a digest' to try one turn.

Trouble? amplifier-tui --check explains local blockers.
amplifier-tui --support-report prints allowlisted JSON for a bug report; it does
not include transcripts, configuration files or credential values. Review before sharing.
amplifier-tui --doctor includes local paths: keep it private unless redacted.
These guides do not create a session, store a key, change policy or send a request.
"""


def storage_available(path):
    """Inspect the nearest existing ancestor without creating a directory or probe file."""
    candidate = path.expanduser().absolute()
    while not candidate.exists() and not candidate.is_symlink():
        parent = candidate.parent
        if parent == candidate:
            return False
        candidate = parent
    return candidate.is_dir() and os.access(candidate, os.W_OK | os.X_OK)


def local_checks(args, binary):
    default_provider = not (args.fixture or args.bundle or args.overlay)
    key_present = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    checks = []

    def add(name, status, message):
        checks.append({"check": name, "status": status, "message": message})

    native = binary.is_file() and os.access(binary, os.X_OK)
    add(
        "native",
        "ok" if native else "error",
        "Native renderer is executable."
        if native
        else "Native renderer missing or not executable. Reinstall with Rust/Cargo and a C linker; developers must build Ratatui.",
    )
    cwd = args.cwd or Path.cwd()
    valid_cwd = cwd.is_dir() and os.access(cwd, os.X_OK)
    add(
        "workspace",
        "ok" if valid_cwd else "error",
        "Working directory is accessible."
        if valid_cwd
        else "Working directory is missing or inaccessible. Choose an existing directory with --cwd.",
    )
    storage = storage_available(args.state_dir)
    add(
        "storage",
        "ok" if storage else "error",
        "State directory or existing ancestor appears writable; no write attempted."
        if storage
        else "State location is blocked or inaccessible. Choose a writable directory with --state-dir.",
    )
    if default_provider:
        add(
            "provider",
            "ok" if key_present else "error",
            "ANTHROPIC_API_KEY is set; validity and billing access are NOT checked."
            if key_present
            else "Set ANTHROPIC_API_KEY in your environment, supply a trusted provider overlay, or try --fixture (scripted, no AI).",
        )
    else:
        add(
            "provider",
            "info",
            "Scripted fixture: no AI credential required."
            if args.fixture
            else "Custom composition: provider requirements are unknown until modules load; no credentials checked.",
        )
    add(
        "git",
        "ok" if shutil.which("git") else "warning",
        "Git is available; remote access is NOT checked."
        if shutil.which("git")
        else "Git is not on PATH. Remote bundle/module resolution may need Git even for a fixture.",
    )
    add(
        "terminal",
        "ok" if sys.stdin.isatty() and sys.stdout.isatty() else "warning",
        "Interactive terminal detected."
        if sys.stdin.isatty() and sys.stdout.isatty()
        else "No interactive input/output terminal here. Launch the native app from a terminal, not a pipe.",
    )
    return checks


def support_report(checks):
    # Construct from allowlisted values, never sanitize a dump of environment/config/state.
    return {
        "schema": 1,
        "application": "amplifier-tui",
        "version": version("amplifier-app-tui"),
        "frontend": "ratatui",
        "platform": platform.system(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "checks": checks,
        "scope": "Local prerequisites only; no module load, network, credential validation or conversation read",
        "privacy": "Paths, environment values, usernames, hostnames and conversation content omitted; review before sharing",
    }
