"""Populate a development workspace from current Amplifier main branches.

Existing checkouts are verified, never reset or updated. New repos are submodules.
Use --historical only to replay the old commits recorded in sources.lock.json.
This is development tooling, not part of the host's runtime policy.
"""

import argparse
import json
import subprocess
from pathlib import Path


def expected_commit(spec, *, historical=False):
    if historical:
        return spec["commit"]
    refs = subprocess.check_output(
        ["git", "ls-remote", "--exit-code", spec["url"], "refs/heads/main"], text=True
    ).splitlines()
    if len(refs) != 1 or refs[0].split()[1] != "refs/heads/main":
        raise ValueError("Source must advertise exactly one main branch")
    return refs[0].split()[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument(
        "--all", action="store_true", help="Both preset closures and inspected repos"
    )
    parser.add_argument(
        "--historical", action="store_true",
        help="Explicitly replay old sources.lock.json commits instead of current main",
    )
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    project = Path(__file__).resolve().parents[1]
    if workspace == project or not (workspace / ".git").exists():
        parser.error("Choose a workspace git root, not this project's source root")
    lock = json.loads((project / "sources.lock.json").read_text())
    selected = (
        lock["repositories"]
        if args.all
        else {
            name: lock["repositories"][name]
            for name in ("amplifier-module-loop-streaming", "amplifier-module-context-simple")
        }
    )
    mapping = {}
    for name, spec in selected.items():
        expected = expected_commit(spec, historical=args.historical)
        target = workspace / name
        if not target.exists():
            subprocess.run(
                ["git", "submodule", "add", *([] if args.historical else ["-b", "main"]),
                 spec["url"], name], cwd=workspace, check=True
            )
            if args.historical:
                subprocess.run(["git", "checkout", "--detach", expected], cwd=target, check=True)
        actual = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=target, text=True
        ).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=target, text=True)
        if actual != expected or dirty:
            basis = "historical source lock" if args.historical else "current remote main"
            parser.error(f"{name} differs from {basis} or has local edits; left untouched. "
                         "Review and update that checkout separately before retrying.")
        mapping[spec["url"].removesuffix(".git")] = name
    map_path = workspace / "tui-sources.json"
    if map_path.exists():
        previous = json.loads(map_path.read_text())
        if any(key in previous and previous[key] != value for key, value in mapping.items()):
            parser.error(f"{map_path.name} has conflicting entries; left untouched")
        mapping = {**previous, **mapping}
    map_path.write_text(json.dumps(mapping, indent=2) + "\n")
    basis = "historical recorded commits" if args.historical else "current remote main"
    print(f"Verified {len(selected)} source checkouts against {basis}; source map: {map_path}")


if __name__ == "__main__":
    main()
