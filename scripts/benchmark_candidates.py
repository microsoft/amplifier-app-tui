"""Alternated paired frontend measurements; NOT a claim of CLI parity."""

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import sys
import time

from terminal_probe import ROOT, Probe


def summary(values):
    ordered = sorted(values)
    return {
        "n": len(values),
        "median_ms": statistics.median(values),
        "p95_ms": ordered[math.ceil(len(ordered) * 0.95) - 1],
    }


def command(frontend, extra=()):
    return [sys.executable, str(ROOT / "scripts/compare.py"), frontend, *extra]


def editor_contains(display, token):
    """Observe complete ASCII tokens across visual wraps, confined to the editor."""
    tops = [
        i
        for i, line in enumerate(display)
        if ("╭" in line and "Message" in line) or line.strip().startswith("Message ·")
    ]
    if not tops:
        return False
    parts = []
    open_input = "╭" not in display[tops[-1]]
    pad = len(display[tops[-1]]) - len(display[tops[-1]].lstrip())
    for line in display[tops[-1] + 1 :]:
        if "╰" in line or "[ Actions ]" in line:
            break
        if open_input:
            parts.append(line[pad : len(line) - pad if pad else None])
        elif "│" in line:
            parts.append(line.partition("│")[2].rpartition("│")[0])
    return token.strip() in "".join(parts)


def wait_edit(probe, token):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if editor_contains(probe.screen.display, token):
            return time.monotonic_ns()
        probe.read()
    raise AssertionError(f"Typed token was not visible: {token!r}\n{probe.text}")


def startup(frontend):
    probe = Probe(command(frontend))
    try:
        # The working editor is usable before Send is enabled. Measure that
        # actual boundary, not a hint whose availability depends on readiness.
        deadline = time.monotonic() + 15
        while not any(
            ("╭" in line and "Message" in line) or line.strip().startswith("Message ·")
            for line in probe.screen.display
        ):
            if time.monotonic() >= deadline:
                raise AssertionError("No provisional composer appeared")
            probe.read()
        first = time.monotonic_ns()
        probe.send(b"boot-probe")
        usable = wait_edit(probe, "boot-probe")
        ready = probe.wait("Waiting for your decision")
        return {
            "first_paint_ms": (first - probe.start) / 1e6,
            "first_usable_ms": (usable - probe.start) / 1e6,
            "scene_ready_ms": (ready - probe.start) / 1e6,
            "rss_kib": probe.rss(),
        }
    finally:
        probe.close()


def stress(frontend, history, rate, output):
    trace = ROOT / ".evidence" / f"trace-{frontend}-{history}-{rate}.jsonl"
    probe = Probe(
        command(frontend, ["--history", str(history), "--rate", str(rate), "--trace", str(trace)])
    )
    try:
        probe.wait("Waiting for your decision", timeout=30)
        probe.send(b"\x19")
        probe.wait("simulated test failed")
        probe.send(b"\r")
        probe.wait("Working")
        edits = []
        for index in range(max(200, math.ceil(220 * 60 / rate))):
            token = f"key{index:04d} "
            start = probe.send(token.encode())
            end = wait_edit(probe, token)
            edits.append((end - start) / 1e6)
            probe.rss()
        start = probe.send(b"\x18")
        stop = (probe.wait("Interrupted") - start) / 1e6
        emitted = [json.loads(line) for line in trace.read_text().splitlines()]
        updates = [
            (probe.visible_deltas[e["text"].strip()] - e["emitted_ns"]) / 1e6
            for e in emitted
            if e["text"].strip() in probe.visible_deltas
        ]
        result = {
            "frontend": frontend,
            "history": history,
            "rate": rate,
            "editing": summary(edits),
            "stream_updates": summary(updates) if updates else None,
            "stop_ack_ms": stop,
            "rss_kib": probe.rss(),
            "terminal_bytes": probe.bytes,
            "observer_parse": summary([v / 1e6 for v in probe.observer_ns]),
            "samples": {"edit_ms": edits, "event_ms": updates},
            "delta_observations": len(updates),
            "deltas_emitted": len(emitted),
        }
        output.append(result)
        print(
            json.dumps({key: value for key, value in result.items() if key != "samples"}),
            flush=True,
        )
    finally:
        probe.close()


