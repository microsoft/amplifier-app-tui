"""Populate an explicit development workspace from the inspected source lock.

Existing checkouts are verified, never reset or updated. New repos are submodules.
This is development tooling, not part of the host's runtime policy.
"""

import argparse
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument(
        "--all", action="store_true", help="Both preset closures and inspected repos"
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
        target = workspace / name
        if not target.exists():
            subprocess.run(
                ["git", "submodule", "add", spec["url"], name], cwd=workspace, check=True
            )
            subprocess.run(["git", "checkout", "--detach", spec["commit"]], cwd=target, check=True)
        actual = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=target, text=True
        ).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=target, text=True)
        if actual != spec["commit"] or dirty:
            parser.error(f"{name} differs from the source lock or has local edits; left untouched")
        mapping[spec["url"].removesuffix(".git")] = name
    map_path = workspace / "tui-sources.json"
    if map_path.exists():
        previous = json.loads(map_path.read_text())
        if any(key in previous and previous[key] != value for key, value in mapping.items()):
            parser.error(f"{map_path.name} has conflicting entries; left untouched")
        mapping = {**previous, **mapping}
    map_path.write_text(json.dumps(mapping, indent=2) + "\n")
    print(f"Verified {len(mapping)} source checkouts; source map: {map_path}")


if __name__ == "__main__":
    main()
