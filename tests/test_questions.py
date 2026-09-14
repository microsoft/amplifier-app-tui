"""Structured question capability exercised by the real kernel and streaming loop."""

import asyncio
import copy
from pathlib import Path

import pytest
from test_navigation import bridge_for
from test_runtime_controls import records, wait_for

from amplifier_tui.composition import SourceMap, prepare
from amplifier_tui.conversations import ConversationStore
from amplifier_tui.frontend_bridge import Admission
from amplifier_tui.host import SessionHost
from amplifier_tui.questions import validate_questions

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = [
    {
        "id": "scope",
        "question": "Which scope?",
        "options": [{"label": "Small"}, {"label": "Broad"}],
    },
    {"id": "notes", "question": "What should I keep in mind?"},
]
ANSWERS = {
    "scope": {"option": "Small", "text": ""},
    "notes": {"option": None, "text": "Preserve 🧭\nmy changes"},
}


@pytest.fixture
async def question_prepared(tmp_path, monkeypatch):
    monkeypatch.setenv("AMPLIFIER_HOME", str(tmp_path / "foundation"))
    paths = {
        f"https://github.com/microsoft/{n}": str(ROOT.parent / n)
        for n in ("amplifier-module-loop-streaming", "amplifier-module-context-simple")
    }
    value, report = await prepare(
        str(ROOT / "src/amplifier_tui/fixtures/bundle.yaml"),
        [str(ROOT / "examples/user-questions.yaml")],
        tmp_path,
        SourceMap(paths),
        install_deps=False,
    )
    value.mount_plan["providers"][0]["config"] = {"questions": QUESTIONS}
    return value, report


def request(host, **extra):
    return {
        "op": "question_answer",
        "question_id": next(iter(host.questions.pending)),
        "turn_id": host.turn_id,
        "session_id": host.session_id,
        "answers": copy.deepcopy(ANSWERS),
        **extra,
    }


async def test_actual_tool_explicit_answers_identity_and_resume(question_prepared, tmp_path):
    bridge, events = await bridge_for(question_prepared, tmp_path, tmp_path)
    host = bridge.host
    try:
        host.submit("Ask before proceeding")
        await wait_for(lambda: host.questions.pending)
        assert host.capabilities["questions"]
        assert not host._pending  # Not an approval.
        for extra in (
            {"session_id": "stale"},
            {"turn_id": "stale"},
            {"question_id": "stale"},
            {"answers": {}},
            {"answers": {**ANSWERS, "invented": {}}},
        ):
            assert not bridge.command(request(host, **extra))[0]
        assert not bridge.command(
            request(host, answers={**ANSWERS, "scope": {"option": "invented", "text": ""}})
        )[0]
        assert not host.task.done()
        admission = Admission()
        command = request(host, version=1, request_id="answer-once")
        answer = admission.apply(command, bridge.command)
        assert answer["accepted"]
        assert admission.apply(command, bridge.command) == answer
        assert not bridge.command(command)[0]
        assert await host.task == "completed"
        await asyncio.sleep(0)
        rows = [e for e in records(host) if e["kind"] == "question.updated"]
        assert [e["payload"]["status"] for e in rows] == ["waiting", "answered"]
        assert rows[-1]["payload"]["answers"] == ANSWERS
        assert any(e["type"] == "question" and e["turn_id"] == host.turn_id for e in events)
        assert len([e for e in records(host) if e["kind"] == "turn.accepted"]) == 1
        context = await host.session.coordinator.get("context").get_messages()
        assert "Preserve" in str(context) and "my changes" in str(context)
        identity, launch = host.session_id, host.store.metadata["launch"]
    finally:
        await bridge.close()
    restored = SessionHost(ConversationStore(tmp_path, launch, identity))
    try:
        await restored.open(*question_prepared, tmp_path)
        assert not restored.questions.pending
        assert restored.session.coordinator.get("providers")["fixture"].calls == []
        assert [i for i in restored.store.projection() if i["kind"] == "question"][0][
            "status"
        ] == "answered"
    finally:
        await restored.close()


@pytest.mark.parametrize("outcome", ["cancelled", "stopped", "timed_out"])
async def test_unanswered_never_invents_defaults(question_prepared, tmp_path, outcome):
    bridge, _ = await bridge_for(question_prepared, tmp_path, tmp_path)
    host = bridge.host
    try:
        if outcome == "timed_out":
            host.session.coordinator.get("tools")["request_user_input"].config["timeout"] = 0.05
        host.submit("Ask")
        await wait_for(lambda: host.questions.pending)
        old = request(host)
        if outcome == "cancelled":
            assert bridge.command({**old, "op": "question_cancel"})[0]
        elif outcome == "stopped":
            host.stop()
        await host.task
        assert not host.questions.pending
        assert not bridge.command(old)[0]
        rows = [e for e in records(host) if e["kind"] == "question.updated"]
        assert rows[-1]["payload"]["status"] == outcome
        assert rows[-1]["payload"]["answers"] is None
    finally:
        await bridge.close()


