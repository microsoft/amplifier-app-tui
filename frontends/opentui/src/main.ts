import {
  createCliRenderer,
  TextRenderable,
  BoxRenderable,
  TextareaRenderable,
  RGBA,
} from "@opentui/core";
import { createInterface } from "node:readline";
import { spawn } from "node:child_process";
import {
  palette as p,
  monochrome,
  safe,
  wrap,
  itemLines,
  color,
  type Item,
} from "./model";

const decisionBg = monochrome ? p.panel : "#382f1d";

const index = process.argv.indexOf("--host-json");
if (index < 0) throw Error("Use scripts/compare.py opentui to launch");
const command: string[] = JSON.parse(process.argv[index + 1]);
if (
  !Array.isArray(command) ||
  !command.length ||
  command.some((c) => typeof c !== "string")
)
  throw Error("Invalid host command");
const child = spawn(command[0], command.slice(1), {
  stdio: ["pipe", "pipe", "ignore"],
});
let closed = false,
  disconnected = false,
  timer: ReturnType<typeof setTimeout> | undefined;
const renderer = await createCliRenderer({
  exitOnCtrlC: false,
  exitSignals: [],
  targetFps: 60,
  maxFps: 60,
  backgroundColor: p.bg,
  consoleMode: "disabled",
  useMouse: true,
  useKittyKeyboard: null,
});
const backdrop = new BoxRenderable(renderer, {
  id: "backdrop",
  position: "absolute",
  width: "100%",
  height: "100%",
  backgroundColor: p.bg,
});
renderer.root.add(backdrop);
let title = "A place to do real work",
  context = "Preparing session",
  mode = "STARTING",
  status = "Starting · draft stays editable";
let system: string[] = [],
  approval: any = null,
  view = 0,
  selected = 0,
  expanded = false,
  detailScroll = 0,
  request = 0;
const scroll = [0, 0, 0],
  items: Item[] = [],
  positions = new Map<string, number>(),
  pending = new Map<string, string>();
const widgets: TextRenderable[] = [];
const composerBox = new BoxRenderable(renderer, {
  id: "composer-box",
  position: "absolute",
  border: true,
  borderStyle: "rounded",
  borderColor: p.line,
  title: " Message · draft stays editable ",
  titleColor: p.muted,
});
const approvalBox = new BoxRenderable(renderer, {
  id: "approval-box",
  position: "absolute",
  border: true,
  borderStyle: "rounded",
  borderColor: p.amber,
  backgroundColor: decisionBg,
  titleColor: p.amber,
});
renderer.root.add(approvalBox);
renderer.root.add(composerBox);
const draft = new TextareaRenderable(renderer, {
  id: "draft",
  position: "absolute",
  textColor: p.ink,
  backgroundColor: p.bg,
  focusedBackgroundColor: p.bg,
  selectionBg: p.line,
  selectionFg: p.ink,
  cursorColor: p.green,
  wrapMode: "char",
  placeholder: "Ask, correct, or describe the next task…",
  keyBindings: [
    { name: "return", action: "submit" },
    { name: "return", meta: true, action: "newline" },
    { name: "return", shift: true, action: "newline" },
    { name: "j", ctrl: true, action: "newline" },
  ],
  onSubmit: () => send({ op: "submit", text: draft.plainText }),
});
renderer.root.add(draft);
draft.focus();

function send(value: Record<string, unknown>) {
  if (disconnected || closed) {
    status = "Disconnected · draft retained; no automatic retry";
    schedule();
    return;
  }
  const id = String(++request);
  if (value.op === "submit") pending.set(id, draft.plainText);
  child.stdin.write(
    JSON.stringify({ ...value, version: 1, request_id: id }) + "\n",
  );
}
function decision(option: string) {
  if (approval) send({ op: "decision", approval_id: approval.id, option });
  else {
    status = "No pending decision";
    schedule();
  }
}
function lost() {
  if (!closed) {
    disconnected = true;
    approval = null;
    status = "Disconnected · outcome uncertain; draft retained; no retry";
    schedule();
  }
}
child.on("error", lost);
child.on("exit", lost);
child.stdin.on("error", lost);
function upsert(item: Item) {
  const i = positions.get(item.id);
  if (i === undefined) {
    positions.set(item.id, items.length);
    if (item.kind === "tool") selected = items.length;
    for (let v = 0; v < 2; v++) if (scroll[v] > 0) scroll[v]++;
    items.push(item);
  } else items[i] = item;
}
function receive(value: any) {
  if (value.version !== 1) {
    lost();
    return;
  }
  switch (value.type) {
    case "snapshot":
      title = safe(value.title);
      context = safe(value.context);
      mode = value.mode;
      system = value.system.map(safe);
      if (!draft.plainText) {
        draft.setText(value.draft);
        draft.cursorOffset = value.draft.length;
      }
      value.items.forEach(upsert);
      selected = Math.max(
        0,
        items.findLastIndex((i) => i.kind === "tool"),
      );
      break;
    case "item":
      upsert(value);
      break;
    case "delta": {
      const i = positions.get(value.id);
      if (i !== undefined) items[i].text += value.text;
      else
        upsert({
          id: value.id,
          kind: "assistant",
          text: value.text,
          status: "",
          detail: "",
        });
      break;
    }
    case "system":
      system = value.lines.map(safe);
      break;
    case "state":
      status = safe(value.status);
      approval = value.approval;
      break;
    case "reply": {
      const sent = pending.get(value.request_id);
      pending.delete(value.request_id);
      if (value.accepted && sent !== undefined && draft.plainText === sent)
        draft.setText("");
      if (!value.accepted) status = safe(value.reason);
      break;
    }
    case "error":
      status = safe(value.message);
      break;
  }
  schedule();
}
// Pausing the line iterator bounds pending event application. Each batch yields
// to keyboard handling. The initial snapshot is explicitly bounded by the host.
const lines = createInterface({ input: child.stdout, crlfDelay: Infinity });
void (async () => {
  let batch = 0;
  try {
    for await (const line of lines) {
      if (line.length > 64 * 1024 * 1024) throw Error("Oversize host record");
      receive(JSON.parse(line));
      if (++batch === 64) {
        batch = 0;
        await new Promise((r) => setTimeout(r, 0));
      }
    }
  } catch {
    lost();
  }
})();
function schedule() {
  if (!timer && !closed)
    timer = setTimeout(() => {
      timer = undefined;
      paint();
    }, 0);
}

