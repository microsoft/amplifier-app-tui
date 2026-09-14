"""Bounded read-only Git observations. Never stage, restore, execute filters or call AI."""

import asyncio
import hashlib
import os
import time
import uuid
from pathlib import Path

LIMIT = 1024 * 1024
MAX_ROWS = 500
NOTICE = (
    "Read-only observation; not agent attribution or test evidence. "
    "Files may change while reading; this is not an atomic snapshot. "
    "External diff, text conversion, clean/process filters and submodule inspection are disabled."
)


def display_path(value):
    return os.fsencode(value).decode("utf-8", "replace") if value is not None else None


class GitReview:
    def __init__(self, cwd):
        self.cwd = Path(cwd)
        self.root = None
        self.rows = {}
        self.token = None
        self.options = []

    async def git(self, *args, allowed=(0,)):
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"}
        }
        env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", LC_ALL="C")
        process = await asyncio.create_subprocess_exec(
            "git",
            "--no-pager",
            "--literal-pathspecs",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=/dev/null",
            *self.options,
            *args,
            cwd=self.cwd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        output = bytearray()
        try:
            async with asyncio.timeout(5):
                while chunk := await process.stdout.read(65536):
                    output.extend(chunk)
                    if len(output) > LIMIT:
                        raise ValueError(
                            "Git output exceeds 1 MiB; nothing truncated or presented as complete"
                        )
                code = await process.wait()
                if code not in allowed:
                    raise ValueError(
                        "Git observation unavailable (not a repository, changed state, or Git error)"
                    )
        finally:
            if process.returncode is None:
                process.kill()
            await process.wait()
        return bytes(output)

    async def setup(self):
        # Disable every configured external clean/process filter, including those
        # referenced by local .gitattributes. --no-textconv alone is insufficient.
        self.options = []
        config = await self.git(
            "config",
            "--null",
            "--name-only",
            "--get-regexp",
            r"^filter\..*\.(clean|process|required)$",
            allowed=(0, 1),
        )
        drivers = {
            key.rsplit(b".", 1)[0].decode("utf-8", "strict") for key in config.split(b"\0") if key
        }
        for driver in sorted(drivers):
            for name, value in (("clean", ""), ("process", ""), ("required", "false")):
                self.options += ["-c", f"{driver}.{name}={value}"]
        self.root = os.fsdecode((await self.git("rev-parse", "--show-toplevel")).rstrip(b"\n"))

    async def status(self):
        raw = await self.git(
            "status", "--porcelain=v1", "-z", "--untracked-files=normal", "--ignore-submodules=all"
        )
        head = await self.git("rev-parse", "--verify", "HEAD", allowed=(0, 128))
        return raw, hashlib.sha256(raw + b"\0" + head).hexdigest()

    async def refresh(self):
        self.rows = {}
        self.token = None
        await self.setup()
        raw, self.token = await self.status()
        fields = iter(raw.split(b"\0"))
        rows = []
        for field in fields:
            if not field:
                continue
            xy, path = field[:2].decode("ascii"), os.fsdecode(field[3:])
            original = os.fsdecode(next(fields)) if "R" in xy or "C" in xy else None
            scopes = (
                ["untracked"]
                if xy == "??"
                else (
                    ["conflict"]
                    if "U" in xy or xy in ("AA", "DD")
                    else [
                        scope
                        for char, scope in zip(xy, ["staged", "unstaged"], strict=True)
                        if char != " "
                    ]
                )
            )
            for scope in scopes:
                if len(rows) >= MAX_ROWS:
                    break
                identity = uuid.uuid4().hex
                row = {
                    "id": identity,
                    "path": path,
                    "original": original,
                    "status": xy,
                    "scope": scope,
                }
                self.rows[identity] = row
                rows.append({**row, "path": display_path(path), "original": display_path(original)})
            if len(rows) >= MAX_ROWS:
                break
        return {
            "rows": rows,
            "root": display_path(self.root),
            "notice": NOTICE,
            "limited": len(rows) >= MAX_ROWS,
            "observed_at": time.time(),
            "token": self.token,
        }

    async def diff(self, identity, token):
        if not self.token or token != self.token or identity not in self.rows:
            raise ValueError("Change selection expired; refresh Workspace changes")
        row = self.rows[identity]
        if (await self.status())[1] != self.token:
            self.rows = {}
            self.token = None
            raise ValueError("Workspace status or HEAD changed; refresh before inspecting")
        scope = row["scope"]
        if scope in ("untracked", "conflict"):
            text = (
                "Untracked path only; contents are not read or followed."
                if scope == "untracked"
                else "Unmerged path; resolve conflicts outside this read-only view."
            )
            base = "not compared"
        else:
            args = [
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                "--no-color",
                "--ignore-submodules=all",
                "--no-renames",
            ]
            if scope == "staged":
                args += ["--cached"]
            # Paths are from the observed Git status, literal, and relative to root.
            args += ["--", row["path"]]
            if row["original"]:
                args.append(row["original"])
            previous = self.cwd
            try:
                self.cwd = Path(self.root)
                text = (await self.git(*args)).decode("utf-8", "replace")
            finally:
                self.cwd = previous
            base = (
                "HEAD → index (empty base on an unborn branch)"
                if scope == "staged"
                else "index → working tree"
            )
            if not text:
                text = "No textual diff returned (path may have changed during this observation)."
            if len(text.encode("utf-8")) > LIMIT:
                raise ValueError("Decoded diff exceeds 1 MiB; no partial text returned")
        return {
            "root": display_path(self.root),
            "path": display_path(row["path"]),
            "scope": scope,
            "base": base,
            "text": text,
            "notice": NOTICE + " Invalid UTF-8 is displayed with replacement characters.",
        }
