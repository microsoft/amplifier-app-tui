"""Fail-closed gate for private prepared-policy receipts, not CLI latency proof.

Exit 0: compared non-secret prepared fields match; 1: differ; 2: invalid evidence.
Credential values were omitted by capture. Neither equality nor hashing validates
credential identity, request-time policy, tool schemas, effects or runtime latency.
"""

import argparse
import json
import os
import re
from pathlib import Path


def compare(left, right):
    def validate(value, kind):
        if not isinstance(value, dict) or value.get("kind") != kind:
            raise ValueError("Expected one CLI and one TUI capture")
        if not isinstance(value.get("core_version"), str) or not value["core_version"]:
            raise ValueError("Missing kernel identity")
        policy = value.get("policy")
        if not isinstance(policy, dict) or set(policy) != {
            "providers",
            "tools",
            "hooks",
            "session_sha256",
            "instruction_sha256",
        }:
            raise ValueError("Incomplete or unknown policy schema")
        for slot in ("providers", "tools", "hooks"):
            rows = policy[slot]
            if not isinstance(rows, list) or len(rows) > 1024:
                raise ValueError("Invalid module inventory")
            for row in rows:
                if not isinstance(row, dict) or set(row) != {
                    "module",
                    "source_sha256",
                    "config_sha256",
                }:
                    raise ValueError("Invalid module evidence")
                if not isinstance(row["module"], str) or not 0 < len(row["module"]) <= 256:
                    raise ValueError("Missing module identity")
                for key in ("source_sha256", "config_sha256"):
                    if not isinstance(row[key], str) or not re.fullmatch(r"[0-9a-f]{64}", row[key]):
                        raise ValueError("Invalid fingerprint")
        for key in ("session_sha256", "instruction_sha256"):
            if not isinstance(policy[key], str) or not re.fullmatch(r"[0-9a-f]{64}", policy[key]):
                raise ValueError("Missing policy fingerprint")
        return policy

    a, b = validate(left, "cli"), validate(right, "tui")
    differences = []
    if left["core_version"] != right["core_version"]:
        differences.append("core_version")
    for key in ("session_sha256", "instruction_sha256"):
        if a[key] != b[key]:
            differences.append(key)
    for slot in ("providers", "tools", "hooks"):
        if len(a[slot]) != len(b[slot]):
            differences.append(f"{slot}.count")
        # Order can encode policy priority. Do not sort away a real difference.
        for index, (x, y) in enumerate(zip(a[slot], b[slot])):
            for field in ("module", "source_sha256", "config_sha256"):
                if x[field] != y[field]:
                    differences.append(f"{slot}[{index}].{field}")
    return {
        "prepared_fields_match": not differences,
        "differences": differences,
        "latency_verdict": "NOT ESTABLISHED",
        "scope": "Ordered prepared-policy fields only. No normalization of storage, sources, instructions or modules. Credential identity, request-time policy/tool schemas and actual CLI/TUI execution must be checked separately; masked credential equality is not equivalence.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--tui", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    def read(path):
        with path.open("rb") as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("Policy receipt exceeds 1 MiB")
        return json.loads(raw)

    try:
        result = compare(read(args.cli), read(args.tui))
        with os.fdopen(
            os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
        ) as stream:
            stream.write(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
    except (OSError, ValueError, TypeError):
        parser.error(
            "Invalid/unavailable evidence or output already exists; no equivalence verdict"
        )
    raise SystemExit(0 if result["prepared_fields_match"] else 1)


if __name__ == "__main__":
    main()