let cursor = 0;
function text(
  x: number,
  y: number,
  width: number,
  value: string,
  fg = p.ink,
  bg = p.bg,
  click?: () => void,
) {
  if (width <= 0) return;
  let widget = widgets[cursor];
  if (!widget) {
    widget = new TextRenderable(renderer, {
      id: `line-${cursor}`,
      position: "absolute",
      height: 1,
      wrapMode: "none",
      truncate: true,
    });
    renderer.root.add(widget);
    widgets.push(widget);
  }
  cursor++;
  widget.visible = true;
  widget.left = x;
  widget.top = y;
  widget.width = width;
  widget.content = safe(value);
  widget.fg = RGBA.fromHex(fg);
  widget.bg = RGBA.fromHex(bg);
  widget.onMouseDown = click
    ? () => {
        click();
        schedule();
      }
    : undefined;
}
function paint() {
  const width = renderer.width,
    height = renderer.height,
    left = 0,
    pad = width >= 80 ? 3 : 2,
    x = left + pad,
    w = width - pad * 2;
  cursor = 0;
  if (width < 32 || height < 12) {
    text(0, 0, renderer.width, "Please resize to at least 32 × 12", p.amber);
    composerBox.visible = draft.visible = approvalBox.visible = false;
  } else {
    text(x, 1, 12, "amplifier", p.green);
    text(x + 14, 1, w - 14, title);
    text(x, 2, w, `OpenTUI · ${mode} · ${context}`, p.muted);
    text(left, 3, width, "─".repeat(width), p.line);
    ["F1  Work", "F2  Review", "F3  System"].forEach((label, i) =>
      text(
        x + i * 16,
        4,
        Math.min(15, w - i * 16),
        label,
        view === i ? p.green : p.muted,
        view === i ? (monochrome ? p.panel : "#20392f") : p.bg,
        () => {
          view = i;
        },
      ),
    );
    const composerH = height >= 30 ? 7 : 5,
      approvalH = approval ? (height >= 30 ? 7 : 5) : 0,
      composeY = height - composerH,
      approvalY = composeY - approvalH,
      bodyY = 6,
      bodyH = Math.max(0, approvalY - 7);
    if (expanded && items[selected]) {
      const item = items[selected];
      text(
        x,
        bodyY,
        w,
        `Evidence · ${item.text}  [Esc close]`,
        color(item.status),
      );
      const detail = wrap(item.detail, w);
      detailScroll = Math.min(
        detailScroll,
        Math.max(0, detail.length - Math.max(0, bodyH - 2)),
      );
      detail
        .slice(detailScroll, detailScroll + Math.max(0, bodyH - 2))
        .forEach((line, i) =>
          text(
            x,
            bodyY + 2 + i,
            w,
            line,
            line.startsWith("-")
              ? p.red
              : line.startsWith("+")
                ? p.green
                : p.ink,
          ),
        );
    } else if (view === 2)
      system
        .slice(scroll[2], scroll[2] + bodyH)
        .forEach((line, i) =>
          text(x, bodyY + i, w, line, i === 0 ? p.green : p.muted),
        );
    else {
      const end = Math.max(0, items.length - scroll[view]);
      const visible: { index: number; lines: [string, string][] }[] = [];
      let used = 0;
      for (let i = end - 1; i >= 0; i--) {
        if (view === 1 && items[i].kind !== "tool") continue;
        const lines = itemLines(items[i], w, i === selected);
        visible.push({ index: i, lines });
        used += lines.length;
        if (used >= bodyH) break;
      }
      visible.reverse();
      let y = bodyY,
        skip = Math.max(0, used - bodyH);
      for (const item of visible)
        for (const [line, fg] of item.lines) {
          if (skip) {
            skip--;
            continue;
          }
          if (y >= bodyY + bodyH) break;
          text(
            x,
            y++,
            w,
            line,
            fg,
            p.bg,
            items[item.index].kind === "tool"
              ? () => {
                  selected = item.index;
                  expanded = true;
                  detailScroll = 0;
                }
              : undefined,
          );
        }
      if (view === 1 && !used)
        text(x, bodyY, w, "No tool evidence yet", p.muted);
    }
    approvalBox.visible = !!approval;
    if (approval) {
      approvalBox.left = x;
      approvalBox.top = approvalY;
      approvalBox.width = w;
      approvalBox.height = approvalH;
      approvalBox.title = ` Decision needed · ${safe(approval.id)} `;
      if (approvalH >= 7)
        text(x + 2, approvalY + 1, w - 4, approval.prompt, p.ink, decisionBg);
      text(
        x + 2,
        approvalY + approvalH - 4,
        w - 4,
        approval.command,
        p.amber,
        decisionBg,
      );
      text(
        x + 2,
        approvalY + approvalH - 2,
        w - 4,
        "Ctrl+Y Allow once    Ctrl+N Deny",
        p.amber,
        decisionBg,
      );
    }
    composerBox.visible = draft.visible = true;
    composerBox.left = x;
    composerBox.top = composeY;
    composerBox.width = w;
    composerBox.height = composerH - 2;
    draft.left = x + 1;
    draft.top = composeY + 1;
    draft.width = w - 2;
    draft.height = composerH - 4;
    text(
      x,
      height - 2,
      w,
      width >= 100
        ? "Enter send  Alt+Enter newline  ^E evidence  ^T next  ^P copy  ^X stop  ^Q quit"
        : "Enter send  ^J newline  ^E detail  ^X stop  ^Q quit",
      p.muted,
    );
    text(
      left,
      height - 1,
      width,
      ` ${status}`,
      disconnected ? p.red : p.muted,
      p.panel,
    );
  }
  for (let i = cursor; i < widgets.length; i++) widgets[i].visible = false;
  renderer.requestRender();
}
function navigate(amount: number) {
  if (expanded) detailScroll = Math.max(0, detailScroll - amount);
  else
    scroll[view] = Math.min(
      Math.max(0, (view === 2 ? system.length : items.length) - 1),
      Math.max(0, scroll[view] + (view === 2 ? -amount : amount)),
    );
}
backdrop.onMouseScroll = (event) => {
  if (event.scroll) {
    navigate(event.scroll.direction === "up" ? 3 : -3);
    schedule();
  }
};
renderer.keyInput.on("keypress", (key) => {
  let handled = true;
  if (key.ctrl && ["q", "c"].includes(key.name)) void shutdown();
  else if (["f1", "f2", "f3"].includes(key.name))
    view = Number(key.name[1]) - 1;
  else if (key.ctrl && key.name === "e") {
    expanded = !expanded;
    detailScroll = 0;
  } else if (key.ctrl && key.name === "t") {
    for (let step = 1; step <= items.length; step++) {
      const i = (selected + step) % items.length;
      if (items[i].kind === "tool") {
        selected = i;
        detailScroll = 0;
        break;
      }
    }
  } else if (key.ctrl && key.name === "p") {
    if (items[selected]) {
      status = renderer.copyToClipboardOSC52(items[selected].detail)
        ? "Evidence copied via OSC52 (terminal permission required)"
        : "Clipboard unavailable in this terminal";
    }
  } else if (key.ctrl && key.name === "y") decision("allow");
  else if (key.ctrl && key.name === "n") decision("deny");
  else if (key.ctrl && key.name === "x") send({ op: "stop" });
  else if (key.name === "pageup") navigate(5);
  else if (key.name === "pagedown") navigate(-5);
  else if (key.name === "escape") expanded = false;
  else handled = false;
  if (handled) {
    key.preventDefault();
    key.stopPropagation();
    schedule();
  }
});
renderer.on("resize", schedule);
async function shutdown() {
  if (closed) return;
  closed = true;
  clearTimeout(timer);
  renderer.destroy();
  child.stdin.end(JSON.stringify({ version: 1, op: "shutdown" }) + "\n");
  const kill = setTimeout(() => {
    child.kill("SIGKILL");
  }, 3000);
  if (child.exitCode === null && child.signalCode === null)
    await new Promise((resolve) => child.once("exit", resolve));
  clearTimeout(kill);
  process.exit(0);
}
process.on("SIGTERM", () => void shutdown());
process.on("SIGINT", () => void shutdown());
paint();
