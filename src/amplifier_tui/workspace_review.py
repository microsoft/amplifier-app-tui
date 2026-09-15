"""Bounded Git observations and separately confirmed, source-checked conflict edits."""

import asyncio
import hashlib
import json
import os
import shlex
import stat
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


def junit_target(command):
    """Only an explicit simple pytest invocation; never interpret shell programs."""
    try:
        words = shlex.split(command) if isinstance(command, str) else []
    except ValueError:
        return None
    if not words or any(any(c in word for c in ";&|<>`$\n\r") for word in words):
        return None
    executable = Path(words[0]).name
    direct = executable in ("pytest", "py.test")
    python_module = executable.startswith("python") and words[1:3] == ["-m", "pytest"]
    uv_run = executable == "uv" and (
        words[1:3] == ["run", "pytest"] or words[1:4] == ["run", "--no-sync", "pytest"]
    )
    if not (direct or python_module or uv_run):
        return None
    targets = []
    for index, word in enumerate(words):
        if word in ("--junitxml", "--junit-xml") and index + 1 < len(words):
            targets.append(words[index + 1])
        elif word.startswith(("--junitxml=", "--junit-xml=")):
            targets.append(word.split("=", 1)[1])
    if (
        len(targets) != 1
        or not targets[0]
        or Path(targets[0]).is_absolute()
        or ".." in Path(targets[0]).parts
    ):
        return None
    return targets[0]


def junit_snapshot(cwd, path):
    from .file_input import snapshot

    try:
        value = snapshot(cwd, path)
        return {"sha256": value["sha256"], "text": value["text"]}
    except FileNotFoundError:
        return {"status": "absent"}
    except (OSError, ValueError, UnicodeError):
        return {"status": "unavailable"}


def junit_observation(cwd, path, before):
    from xml.etree import ElementTree

    after = junit_snapshot(cwd, path)
    evidence = {
        "path": path,
        "sha256": after.get("sha256"),
        "status": "unavailable",
        "scope": "Explicit pytest JUnit file changed across this command. Counts are report assertions, not semantic coverage, exclusive command authorship or task acceptance. Source snapshots bracket the command, not individual test cases.",
    }
    if "text" not in after or before.get("status") == "unavailable":
        return evidence
    if before.get("sha256") == after["sha256"]:
        return {**evidence, "status": "unchanged report; not attributed to this command"}
    try:
        xml = after["text"]
        if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
            raise ValueError("DTD/entity declarations refused")
        root = ElementTree.fromstring(xml)
        if root.tag not in ("testsuite", "testsuites"):
            raise ValueError("Not a JUnit report")
        cases = list(root.iter("testcase"))
        if not cases or len(cases) > 2000:
            raise ValueError("Missing or excessive case detail")
        counts = {"tests": len(cases), "failed": 0, "errors": 0, "skipped": 0, "passed": 0}
        for case in cases:
            status = (
                "errors"
                if case.find("error") is not None
                else "failed"
                if case.find("failure") is not None
                else "skipped"
                if case.find("skipped") is not None
                else "passed"
            )
            counts[status] += 1
        return {**evidence, "status": "changed structured report observed", "counts": counts}
    except (ValueError, ElementTree.ParseError):
        return {**evidence, "status": "invalid or unsupported report; counts unavailable"}


