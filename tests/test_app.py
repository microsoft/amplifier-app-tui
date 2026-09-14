import asyncio

from textual.events import Paste
from textual.widgets import Button, TabbedContent, TextArea

from amplifier_tui.app import AmplifierApp
from amplifier_tui.host import SessionHost


async def wait_until(pilot, predicate):
    async with asyncio.timeout(5):
        while not predicate():
            await pilot.pause(0.02)


async def test_draft_during_startup_stream_paste_and_resize(prepared, tmp_path):
    gate = asyncio.Event()
    host = SessionHost()

    async def opener(target):
        await gate.wait()
        await target.open(*prepared, tmp_path)

    app = AmplifierApp(host, opener)
    async with app.run_test(size=(100, 32)) as pilot:
        composer = app.query_one("#composer", TextArea)
        composer.load_text("draft\n世界")
        composer.move_cursor((0, 3))
        selection = composer.selection
        app.action_submit()
        assert composer.text == "draft\n世界" and composer.selection == selection
        gate.set()
        await wait_until(pilot, lambda: host.ready)
        assert composer.text == "draft\n世界" and composer.selection == selection
        host.session.coordinator.get("providers")["fixture"].config["delay"] = 0.2
        await pilot.press("ctrl+s")
        await wait_until(pilot, lambda: host.task is not None)
        app.post_message(Paste("next\nline\n?"))
        await pilot.pause()
        assert composer.text == "next\nline\n?"
        assert host.turn_id
        app.action_submit()
        assert composer.text == "next\nline\n?"
        selection = composer.selection
        app.query_one(TabbedContent).active = "review-view"
        await pilot.pause()
        app.query_one(TabbedContent).active = "system-view"
        await pilot.pause()
        app.query_one(TabbedContent).active = "work-view"
        await pilot.resize_terminal(60, 24)
        await wait_until(pilot, lambda: host.task.done())
        await pilot.pause()
        assert composer.text == "next\nline\n?" and composer.selection == selection
        texts = [i for i in app.transcript.items.values() if i.kind == "assistant"]
        assert len(texts) == 1
        assert texts[0].text.endswith("evidence.")
        assert len([i for i in app.transcript.items.values() if i.kind == "user"]) == 1


async def test_startup_failure_keeps_draft():
    gate = asyncio.Event()

    async def opener(_host):
        await gate.wait()
        raise RuntimeError("missing provider")

    app = AmplifierApp(SessionHost(), opener)
    async with app.run_test() as pilot:
        composer = app.query_one("#composer", TextArea)
        composer.load_text("keep this")
        gate.set()
        await pilot.pause()
        assert composer.text == "keep this"
        assert not app.host.ready


async def test_stale_button_cannot_approve_next_request(prepared, tmp_path):
    host = SessionHost()

    async def opener(target):
        await target.open(*prepared, tmp_path)

    app = AmplifierApp(host, opener)
    async with app.run_test() as pilot:
        await wait_until(pilot, lambda: host.ready)
        first = asyncio.create_task(host.request_approval("First", ["allow", "deny"], 5, "deny"))
        await wait_until(pilot, lambda: bool(app.approval_choices))
        stale_button = app.query_one("#decision-0", Button)
        first_id = next(iter(host._pending))
        host.answer(first_id, "deny")
        assert await first == "deny"
        second = asyncio.create_task(host.request_approval("Second", ["allow", "deny"], 5, "deny"))
        await wait_until(
            pilot, lambda: any(v[0] != first_id for v in app.approval_choices.values())
        )
        app.on_button_pressed(Button.Pressed(stale_button))
        await pilot.pause()
        assert not second.done()
        await pilot.click("#decision-0")
        assert await second == "allow"
