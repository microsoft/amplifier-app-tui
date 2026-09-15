# AFK continuation validation — 2026-09-15

Runtime candidate source: `b02153d843907ea81907ef3781f5df54204114ec`.
These are development candidates after the published rc3 source, **not replacement
rc3 release assets**. Their package metadata still reads `0.3.0rc3`; source and artifact
hashes below identify the tested candidates. Existing published wheels are unchanged.

## Local and live gates

- Final integrated suite: 469 passed in 211.23 seconds, candidates/presets/swaps enabled,
  no warnings reported. Runtime source is b02153d; the final test-only extension adds
  private-context and foreign-lineage refusal assertions to both child-adoption paths.
- Rust: 35 tests, repeated with NO_COLOR; all-target Clippy passes. Bun: 3 tests.
- Ruff/format/direction pass; 585 contract lines / 49 production source files, all DRAFT.
- Both live presets: completed read, explicit resume without replay, Stop immediately
  followed by exit while a child question waits. Four root/two child turns; interrupted
  parent/child, stopped unanswered question, uncertain checkpoint, clean terminal exit.
- Native provider-fork confirmation and ready captures inspected; draft retained and
  captured context present, no model turn at creation. This path uses a fixture provider.
- Local compiler-free candidate install and installed PTY fixture pass.
- Synthetic 200 conversations / 100,000 messages, 30 warm samples: catalog/search/page
  p95 37.0 ms; native Resume interaction-to-picker-paint p95 68.3 ms. Four bounded index
  refreshes total 2.11 seconds, source journals unchanged. Not matched-policy CLI evidence.

## Private five-platform CI

Run `34982306867` completed successfully at the candidate source above. All five jobs
pass native unit tests, compiler-free install, native executable loading, installed
fixture tool execution, Help/draft safety, no-replay resume, second turn and actual
terminal-mode restoration. Both macOS jobs additionally pass the installed adapter's
real OS PNG pasteboard round trip with original bytes preserved, then clear the fixture.
This is a disposable hosted-runner test, not a physical desktop or remote clipboard test.

| Runner | Wheel SHA-256 |
|---|---|
| Ubuntu 22.04 x86_64 | `72728d58fc1e6d5dd3692d0092256dc71907de15a0cb286344fc490e163fa09b` |
| Ubuntu 24.04 x86_64 | `11944045bf95c75472ee14f0d956e29f4110a29f364df7b0b52a57d0bf93bf75` |
| Ubuntu 24.04 ARM64 | `b9bc9bd9603bd4978673c9715fbd6eebcdf2465260b47a1e9347e820a75a1d6a` |
| macOS 14 ARM64 | `6dbe430e3a2115ea767fb70c0d943925474f8c2f9da44f5581e2cff971f24abf` |
| macOS 15 Intel | `23e15550ef80c4df3d822492c1018c39701a9eb298832be756b2ee799e856d57` |

The two Linux x86 wheels share a filename, not a payload; they remain separate CI
experiments. No new release or broad Linux ABI compatibility claim follows from them.
The exact Linux ARM64 CI wheel additionally passes installed live delegation, child
read-only tool use, Help without submission, no-replay resume and a second turn on both
presets, outside the checkout with no workspace source map. Its installed native SHA-256
is `5afc096b4b0fbefd70957d3c7e87451b31ef092d6ef97dc2de7781fbb5dbab65`.

A fresh-context privacy reviewer inspected all 195 decompressed members and five receipts,
verified ZIP/RECORD and wheel/native digests, and found no blocking private-upload concern.
The temporary run/uploads were removed after evidence capture; the run API returned
HTTP 404. Local private artifact copies remain available. Existing private releases and
the checkout-backed development launcher are intentionally retained.

## Explicit remaining scope

Matched-policy CLI latency; generic private/persistent interrupted-state reconstruction;
crash-uncertain recipe effects and subprocess isolation; exclusive external-writer/test
causality; character-exact structural table transformations; last unflushed keystrokes;
exact provider wire/context occupancy; physical desktops and musl remain unresolved.
No raw captures, user transcripts, credentials or machine-specific paths are published.
