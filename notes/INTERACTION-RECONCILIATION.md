# Interaction source reconciliation

Recorded 2026-09-12 after the steward challenged the shortcut-first prototype and
authorized correction plus usable Amplifier ecosystem execution. This is source/adoption
analysis, not competing direction, ratification or a formal verdict ledger.

Sources are the supplied Codex blueprint (source commit
c4017a87aacc7558002b7cb510025e967c1d765e), Amplifier ecosystem blueprint (repository pins
in sources.lock.json) and preserved design/reference.html. Private archives remain excluded.
The original studies are reconstructed draft contracts, not executed upstream conformance.

| Source | What was lost or reduced | Owning destination / disposition |
|---|---|---|
| Codex experience/composer P1, P4 | Rich drafts, honest history and cancellation | interaction P3; attachments/references remain an explicit later gap |
| Codex composer P2; Amplifier host/input | Submit, queue and steer distinguish timing; focus has precedence | session P2/P6; interaction P2/P6; no fake queue or steer |
| Codex composer P3/P5 | Paste safety and focused, dismissible completion | presentation P2; interaction P2/P4; local action search first, token completion later |
| Codex decisions P1–5; Amplifier host/decisions | Actual scoped options, protected questions and stable request identity | interaction P5; session P7; approval options and queued requests first, structured questions later |
| Codex navigation P1–5 | Explicit identity/cwd, coherent resume/fork and disconnect | continuity P1–3; session P4; durable resume/fork remain unimplemented |
| Codex transcript P1–4 | Source-backed reflow, exact independent evidence | presentation P3/P4/P7; retain the existing tested path |
| Amplifier REBUILD stage 6 / host-session P2 | Meaningful ecosystem discovery, not raw module dumps | ecosystem P1/P2; interaction P6; readable mounted-tool/provider/definition inventory first |
| Supplied HTML concept | Visible buttons, expandable rows, composer actions | interaction P1/P2; keyboard focus plus click, shortcuts secondary |

The study explicitly permits changing exact keybindings after an explicit product
decision. It does not support replacing discovery with an arbitrary wall of Ctrl hints.
Our earlier presentation contract emphasized safety and appearance while leaving that
gap unstated. The new interaction child restores it without prescribing a framework.

## Derived implementation slice

Use Ratatui as the working integration client, reflecting the prior measured preference.
OpenTUI remains the comparison baseline; neither final topology nor a complete product
port is selected. This avoids making two evolving products a prerequisite to proving one.

Visible Actions opens a searchable local menu; Tab cycles visible controls, Enter activates
the focused control, Escape returns to the unchanged composer. Slash at an empty composer
also opens Actions; pasted slash text remains draft text. Menus never call a model merely
because they opened. Approvals do not steal typing focus; their options come from the host,
and every activation retains its request ID. An explicit Decisions action opens the full
question and option list, including options too long for the compact card.

A separate real-work launcher defaults to an actual ecosystem preset, with explicit
provider overlay and isolated host state. Simulation stays in the comparison launcher.
System shows readable composition/capability facts and the optional public skills_discovery
catalog (a startup snapshot, not automatic skill loading). Full raw composition remains inspectable
separately, not the default reading surface. Test two turns, generic evidence, real policy
approval and both presets; label fixture/live evidence distinctly.

This slice does not introduce queue/steer, durable history, attachments, structured user
questions, provider switching, recipe execution or child sessions. Their promises remain
visible in direction and the existing work plan; a functioning turn is not full CLI parity.

## Experience still to evaluate

The immediate review is whether a person can find an action, inspect an approval's scope,
read its result and continue composing without learning a keymap. The working implementation
is evidence for that discussion, not a claim that the complete UX has been designed.
Popups are bounded overlays so the full-width composer remains visible at ordinary sizes;
they do not reinstate the rejected width cap on the conversation itself. Draft history is
explicit selection, not a live preview, and is text-only/in-memory in this slice.
