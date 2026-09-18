"""Task labels use controlled instructions, not captured conversations or naming calls."""

import asyncio
import json
from dataclasses import asdict

import pytest
from test_navigation import bridge_for

from amplifier_tui.children import task_title
from amplifier_tui.events import Event
from amplifier_tui.inspection import Inspection


@pytest.mark.parametrize(
    "instruction,expected,source",
    [
        (
            "Perform a read-only architecture review of startup paths.",
            "Architecture review of startup paths",
            "instruction excerpt",
        ),
        (
            "Conduct a bounded, READ-ONLY test coverage review.",
            "Test coverage review",
            "instruction excerpt",
        ),
        (
            "You are a reviewer.\nPlease map startup paths. Leave files unchanged.",
            "Map startup paths",
            "instruction excerpt",
        ),
        (
            "CWD: /fixture/work\nPlease inspect file tools.",
            "Inspect file tools",
            "instruction excerpt",
        ),
        (
            "**Task:** Map startup paths\nKeep the instructions intact.",
            "Map startup paths",
            "instruction heading",
        ),
        (
            "## Goal\nCheck resume handling\nKeep the instructions intact.",
            "Check resume handling",
            "instruction heading",
        ),
        ("Do not edit files. Inspect startup.", "Do not edit files", "instruction excerpt"),
        ("Never delete saved sessions.", "Never delete saved sessions", "instruction excerpt"),
        (
            "Inspect src/école.py and 日本語 paths.",
            "Inspect src/école.py and 日本語 paths",
            "instruction excerpt",
        ),
        ("src/loader.py review", "src/loader.py review", "instruction excerpt"),
        ("Review cafe\u0301", "Review cafe\u0301", "instruction excerpt"),
        (
            "\x1b[31mTask:\x1b[0m Check resume\x1b]0;untrusted\x07",
            "Check resume",
            "instruction heading",
        ),
        ("\n\t", "Delegated task", "unavailable"),
    ],
)
def test_local_task_title_keeps_task_content(instruction, expected, source):
    assert task_title(instruction) == {"task_title": expected, "task_title_source": source}


def test_title_is_bounded_without_scanning_the_rest_of_the_instruction():
    title = task_title("Review " + "word " * 20000 + "\nTask: Unrelated late heading")
    assert title["task_title"] == "Review word word word word word word word…"
    assert len(task_title("x" * 20000)["task_title"]) == 65


@pytest.mark.parametrize(
    "history",
    [
        "Task: Old job",
        "old history\n" * 12000,
        "[PARENT CONVERSATION CONTEXT]\nold\n[END PARENT CONTEXT]\n\n[YOUR TASK]\nTask: Old nested job",
    ],
)
def test_inherited_history_never_becomes_the_current_task_title(history):
    instruction = f"[PARENT CONVERSATION CONTEXT]\n{history}\n[END PARENT CONTEXT]\n\n[YOUR TASK]\nTask: Inspect saved drafts\nKeep all files unchanged."
    assert task_title(instruction) == {
        "task_title": "Inspect saved drafts",
        "task_title_source": "instruction heading",
    }


@pytest.mark.parametrize(
    "suffix",
    [
        "",
        "\n[YOUR TASK]\nTask: Ambiguous",
        "\n[END PARENT CONTEXT]\n\n[YOUR TASK]\n" + "x" * 262144,
    ],
)
def test_unavailable_inherited_task_boundary_is_not_guessed(suffix):
    assert task_title("[PARENT CONVERSATION CONTEXT]\nTask: Old job" + suffix) == {
        "task_title": "Delegated task",
        "task_title_source": "unavailable",
    }


async def test_parallel_titles_survive_observation_persistence_and_new_tasks(
    prepared, tmp_path, monkeypatch
):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        host = bridge.host
        providers = {}
        original = host.children.register

        def register(session):
            providers[id(session)] = session.coordinator.get("providers")["fixture"]
            original(session)

        monkeypatch.setattr(host.children, "register", register)
        instructions = [
            "Task: Map startup paths\nRead the launcher. Do not change files.",
            "Task: Review file tools\nInspect file operations. Do not change files.",
        ]
        results = await asyncio.gather(
            *(host.children.spawn("probe", s, host.session, {"probe": {}}) for s in instructions)
        )
        assert sum(len(p.calls) for p in providers.values()) == 4
        assert not host.session.coordinator.get("providers")["fixture"].calls
        for result, instruction in zip(results, instructions, strict=True):
            child = result["session_id"]
            expected = task_title(instruction)["task_title"]
            assert host.children.summary(child)["task_title"] == expected
            saved = json.loads((host.store.path / "children" / f"{child}.json").read_text())
            assert saved["task_title"] == expected and saved["instruction"] == instruction
            for page in (
                host.inspection.activity_tree(f"child:{child}"),
                Inspection.journal_activity(host.store.path / "events.jsonl", f"child:{child}"),
            ):
                assert page["focus"]["label"].startswith(expected)
                assert (
                    json.loads(page["focus"]["detail"])["arguments"]["instruction"] == instruction
                )
                assert expected in page["breadcrumb"]
        identity = results[0]["session_id"]
        await host.children.resume(
            identity, "Task: Check resume handling\nContinue the same agent."
        )
        assert sum(len(p.calls) for p in providers.values()) == 6  # Two normal calls per run.
        assert host.children.summary(identity)["task_title"] == "Check resume handling"
        assert host.children.summary(results[1]["session_id"])["task_title"] == "Review file tools"
        page = Inspection.journal_activity(host.store.path / "events.jsonl", f"child:{identity}")
        assert page["focus"]["label"].startswith("Check resume handling")
    finally:
        await bridge.close()


def test_activity_task_title_survives_partial_output_finalization_and_multiple_children(tmp_path):
    index, events = Inspection(), []

    def emit(kind, **payload):
        event = Event("title-fixture", len(events) + 1, "turn", kind, "parent", payload)
        events.append(event)
        index.observe(event)

    emit("tool.updated", name="delegate", status="running", arguments={"instruction": "Original"})
    emit("tool.progress", child_progress=[{"task_title": "Map startup paths"}])
    emit("tool.updated", result={"output": "x" * 20000})
    emit("tool.ended", name="delegate", status="succeeded")
    assert index.rows["parent"]["label"] == "Map startup paths · delegate"
    emit(
        "tool.progress",
        child_progress=[{"task_title": "Map startup paths"}, {"task_title": "Review tools"}],
    )
    emit("tool.ended", name="delegate", status="succeeded")
    assert index.rows["parent"]["label"] == "2 tasks · delegate"
    journal = tmp_path / "events.jsonl"
    journal.write_text("".join(json.dumps(asdict(e)) + "\n" for e in events))
    page = Inspection.journal_activity(journal, "parent")
    assert page["focus"]["label"] == page["breadcrumb"] == "2 tasks · delegate"