def syntax_stress():
    """Cold grammar use plus repeated native code commits while editing; no runtime."""
    program = """
import json, select, sys, time
def emit(**message):
    print(json.dumps(dict(version=1, **message)), flush=True)
emit(type='snapshot', session_id='syntax-stress', mode='SIMULATED', ready=True,
     title='Syntax stress', items=[], system=[])
emit(type='state', status='Ready')
samples = [('python', 'def example():\\n    return "hello"'),
           ('rust', 'fn main() { let value = "hello"; }'),
           ('javascript', 'const value = "hello"; // comment'),
           ('bash', 'echo "hello" # comment'),
           ('json', '{"value": 123}'), ('yaml', 'value: true')]
index, deadline = 0, time.monotonic() + .1
while True:
    now = time.monotonic()
    if index < 100 and now >= deadline:
        lang, code = samples[index % len(samples)]
        emit(type='item', id=f'code-{index}', kind='assistant',
             text=f'```{lang}\\n{code}\\n```\\n\\nCode marker {index:03d}')
        index += 1
        deadline = now + .03
        if index == 100:
            emit(type='item', id='end', kind='notice', text='SYNTAX-STRESS-END')
    ready, _, _ = select.select([sys.stdin], [], [], .002)
    if ready:
        line = sys.stdin.readline()
        if not line or json.loads(line).get('op') == 'shutdown': break
"""
    probe = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-u", "-c", program]),
        ]
    )
    try:
        probe.wait("Ready")
        edits = []
        for index in range(240):
            token = f"syntax{index:04d} "
            start = probe.send(token.encode())
            edits.append((wait_edit(probe, token) - start) / 1e6)
            probe.rss()
        probe.wait("SYNTAX-STRESS-END")
        result = {
            "scope": "Ratatui simulated code commits while editing; six bundled grammars, 100 blocks. Not provider or event-to-visible latency.",
            "editing": summary(edits),
            "max_edit_ms": max(edits),
            "rss_kib": probe.peak_rss_kib,
            "samples_ms": edits,
        }
        print(json.dumps({k: v for k, v in result.items() if k != "samples_ms"}), flush=True)
        return result
    finally:
        probe.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=30)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--output", type=str, default="notes/evidence/candidate-benchmark.json")
    args = parser.parse_args()
    path = ROOT / args.output
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "scope": "Candidate scene comparisons only; CLI parity unproven",
        "history_projection": "Ratatui retains all scene source but initially emits the latest 1000 items with a notice; subsequent output is not capped. OpenTUI retains its virtual fullscreen viewport. Not a matched-output or CLI-policy comparison.",
        "platform": platform.system(),
        "arch": platform.machine(),
        "cpu_count": os.cpu_count(),
        "terminal": "Linux PTY / xterm-256color / pyte 0.8.2 / 120x40 / truecolor",
        "cache": "Fresh processes, installed dependencies, warm OS file caches; no cold-cache claim",
        "startup_observation": "First visible composer, then a typed token observed inside it, separately from scene readiness. Send may be unavailable while the provisional editor is already usable.",
        "editing_observation": "Complete ASCII token observed inside the composer, joining its visual rows to account for glyph wrapping. No transcript matches.",
        "uncertainty": "Includes observer parse and scheduler delay; no subtraction. CLI comparison unresolved. Event samples are visible coalesced observations, not every delta.",
        "scene_sha256": hashlib.sha256((ROOT / "scenes/retry.json").read_bytes()).hexdigest(),
        "startup": {"ratatui": [], "opentui": []},
        "stress": [],
    }
    try:
        for pair in range(args.pairs):
            for frontend in ["ratatui", "opentui"] if pair % 2 == 0 else ["opentui", "ratatui"]:
                receipt["startup"][frontend].append(startup(frontend))
        for history in [1000] if args.quick else [1000, 10000, 100000]:
            for rate in [500] if args.quick else [30, 100, 500]:
                for frontend in ["ratatui", "opentui"]:
                    stress(frontend, history, rate, receipt["stress"])
        receipt["startup_summary"] = {
            frontend: {
                metric: summary([r[metric] for r in samples])
                for metric in ["first_paint_ms", "first_usable_ms", "scene_ready_ms"]
            }
            for frontend, samples in receipt["startup"].items()
        }
        receipt["syntax_stress"] = syntax_stress()
        print(json.dumps(receipt["startup_summary"], indent=2))
    finally:
        receipt["source_fingerprints"] = {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                ROOT / "src/amplifier_tui/frontend_bridge.py",
                ROOT / "scripts/terminal_probe.py",
                ROOT / "scripts/benchmark_candidates.py",
                ROOT / "frontends/ratatui/src/main.rs",
                ROOT / "frontends/ratatui/src/interaction.rs",
                ROOT / "frontends/ratatui/src/composer.rs",
                ROOT / "frontends/ratatui/src/chrome.rs",
                ROOT / "frontends/ratatui/src/markdown.rs",
                ROOT / "frontends/ratatui/src/syntax.rs",
                ROOT / "frontends/ratatui/src/transcript.rs",
                ROOT / "frontends/ratatui/src/navigation.rs",
                ROOT / "frontends/ratatui/src/workflow.rs",
                ROOT / "frontends/ratatui/src/controls.rs",
                ROOT / "frontends/ratatui/src/questions.rs",
                ROOT / "frontends/ratatui/src/selection.rs",
                ROOT / "frontends/ratatui/src/native.rs",
                ROOT / "frontends/ratatui/src/workspace.rs",
                ROOT / "frontends/ratatui/src/tables.rs",
                ROOT / "frontends/ratatui/src/code_blocks.rs",
                ROOT / "frontends/ratatui/src/insights.rs",
                ROOT / "frontends/ratatui/src/external_editor.rs",
                ROOT / "frontends/ratatui/Cargo.lock",
                ROOT / "frontends/ratatui/Cargo.toml",
                ROOT / "frontends/opentui/src/main.ts",
                ROOT / "frontends/opentui/src/model.ts",
                ROOT / "frontends/opentui/bun.lock",
                ROOT / "uv.lock",
            ]
        }
        path.write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