class ToolEvidence:
    """Bounded source observations correlated to a tool, never exclusive authorship."""

    def __init__(self, cwd, events=()):
        self.cwd = Path(cwd).resolve()
        self.pending = {}
        self.versions = {}
        for event in events:
            if event.kind == "change.observed":
                self.remember(event.payload, event.turn_id, historical=True)

    def remember(self, row, turn, *, historical=False):
        """Replay bounded version observations only; never read files or run commands."""
        after = row.get("after")
        files = after.get("files") if isinstance(after, dict) else None
        changed = row.get("changed")
        if not isinstance(files, dict) or not isinstance(changed, list):
            return
        for path in changed[:128]:
            if not isinstance(path, str) or len(path) > 4096:
                continue
            self.versions.pop(path, None)
            digest = files.get(path)
            if (
                isinstance(digest, str)
                and len(digest) == 64
                and all(c in "0123456789abcdef" for c in digest)
            ):
                self.versions[path] = {
                    "sha256": digest,
                    "agent": row.get("agent"),
                    "source_session": row.get("source_session"),
                    "tool_call_id": row.get("tool_call_id"),
                    "turn": turn,
                    "overlapping_tools": row.get("overlapping_tools"),
                    "historical": historical,
                }
        while len(self.versions) > 256:
            self.versions.pop(next(iter(self.versions)))

    async def snapshot(self, name, arguments):
        from .file_input import snapshot

        paths, partial = [], False
        if name in ("write_file", "edit_file"):
            target = arguments.get("file_path", arguments.get("path"))
            if not isinstance(target, str):
                return {"files": {}, "partial": True, "scope": "No explicit file target"}
            paths = [target]
        elif name == "bash":
            review = GitReview(self.cwd)
            try:
                await review.setup()
                raw = await review.git(
                    "ls-files", "-z", "--cached", "--others", "--exclude-standard"
                )
                all_paths = list(dict.fromkeys(os.fsdecode(p) for p in raw.split(b"\0") if p))
                paths = all_paths[:128]
                partial = len(all_paths) > len(paths)
                base = Path(review.root)
                paths = [str(base / p) for p in paths]
            except (OSError, ValueError):
                partial = True
        files = {}
        deadline = time.monotonic() + 0.15

        def capture():
            nonlocal partial
            for name in paths:
                if time.monotonic() >= deadline:
                    partial = True
                    break
                relative = name
                try:
                    path = Path(name)
                    relative = str(path.relative_to(self.cwd)) if path.is_absolute() else name
                    value = snapshot(self.cwd, relative)
                    files[relative] = value["sha256"]
                except FileNotFoundError:
                    files[relative] = "absent"
                except (OSError, ValueError, UnicodeError):
                    files[relative] = "unavailable"
                    partial = True

        await asyncio.to_thread(capture)
        return {
            "files": files,
            "sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
            "partial": partial,
            "scope": "Explicit file target or first 128 Git-listed workspace files; 64 KiB UTF-8 per file, 150 ms capture budget. Ignored/outside/symlink/large files excluded; not an atomic snapshot.",
        }

    async def observe(self, event, data, *, session, turn, agent):
        name, call = data.get("tool_name"), data.get("tool_call_id")
        if name not in ("write_file", "edit_file", "bash") or not isinstance(call, str):
            return None
        key = (turn, session, call)
        if event == "tool:pre":
            arguments = data.get("tool_input") or {}
            if not isinstance(arguments, dict) or len(self.pending) >= 128:
                return None
            self.pending[key] = {
                "name": name,
                "arguments": arguments,
                "agent": agent,
                "overlap": bool(self.pending),
                "before": None,
            }
            for other in self.pending.values():
                if len(self.pending) > 1:
                    other["overlap"] = True
            self.pending[key]["before"] = await self.snapshot(name, arguments)
            target = junit_target(arguments.get("command")) if name == "bash" else None
            if target:
                self.pending[key]["junit"] = (
                    target,
                    await asyncio.to_thread(junit_snapshot, self.cwd, target),
                )
            return None
        row = self.pending.pop(key, None)
        if row is None:
            return None
        after = await self.snapshot(name, row["arguments"])
        before = row["before"] or {"files": {}, "partial": True, "scope": "Capture interrupted"}
        result = data.get("result")
        if hasattr(result, "model_dump"):
            result = result.model_dump()
        changed = sorted(
            p
            for p in before["files"].keys() | after["files"].keys()
            if before["files"].get(p) != after["files"].get(p)
        )
        matched = []
        if name == "bash":
            for path, digest in before["files"].items():
                previous = self.versions.get(path)
                if previous and previous["sha256"] == digest and after["files"].get(path) == digest:
                    matched.append({"path": path, **previous})
        output = result.get("output") if isinstance(result, dict) else None
        observation = {
            "name": f"{agent} · {name} · source evidence",
            "source_session": session,
            "tool_call_id": call,
            "agent": agent,
            "status": "tool-correlated observation; external writers not excluded",
            "before": before,
            "after": after,
            "changed": changed,
            "matching_prior_changes": matched,
            "source_stability": "changed during command"
            if changed
            else "partial observation"
            if before["partial"] or after["partial"]
            else "captured files unchanged at command boundaries",
            "returncode": output.get("returncode") if isinstance(output, dict) else None,
            "overlapping_tools": row["overlap"],
            "tool_success": result.get("success") if isinstance(result, dict) else None,
            "command": row["arguments"].get("command") if name == "bash" else None,
            "scope": "Observed source versions bracket this identified tool. Command success is not a test-coverage or task-acceptance verdict; concurrent external edits cannot be causally attributed.",
        }
        self.remember(observation, turn)
        if "junit" in row:
            target, report_before = row["junit"]
            observation["test_report"] = await asyncio.to_thread(
                junit_observation, self.cwd, target, report_before
            )
        return observation

    def interrupted(self):
        """Retain pre-effect observations when no post-tool callback arrives."""
        rows = []
        for (turn, session, call), row in self.pending.items():
            rows.append(
                {
                    "name": f"{row['agent']} · {row['name']} · unresolved source evidence",
                    "source_session": session,
                    "tool_call_id": call,
                    "agent": row["agent"],
                    "status": "No terminal tool observation; effects unknown",
                    "before": row["before"],
                    "after": None,
                    "tool_success": None,
                    "overlapping_tools": row["overlap"],
                    "command": row["arguments"].get("command"),
                    "scope": "Pre-tool capture only. No result or rollback inferred; no command repeated.",
                }
            )
        self.pending.clear()
        return rows


