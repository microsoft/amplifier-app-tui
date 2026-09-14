"""Textual is the only owner of terminal input and rendering."""

from __future__ import annotations

import json

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Static, TabbedContent, TabPane, TextArea

from .events import Transcript


class AmplifierApp(App):
    TITLE = "amplifier"
    CSS = """
    Screen { background: $surface; }
    #views { height: 1fr; }
    #transcript, #review, #system { padding: 1 2; }
    #composer { height: 6; margin: 0 1; }
    #controls { height: 3; margin: 0 1; }
    #notice { height: 2; padding: 0 1; }
    #approval { height: auto; max-height: 10; padding: 0 1; border: solid $warning; }
    #approval-actions { height: 3; }
    Button { margin-right: 1; }
    """
    BINDINGS = [
        ("ctrl+s", "submit", "Send"),
        ("ctrl+x", "stop", "Stop turn"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, host, opener):
        super().__init__()
        self.host = host
        self.opener = opener
        self.transcript = Transcript()
        self.pending = {}
        self.approval_choices = {}
        self.consumer = None

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(id="views"):
            with TabPane("Work", id="work-view"):
                with VerticalScroll(id="work-scroll"):
                    yield Static("", id="transcript", markup=False)
            with TabPane("Review", id="review-view"):
                with VerticalScroll():
                    yield Static("No tool results yet.", id="review", markup=False)
            with TabPane("System", id="system-view"):
                with VerticalScroll():
                    yield Static("Preparing session…", id="system", markup=False)
        with VerticalScroll(id="approval"):
            yield Static("", id="approval-prompt", markup=False)
            yield Horizontal(id="approval-actions")
        yield TextArea(id="composer", soft_wrap=True)
        with Horizontal(id="controls"):
            yield Button("Send · Ctrl+S", id="send", variant="primary")
            yield Button("Stop · Ctrl+X", id="stop")
        yield Static(
            "Connecting. Your draft stays editable. Enter inserts a newline.",
            id="notice",
            markup=False,
        )
        yield Footer()

    def on_mount(self):
        self.query_one("#approval").display = False
        self.query_one("#composer").focus()
        self.consumer = self.run_worker(self._consume(), exit_on_error=False)
        self.run_worker(self._open(), exit_on_error=False)

    async def _open(self):
        try:
            await self.opener(self.host)
            self.query_one("#notice", Static).update("Ready. Enter: newline · Ctrl+S: send.")
        except Exception as exc:
            self.query_one("#notice", Static).update(f"Startup failed: {exc}. Draft retained.")

    async def _consume(self):
        while True:
            try:
                event = await self.host.next_event()
            except RuntimeError as exc:
                self.query_one("#notice", Static).update(f"Delivery failed: {exc}. Draft retained.")
                return
            self.transcript.apply(event)
            if event.kind == "session.ready":
                self.sub_title = (
                    "Fixture · no live AI"
                    if event.payload.get("fixture")
                    else ", ".join(event.payload.get("providers", []))
                )
                self.query_one("#system", Static).update(json.dumps(event.payload, indent=2))
            elif event.kind == "approval.requested":
                self.pending[event.item_id] = event.payload
                await self._render_approval()
            elif event.kind == "approval.resolved":
                self.pending.pop(event.item_id, None)
                await self._render_approval()
            elif event.kind == "turn.ended":
                self.query_one("#notice", Static).update(
                    f"{event.payload['status']}: {event.payload['message']}"
                )
            elif event.kind == "display.message":
                self.query_one("#notice", Static).update(event.payload["text"])
            self._render_transcript()

    async def _render_approval(self):
        self.query_one("#approval").display = bool(self.pending)
        row = self.query_one("#approval-actions", Horizontal)
        await row.remove_children()
        self.approval_choices.clear()
        if self.pending:
            request_id, data = next(iter(self.pending.items()))
            self.query_one("#approval-prompt", Static).update(data["prompt"])
            for index, option in enumerate(data["options"]):
                button_id = f"decision-{index}"
                button = Button(option, id=button_id)
                self.approval_choices[button] = (request_id, option)
                await row.mount(button)

    def _render_transcript(self):
        scroll = self.query_one("#work-scroll", VerticalScroll)
        following = scroll.is_vertical_scroll_end
        lines, evidence = [], []
        for item in self.transcript.items.values():
            if item.kind == "tool":
                detail = json.dumps(item.detail, ensure_ascii=False, default=str, indent=2)
                lines.append(f"[{item.status}] {item.text}\n{detail}")
                evidence.append(f"[{item.status}] {item.text}\n{detail}")
            elif item.kind == "outcome":
                lines.append(f"[{item.status}] {item.text}")
            else:
                lines.append(f"{'you' if item.kind == 'user' else 'amplifier'}\n{item.text}")
        self.query_one("#transcript", Static).update("\n\n".join(lines))
        if following:
            self.call_after_refresh(scroll.scroll_end, animate=False)
        self.query_one("#review", Static).update(
            "\n\n".join(evidence) or "No tool results yet. File attribution is not available."
        )

    def action_submit(self):
        composer = self.query_one("#composer", TextArea)
        accepted, result = self.host.submit(composer.text)
        if accepted:
            composer.clear()
            self.query_one("#notice", Static).update(
                "Running. You can keep editing the next draft."
            )
        else:
            self.query_one("#notice", Static).update(result)

    def action_stop(self):
        if self.host.stop():
            self.query_one("#notice", Static).update("Stopping; partial effects may remain.")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "send":
            self.action_submit()
        elif event.button.id == "stop":
            self.action_stop()
        elif event.button in self.approval_choices:
            request_id, option = self.approval_choices[event.button]
            if not self.host.answer(request_id, option):
                self.query_one("#notice", Static).update("That decision is no longer pending.")

    async def action_quit(self):
        await self.host.close()
        self.exit()

    async def on_unmount(self):
        await self.host.close()
