"""Private, rebuildable search cache. Journals remain the only source of truth."""

import hashlib
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

READ_BUDGET = 16 * 1024 * 1024
LINE_LIMIT = 1024 * 1024
REFRESH_SECONDS = 1.0


def connect(root):
    path = Path(root) / "history-index.sqlite3"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    os.chmod(path, 0o600)
    db = sqlite3.connect(path, timeout=0.5)
    try:
        db.execute("PRAGMA max_page_count=131072")  # 512 MiB at the standard page size.
        db.execute("PRAGMA trusted_schema=OFF")
        db.execute(
            "CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, signature TEXT, position INTEGER, size INTEGER, modified INTEGER, partial INTEGER, skipping INTEGER DEFAULT 0)"
        )
        if "skipping" not in {row[1] for row in db.execute("PRAGMA table_info(sources)")}:
            db.execute("ALTER TABLE sources ADD COLUMN skipping INTEGER DEFAULT 0")
        db.execute(
            "CREATE TABLE IF NOT EXISTS messages (session TEXT, position INTEGER, sequence INTEGER, kind TEXT, item TEXT, text TEXT, stamp INTEGER, PRIMARY KEY(session,position))"
        )
        db.execute("CREATE INDEX IF NOT EXISTS message_time ON messages(stamp)")
        db.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(session UNINDEXED, position UNINDEXED, folded, tokenize='trigram')"
        )
        return db
    except sqlite3.DatabaseError:
        db.close()
        raise


def open_index(root):
    try:
        return connect(root)
    except sqlite3.DatabaseError as exc:
        if getattr(exc, "sqlite_errorcode", None) not in (
            sqlite3.SQLITE_CORRUPT,
            sqlite3.SQLITE_NOTADB,
        ):
            raise
        # Preserve the invalid derived cache, not the canonical journals. A failed
        # rebuild remains an error; it is never reported as zero search matches.
        path = Path(root) / "history-index.sqlite3"
        path.rename(path.with_name(f"history-index.corrupt-{uuid.uuid4().hex}.sqlite3"))
        return connect(root)