class GitReview:
    def __init__(self, cwd):
        self.cwd = Path(cwd)
        self.root = None
        self.rows = {}
        self.token = None
        self.options = []
        self.edit = None

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
                else "Unmerged path. Prepare conflict edit captures a proposal; only a separately confirmed Apply writes the file. Git staging remains explicit and separate."
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
            "id": identity,
            "token": token,
            "root": display_path(self.root),
            "path": display_path(row["path"]),
            "scope": scope,
            "base": base,
            "text": text,
            "notice": NOTICE + " Invalid UTF-8 is displayed with replacement characters.",
        }

    async def prepare_edit(self, identity, token):
        """Capture only an explicitly selected conflict; do not alter its index."""
        from .file_input import snapshot

        await self.diff(identity, token)
        row = self.rows[identity]
        if row["scope"] != "conflict" or ".git" in Path(row["path"]).parts:
            raise ValueError("Choose an unmerged regular text file; no other path is editable here")
        captured = snapshot(self.root, row["path"])
        self.edit = {**captured, "id": uuid.uuid4().hex, "token": token}
        return {
            **self.edit,
            "notice": "Edit a proposal, then explicitly Apply. Original bytes are backed up privately before replacement. Git index is never staged or marked resolved. Newer detected file versions refuse Apply. This is not a lock against unrelated external writers; stop other writers first.",
        }

    async def apply_edit(self, identity, text, backup_dir):
        """One-use proposal, descriptor-relative writes, backup before replacement.

        Other applications do not participate in our lock: detect version changes
        immediately before replace, but never claim a cross-process CAS transaction.
        """
        from .conversations import atomic_json
        from .file_input import MAX_FILE, snapshot

        value = self.edit
        if not value or identity != value["id"]:
            raise ValueError("Edit proposal expired; capture the conflict again")
        if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_FILE:
            raise ValueError("Replacement must be UTF-8 text of at most 64 KiB")
        if any(ord(c) < 32 and c not in "\n\r\t" for c in text) or "\x7f" in text:
            raise ValueError("Replacement contains terminal-control characters")
        if (await self.status())[1] != value["token"]:
            raise ValueError("Workspace status or HEAD changed; capture the conflict again")
        current = snapshot(self.root, value["path"])
        if current["sha256"] != value["sha256"]:
            raise ValueError("Conflict file changed; proposal retained, no write performed")
        path = Path(value["path"])
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        temporary = None
        try:
            for part in path.parts[:-1]:
                child = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
                )
                os.close(directory)
                directory = child
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            with os.fdopen(fd, "rb") as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                    raise ValueError("Conflict target must be a regular file with one hard link")
                raw = stream.read(MAX_FILE + 1)
                if hashlib.sha256(raw).hexdigest() != value["sha256"]:
                    raise ValueError("Conflict file changed; no write performed")
                backup_dir = Path(backup_dir)
                backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
                backup = backup_dir / f"{identity}.json"
                # This receipt is a backup, not a claim that replacement succeeded.
                atomic_json(
                    backup,
                    {
                        **value,
                        "replacement_sha256": hashlib.sha256(text.encode()).hexdigest(),
                        "status": "backup before attempted write; outcome not certified",
                    },
                )
                temporary = f".amplifier-review-{uuid.uuid4().hex}.tmp"
                out = os.open(
                    temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory
                )
                with os.fdopen(out, "wb") as replacement:
                    replacement.write(text.encode("utf-8"))
                    replacement.flush()
                    os.fchmod(replacement.fileno(), stat.S_IMODE(before.st_mode) & 0o777)
                    os.fsync(replacement.fileno())
                after = os.stat(path.name, dir_fd=directory, follow_symlinks=False)

                def stamp(s):
                    return (
                        s.st_dev,
                        s.st_ino,
                        s.st_size,
                        s.st_mtime_ns,
                        s.st_ctime_ns,
                        s.st_mode,
                        s.st_nlink,
                    )

                if stamp(before) != stamp(after) or stamp(before) != stamp(
                    os.fstat(stream.fileno())
                ):
                    raise ValueError(
                        "Conflict file changed before replacement; backup retained, no write performed"
                    )
                # Consume before the effect: even an fsync failure must never retry.
                self.edit = None
                os.replace(temporary, path.name, src_dir_fd=directory, dst_dir_fd=directory)
                temporary = None
                os.fsync(directory)
        finally:
            if temporary is not None:
                os.unlink(temporary, dir_fd=directory)
            os.close(directory)
        return {
            "path": value["path"],
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "backup": str(backup),
            "text": "Conflict file replaced. Original retained in the private backup; Git index unchanged. Review the file and stage explicitly outside this action.",
        }
