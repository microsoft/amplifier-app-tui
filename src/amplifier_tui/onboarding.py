"""Local onboarding only: no module loading, credential storage or conversation reads."""

import json
import os
import platform
import re
import shutil
import sys
from importlib.metadata import version
from pathlib import Path


def provider_overlay(provider, model, credential_env=None):
    """Generate explicit environment-reference configuration, never credential values."""
    if provider not in ("anthropic", "openai"):
        raise ValueError("Choose anthropic or openai; custom modules use --overlay")
    if (
        not isinstance(model, str)
        or not 0 < len(model) <= 128
        or not all(c.isalnum() or c in "-._:/" for c in model)
    ):
        raise ValueError(
            "Enter an explicit model ID (letters, numbers, -._:/; at most 128 characters)"
        )
    credential_env = credential_env if credential_env is not None else provider.upper() + "_API_KEY"
    if not isinstance(credential_env, str) or not re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_]{0,63}", credential_env
    ):
        raise ValueError("Enter an environment variable NAME, not a key, value or shell expression")
    return {
        "bundle": {"name": f"local-{provider}", "version": "1.0.0"},
        "providers": [
            {
                "module": f"provider-{provider}",
                "source": f"git+https://github.com/microsoft/amplifier-module-provider-{provider}@main",
                "config": {
                    "default_model": model,
                    "api_key": "${" + credential_env + "}",
                },
            }
        ],
    }


def setup_provider():
    """Explicit offline wizard. A new file only; no key prompt or shared settings."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError(
            "--setup needs an interactive terminal; use --getting-started for offline instructions"
        )
    print("Provider setup · no network, model calls, or CLI settings import")
    print("Credentials stay in environment variables. Do not enter an API key here.")
    provider = input("Provider [anthropic/openai]: ").strip().lower()
    model = input("Exact model ID from your provider: ").strip()
    provider_overlay(provider, model)  # Validate before requesting any path.
    path = Path(
        input("New overlay file path (existing files are never replaced): ").strip()
    ).expanduser()
    if not path.name or path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise ValueError("Choose a new file in an existing directory")
    if path.suffix not in (".yaml", ".yml"):
        raise ValueError("Choose a .yaml or .yml overlay path so Foundation can load it")
    credential_env = (
        input(
            f"Credential environment variable NAME [{provider.upper()}_API_KEY] (never the value): "
        ).strip()
        or provider.upper() + "_API_KEY"
    )
    value = provider_overlay(provider, model, credential_env)
    rendered = json.dumps(value, indent=2) + "\n"  # JSON is valid YAML.
    print(rendered)
    print(
        "This trusts the named module's main branch on launch; review or pin its source before use."
    )
    if input("Create this overlay? [y/N]: ").strip().lower() != "y":
        print("Cancelled; nothing written.")
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(rendered)
        stream.flush()
        os.fsync(stream.fileno())
    import shlex

    print(f"Created overlay. Set {credential_env} through your usual secret mechanism.")
    print(f"Launch: amplifier-tui --overlay {shlex.quote(str(path.resolve()))}")
    print(
        "Model/credentials were not validated. Existing conversations keep their recorded composition."
    )


GETTING_STARTED = """Amplifier TUI — your first conversation

1. Check this installation: amplifier-tui --check
   Checks are local only; they do not validate credentials or download modules.
2. Set ANTHROPIC_API_KEY in your environment for the default live provider.
   Never paste a key into chat or a bug report. CLI credentials are not imported.
   Another provider/model? amplifier-tui --setup creates a reviewed overlay without
   storing a key or changing shared settings. Custom modules use --bundle / --overlay.
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