def refresh(db, root, entries, *, budget=READ_BUDGET):
    deadline = time.monotonic() + REFRESH_SECONDS
    partial = False
    active = {entry["id"] for entry in entries}
    known = {row[0]: row[1:] for row in db.execute("SELECT * FROM sources")}
    # Incomplete/never-indexed journals first, so a busy current journal cannot
    # starve old conversations on every refresh.
    ordered = sorted(
        entries,
        key=lambda entry: entry["id"] in known and known[entry["id"]][1] >= known[entry["id"]][2],
    )
    with db:
        for identity in known.keys() - active:
            db.execute("DELETE FROM messages WHERE session=?", (identity,))
            db.execute("DELETE FROM search WHERE session=?", (identity,))
            db.execute("DELETE FROM sources WHERE id=?", (identity,))
        for entry in ordered:
            if budget <= 0 or time.monotonic() >= deadline:
                partial = True
                break
            identity = entry["id"]
            path = Path(root) / "conversations" / identity / "events.jsonl"
            try:
                with path.open("rb") as stream:
                    stat = os.fstat(stream.fileno())
                    prior = known.get(identity)
                    # A fixed first-record fingerprint plus inode/size/mtime detects
                    # replacement/truncation and same-size edits without re-reading
                    # the already indexed body of an append-only journal.
                    prefix = stream.readline(LINE_LIMIT + 1)
                    signature = f"{stat.st_dev}:{stat.st_ino}:" + hashlib.sha256(prefix).hexdigest()
                    position, source_partial = (prior[1], bool(prior[4])) if prior else (0, False)
                    skipping = bool(prior[5]) if prior else False
                    if prior and (
                        prior[0] != signature
                        or stat.st_size < position
                        or (stat.st_size == prior[2] and stat.st_mtime_ns != prior[3])
                    ):
                        db.execute("DELETE FROM messages WHERE session=?", (identity,))
                        db.execute("DELETE FROM search WHERE session=?", (identity,))
                        position, source_partial = 0, False
                        skipping = False
                    stream.seek(position)
                    while budget > 0 and time.monotonic() < deadline:
                        start = stream.tell()
                        line = stream.readline(min(LINE_LIMIT + 1, budget))
                        budget -= len(line)
                        if not line:
                            break
                        if skipping:
                            position = stream.tell()
                            skipping = not line.endswith(b"\n")
                            continue
                        if len(line) > LINE_LIMIT:
                            source_partial = True
                            position = stream.tell()
                            skipping = not line.endswith(b"\n")
                            continue
                        if not line.endswith(b"\n"):
                            break  # An unfinished append is retried next refresh.
                        position = stream.tell()
                        try:
                            event = json.loads(line)
                            if not isinstance(event, dict) or event.get("session_id") != identity:
                                source_partial = True
                                continue
                            if event.get("kind") not in ("turn.accepted", "text.final"):
                                continue
                            text = event.get("payload", {}).get("text")
                            if not isinstance(text, str):
                                source_partial = True
                                continue
                            stamp = event.get("timestamp_ns", 0)
                            stamp = stamp if type(stamp) is int and stamp > 0 else 0
                            sequence = event.get("sequence", 0)
                            if type(sequence) is not int:
                                source_partial = True
                                continue
                            db.execute(
                                "INSERT OR REPLACE INTO messages VALUES (?,?,?,?,?,?,?)",
                                (
                                    identity,
                                    start,
                                    sequence,
                                    event["kind"],
                                    str(event.get("item_id", "")),
                                    text,
                                    stamp,
                                ),
                            )
                            db.execute(
                                "INSERT INTO search VALUES (?,?,?)",
                                (identity, start, text.casefold()),
                            )
                        except (ValueError, TypeError, AttributeError):
                            source_partial = True
                    db.execute(
                        "INSERT OR REPLACE INTO sources VALUES (?,?,?,?,?,?,?)",
                        (
                            identity,
                            signature,
                            position,
                            stat.st_size,
                            stat.st_mtime_ns,
                            int(source_partial),
                            int(skipping),
                        ),
                    )
                    partial |= source_partial or position < stat.st_size
            except OSError:
                # Never return stale matches for an unreadable or vanished source.
                db.execute("DELETE FROM messages WHERE session=?", (identity,))
                db.execute("DELETE FROM search WHERE session=?", (identity,))
                db.execute("DELETE FROM sources WHERE id=?", (identity,))
                partial = True
    return partial


def search(root, entries, query):
    db = open_index(root)
    matches = {}
    try:
        partial = refresh(db, root, entries)
        deadline = time.monotonic() + 0.5
        db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        folded = query.casefold()
        if len(folded) >= 3:
            expression = '"' + folded.replace('"', '""') + '"'
            rows = db.execute(
                "SELECT m.session,m.sequence,m.kind,m.text FROM search s JOIN messages m ON m.session=s.session AND m.position=s.position WHERE search MATCH ? ORDER BY m.stamp DESC,m.position DESC LIMIT 10001",
                (expression,),
            )
        else:
            rows = db.execute(
                "SELECT m.session,m.sequence,m.kind,m.text FROM search s JOIN messages m ON m.session=s.session AND m.position=s.position WHERE instr(s.folded,?)>0 ORDER BY m.stamp DESC,m.position DESC LIMIT 10001",
                (folded,),
            )
        for index, (identity, sequence, kind, text) in enumerate(rows):
            if index == 10000:
                partial = True
                break
            if identity not in matches and folded in text.casefold():
                at = text.casefold().find(folded)
                matches[identity] = (
                    f"{kind} · sequence {sequence} · indexed excerpt\n{text[max(0, at - 80) : at + 400]}"
                )
        return matches, partial
    except sqlite3.OperationalError as exc:
        if getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_INTERRUPT:
            return matches, True
        raise
    finally:
        db.close()
