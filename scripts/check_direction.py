"""Check local direction shape/links/work references, never behavioral conformance.

Worked checks for the pinned method's documents P2–6/P14–15 and operation P1–2.
This is not the future Converge kit, a ledger generator or a ratification authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from zipfile import ZipFile

VISION_SECTIONS = [
    "What Amplifier TUI is",
    "Principles",
    "What this deliberately resists",
    "How you can tell it is working",
]
CONTRACT_SECTIONS = [
    "Who builds against this",
    "What it is",
    "The promises",
    "Not in v1",
    "How the kit checks it",
    "Open questions",
]
SOURCE_SUFFIXES = {
    ".py",
    ".rs",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".zig",
    ".go",
    ".c",
    ".h",
    ".cpp",
}
GENERATED_DIRS = {"node_modules", "target", "dist", "build", ".venv", ".state", "__pycache__"}
REFERENCE = r"([a-z][a-z0-9-]*\.v\d+):(\d+)"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_document(text: str, name: str, *, vision=False):
    lines = text.splitlines()
    require(bool(lines), f"{name}: empty document")
    heading = lines[0]
    state = re.search(r"\((DRAFT|RATIFIED|LOCKED)(?: (\d{4}-\d{2}-\d{2}))?\)$", heading)
    require(heading.startswith("# ") and state is not None, f"{name}: invalid state heading")
    require(
        len(re.findall(r"\b(?:DRAFT|RATIFIED|LOCKED)\b", heading)) == 1,
        f"{name}: exactly one state word required",
    )
    if state[1] != "DRAFT":
        require(state[2] is not None, f"{name}: settled heading needs a date")
    if state[2]:
        date.fromisoformat(state[2])
    expected = VISION_SECTIONS if vision else CONTRACT_SECTIONS
    require(re.findall(r"^## (.+)$", text, re.M) == expected, f"{name}: section order differs")
    if vision:
        body = text
        require(80 <= len(body.splitlines()) <= 120, f"{name}: vision line budget (80–120)")
        require(
            not re.search(r"\b\d{4}-\d{2}-\d{2}\b", body), f"{name}: dated status in vision body"
        )
        signs = body.split("## How you can tell it is working")[1]
        signs = [line for line in signs.splitlines() if line.startswith("- ")]
        require(bool(signs), f"{name}: no observable signs")
        for sign in signs:
            require(
                re.search(r"\d", sign)
                and re.search(r"developer|reviewer|author|person|steward", sign),
                f"{name}: a sign needs a person and number",
            )
        return {"state": state[1], "promises": []}
    require(50 <= len(lines) <= 100, f"{name}: contract line budget (50–100)")
    artifact = text.split("## What it is")[1].split("## The promises")[0]
    require(artifact.count("```") >= 2, f"{name}: show a fenced artifact before rules")
    promises = text.split("## The promises")[1].split("## Not in v1")[0]
    clauses = re.findall(r"^(\d+)\. (.*?)(?=^\d+\. |\Z)", promises, re.M | re.S)
    numbers = [int(number) for number, _ in clauses]
    require(3 <= len(numbers) <= 8, f"{name}: promise count (3–8)")
    require(
        numbers == sorted(set(numbers)) and numbers[0] > 0,
        f"{name}: duplicate/unordered promise identity",
    )
    for number, clause in clauses:
        parts = [line for line in clause.strip().splitlines() if line.strip()]
        require(2 <= len(parts) <= 4, f"{name}:{number}: promise needs 2–4 lines")
        require(
            "Broken:" in clause and "Affected:" in clause,
            f"{name}:{number}: missing observable failure/reader",
        )
    return {"state": state[1], "promises": numbers}


def check_links(root: Path):
    documents = list(root.glob("*.md"))
    for directory in ("docs", "contracts", "notes"):
        documents.extend((root / directory).rglob("*.md"))
    for path in documents:
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text()):
            if not target.startswith(("https://", "http://", "#")):
                target_path = target.split("#")[0]
                require(not Path(target_path).is_absolute(), f"{path.name}: nonportable local link")
                require((path.parent / target_path).exists(), f"{path.name}: missing link {target}")


def check_plan(text: str, contracts: dict):
    items = []
    for line in text.splitlines():
        if not re.match(r"\| [A-Z]+-\d+ \|", line):
            continue
        columns = [part.strip() for part in line.strip("|").split("|")]
        require(
            len(columns) == 5 and all(columns),
            "Plan items need identity, source, gap, falsifier and state",
        )
        item_id, sources = columns[:2]
        require(item_id not in items, f"Duplicate work item {item_id}")
        require(
            re.fullmatch(rf"{REFERENCE}(?:,\s*{REFERENCE})*", sources),
            f"{item_id}: malformed sources",
        )
        for contract, number in re.findall(REFERENCE, sources):
            require(
                contract in contracts and int(number) in contracts[contract]["promises"],
                f"{item_id}: unknown source promise {contract}:{number}",
            )
        items.append(item_id)
    require(bool(items), "No sourced work items in notes/PLAN.md")
    return items


def source_files(root: Path):
    return [
        path
        for directory in ("src", "frontends")
        for path in (root / directory).rglob("*")
        if path.is_file()
        and path.suffix in SOURCE_SUFFIXES
        and not (set(path.relative_to(root).parts) & GENERATED_DIRS)
    ]


def verify_archive(archive_path: Path, receipt: dict):
    with archive_path.open("rb") as source:
        require(
            hashlib.file_digest(source, "sha256").hexdigest() == receipt["archive_sha256"],
            "Method archive fingerprint differs; review upstream change before adopting it",
        )
    prefix = receipt["package_prefix"]
    with ZipFile(archive_path) as archive:
        manifest = json.loads(archive.read(f"{prefix}/SOURCES.json"))
        repo = next(
            item for item in manifest["repositories"] if item["repository"] == receipt["repository"]
        )
        require(repo["commit"] == receipt["commit"], "Method commit differs from receipt")
        actual_paths = {item["source_relative_path"] for item in repo["files"]}
        require(
            actual_paths == {item["source_relative_path"] for item in receipt["files"]},
            "Method file inventory differs",
        )
        for item in receipt["files"]:
            data = archive.read(f"{prefix}/{receipt['repository']}/{item['source_relative_path']}")
            require(
                len(data) == item["byte_length"]
                and hashlib.sha256(data).hexdigest() == item["sha256"],
                f"Method file fingerprint differs: {item['source_relative_path']}",
            )


def check_repository(root: Path, archive: Path | None = None):
    vision = check_document((root / "docs/VISION.md").read_text(), "VISION", vision=True)
    contracts = {
        path.stem: check_document(path.read_text(), path.name)
        for path in sorted((root / "contracts").glob("*.md"))
    }
    all_contract_files = [path for path in (root / "contracts").rglob("*") if path.is_file()]
    lines = sum(len(path.read_text().splitlines()) for path in all_contract_files)
    require(lines <= 600, "Contract body exceeds method's 600-line ceiling")
    files = source_files(root)
    require(len(files) <= 50, "Production source body exceeds composition P5's 50-file ceiling")
    check_links(root)
    items = check_plan((root / "notes/PLAN.md").read_text(), contracts)
    receipt = json.loads((root / "notes/method-source.json").read_text())
    if archive:
        verify_archive(archive, receipt)
    return {
        "scope": "Structure, local links and work references only; not behavioral or Converge service conformance",
        "vision": vision,
        "contracts": contracts,
        "contract_lines": lines,
        "production_source_files": len(files),
        "work_items": items,
        "method_source_integrity": "verified" if archive else "not checked; supply --archive",
        "formal_verdicts_generated": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--archive", type=Path, help="Verify the optional local private method archive"
    )
    args = parser.parse_args()
    try:
        report = check_repository(args.root, args.archive)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"Direction check failed: {exc}\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
