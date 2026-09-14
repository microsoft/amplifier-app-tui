# Terminal comparison candidates

Current interaction work is in Ratatui with `scripts/run.py`; OpenTUI retains the earlier
comparison controls. The historical same-design description below explains their origin,
not a claim of current interaction parity. See notes/INTERACTION-RECONCILIATION.md.

Both candidates read `../scenes/retry.json` and label the run SIMULATED. Nothing in
that scene executes a command or invokes a provider. The comparison preserves the
concept's muted slate/green/amber palette, three views, quiet tool rows, an approval
card and a persistent draft. This is an experiment toward presentation P1–8, not a
second runtime authority or a completed product port.

These are two engines for one design, not alternative visual proposals. For a layout
review, use Ratatui; use OpenTUI to investigate engine behavior/costs. Both use the
available terminal width with 3-cell edge padding (2 cells below 80 columns).

Shared portable keys: Enter sends, Alt+Enter or Ctrl+J inserts a newline; bracketed
paste always inserts text. F1/F2/F3 change views, Ctrl+E expands evidence, PageUp/Down
scroll the current view, Ctrl+Y/Ctrl+N answer the identified approval, Ctrl+X stops,
Ctrl+Q quits. Shift+Enter works where the terminal reports it distinctly. No hidden
queue/steer behavior: a busy send is rejected and retains the draft.

Comparison resource budgets, declared before measurement: 256 MiB RSS per frontend
for 100,000 short synthetic history records; 64 received records per input-loop
iteration; no busy redraw when idle; at most 60 display frames/second. Shutdown
deadline: 3 seconds for these cooperative fixtures. These are experiment budgets,
not new contract law or promises for arbitrary plugins.

Terminal-tester's examples describe another app; its claimed keymap/startup timings
are not facts about these candidates. Use its generic PTY path and inspect actual
terminal output. ANSI-emulator screenshots approximate fonts/emoji; native terminal
review remains a separate judgment.
