# CLI interoperability gaps

The baseline is the pinned amplifier-app-cli `f0ba883`, its app behaviors and
independent ecosystem modules. Source snapshots are evidence about those revisions,
not universal compatibility. [PLAN](PLAN.md) is the current queue;
[PARITY](PARITY.md) maps working paths and [ACCEPTANCE](ACCEPTANCE.md) owns verification.

| Boundary | Working path | Remaining work |
|---|---|---|
| Canonical history | Same-ID CLI/TUI sessions, directory Resume/search/recall, metadata/names and session settings | Cooperative writer lease and explicit shared crash recovery; current switching is sequential |
| Reading | Structured tools/delegates, native scrollback/copy, Markdown parser, syntax colour and tables | List/paragraph/quote layout and conservative links; see MARKDOWN-GAPS |
| Accounting | Attributed TUI calls and turn/session totals with missing-data disclosure | Import actual CLI event usage/costs and reconcile child identities without duplicate counting |
| Private controls | Native provider/mode/goal/queue/child persistence | Common CLI control-state round trips, unsupported-module refusal and actual-entrypoint persistent-context tests |
| Loaded ecosystem | Independent modules, generic tools, child processes, approvals, questions, cancellation and bounded private module diagnostics | Real account/service/device acceptance under explicit scope, not mount-count claims |
| CLI administration | Pinned CLI command handoff for setup, bundles/providers/routing/modules/sources, directory policy, notifications, update/reset and sessions | No separate wizard is needed merely to duplicate terminal UI; retain shared policy and data |
| Scripted use | CLI-owned run/stdin/text/JSON/trace and shell completion | Installed-artifact verification is tied to the exact wheel/receipt revision |
| Performance | Warm-start and interactive fixture measurements | Match prepared/request policy before claiming CLI-equivalent responsiveness |

CLI source anchors: `main.py:CommandProcessor` owns argument and control semantics;
`commands/session.py:_get_session_display_info` currently labels transcript-line
counts as turns. That naming defect belongs in CLI presentation, not a rewrite of
canonical messages. The shared store should preserve history exactly.

No disposable test-session migration layer is part of the product. A future shared
recovery or control-state change must be derived from current contracts and verified,
not disguised as backward compatibility for an abandoned test format.