async def test_no_interactive_host_fails_without_waiting(question_prepared, tmp_path):
    host = SessionHost()
    try:
        await host.open(*question_prepared, tmp_path)
        tool = host.session.coordinator.get("tools")["request_user_input"]
        result = await tool.execute({"questions": QUESTIONS})
        assert not result.success and "no interactive" in result.error["message"]
        assert not host.questions.pending
    finally:
        await host.close()


async def test_question_tool_keeps_normal_pre_tool_policy(question_prepared, tmp_path):
    from amplifier_core import HookResult

    bridge, _ = await bridge_for(question_prepared, tmp_path, tmp_path)
    host = bridge.host

    async def deny(event, data):
        return HookResult(action="deny", reason="fixture policy refuses questions")

    host.session.coordinator.hooks.register(
        "tool:pre", deny, priority=1, name="fixture-deny-question"
    )
    try:
        host.submit("Ask")
        await host.task
        assert not any(e["kind"] == "question.updated" for e in records(host))
        assert "fixture policy refuses" in str(
            await host.session.coordinator.get("context").get_messages()
        )
    finally:
        await bridge.close()


async def test_question_limits_and_child_scope(question_prepared, tmp_path):
    bridge, _ = await bridge_for(question_prepared, tmp_path, tmp_path)
    host = bridge.host
    extra = []
    try:
        host.submit("Ask")
        await wait_for(lambda: host.questions.pending)
        assert (await host.questions.ask(QUESTIONS, session_id="child"))["status"] == "unavailable"
        for _ in range(3):
            extra.append(
                asyncio.create_task(host.questions.ask(QUESTIONS, session_id=host.session_id))
            )
        await wait_for(lambda: len(host.questions.pending) == 4)
        assert (await host.questions.ask(QUESTIONS, session_id=host.session_id))[
            "status"
        ] == "limit_reached"
        host.stop()
        await host.task
        assert all(r["status"] == "stopped" for r in await asyncio.gather(*extra))
        assert not host.questions.pending
    finally:
        for task in extra:
            task.cancel()
        await asyncio.gather(*extra, return_exceptions=True)
        await bridge.close()


async def test_recording_failure_cannot_deliver_answers(question_prepared, tmp_path, monkeypatch):
    bridge, _ = await bridge_for(question_prepared, tmp_path, tmp_path)
    host = bridge.host
    try:
        host.submit("Ask")
        await wait_for(lambda: host.questions.pending)
        emit = host.emit

        def fail(kind, *args, **kwargs):
            if kind == "question.updated" and kwargs["status"] == "answered":
                raise OSError("disk unavailable")
            return emit(kind, *args, **kwargs)

        monkeypatch.setattr(host, "emit", fail)
        with pytest.raises(OSError):
            bridge.command(request(host))
        assert not host.ready and not host.questions.pending
        await host.task
        context = await host.session.coordinator.get("context").get_messages()
        assert "my changes" not in str(context)
    finally:
        await bridge.close()


@pytest.mark.parametrize(
    "value",
    [
        [],
        QUESTIONS * 2,
        [{"id": "bad id", "question": "why"}],
        [{"id": "q", "question": " "}],
        [QUESTIONS[0], QUESTIONS[0]],
        [{"id": "q", "question": "why", "options": [{"label": "same"}] * 2}],
        [{"id": "q", "question": "why", "options": ["not a choice"]}],
    ],
)
def test_question_validation(value):
    with pytest.raises(ValueError):
        validate_questions(value)


def test_launcher_defaults_are_explicit_ordered_and_optional(monkeypatch):
    import runpy
    import sys

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    arguments = runpy.run_path(str(ROOT / "scripts/run.py"))["arguments"]
    _, command = arguments(["--fixture", "--overlay", "custom.yaml"])
    assert command.index(str(ROOT / "examples/user-questions.yaml")) < command.index("custom.yaml")
    _, command = arguments(["--fixture", "--no-questions"])
    assert not any("user-questions.yaml" in part for part in command)
    assert command[0] == sys.executable


def test_live_probe_readiness_ignores_restored_ready_text(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    from questions_probe import wait_ready

    class Observer:
        screen = SimpleNamespace(display=["Ready is old assistant text", "Starting"])
        reads = 0

        def read(self, timeout):
            self.reads += 1
            self.screen.display[-1] = " Ready · real modules mounted "

    probe = Observer()
    wait_ready(probe)
    assert probe.reads == 1
