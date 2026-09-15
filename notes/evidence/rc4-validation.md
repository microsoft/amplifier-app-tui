# rc4 validation — 2026-09-15

Runtime/release candidate source: `c6817f2351bf0e19ab29fa578d9ee48d347e8260`.
Version: `0.3.0rc4`. This record distinguishes observed gates from remaining scope;
all governing contracts remain DRAFT, with no formal Converge verdict generated.

## Local and live gates

- Final integrated suite: 476 passed in 232.55 seconds with candidates/presets/swaps
  enabled, no warnings, against the final runtime source above.
- Rust: 36 normal/NO_COLOR tests and all-target Clippy; Bun: 3 tests. Ruff/format pass
  for 146 Python files. Direction: 586 contract lines / 49 production source files.
- Both live presets: completed read, explicit no-replay resume, Stop then immediate exit
  during a child question, interrupted parent/child, unanswered stopped question,
  uncertain checkpoint and clean exit. Recovery then creates a new root and, only after
  native menu confirmation, continues a supported persistent child under a new ID/store.
  New execution completes without tools; original receipt/transcript bytes are unchanged.
  Recovery confirmation/adopted captures and configuration detail were inspected privately.
- Real module tests cover same-root and historical-root persistent adoption, public
  message readback, original preservation, stale/foreign identity and private-state refusal.
- Local compiler-free wheel and pinned Git-source installation pass isolated installed
  fixture tool/Help/draft/terminal-restoration/resume/second-turn gates outside the checkout.
  Git source still needs Rust/linker. The shared development launcher is unchanged.

## Performance scope

Thirty alternating fresh-process pairs, warm OS cache, Linux PTY/pyte, 120x40:
native first-paint p95 48.9 ms; first usable composer p95 63.4 ms; scene-ready p95
118.4 ms. Across nine native history/rate cells (1k/10k/100k items, 30/100/500 updates/s),
editing p95 ranges 18.1–19.6 ms and Stop acknowledgement 16.8–18.8 ms. The separate
100-block syntax simulation has editing p95 21.0 ms. Observer/scheduling costs are included.
The comparison also ran nine historical OpenTUI cells; its different fullscreen
projection does not establish matched-output equivalence. These are synthetic renderer
measurements, not cold-start, provider or CLI end-to-end latency.

Actual isolated CLI/TUI preparation with the same minimal fixture confirms six extra
CLI policy modules. Raw policy inventories/hashes remain private: hashes are not
anonymization. Prepared equivalence and matched request-time CLI latency remain open.

## Delivery

Final private CI run `34989557230` passes all five jobs at the source above: native unit
tests, compiler-free installation, actual native loading, installed fixture tool use,
Help/draft safety, no-replay resume, second turn and terminal-mode restoration. Both
macOS runners additionally pass actual PNG pasteboard acquisition through the installed
adapter with original bytes preserved, then clear the disposable fixture.

| Runner | Wheel SHA-256 | Published |
|---|---|---|
| Ubuntu 22.04 x86-64 | `450293ad24560f1a18feb05dfbd51bd0bed513b3f12cb51762988e9b0459f43a` | Yes |
| Ubuntu 24.04 x86-64 | `51d574d583083064f76debf081f8ac11d13a50fc1aa84542d6a3c1607a585bdd` | No, separate private experiment |
| Ubuntu 24.04 ARM64 | `e3f27506807ab8c5651663d384629ec8cf215dd90f4ee0ec8839e415fa22ef89` | Yes |
| macOS 14 ARM64 | `0122294bce9b9704502fc50e97353275ea1e8378fb1bfed13fea9f98a891c77d` | Yes |
| macOS 15 Intel | `e56149d5b940b911d5b5be205c0d7edd9c3fd5f6840eed1b874908517eb76206` | Yes |

The two Linux x86 builds share a filename, not a payload. Only the Ubuntu 22.04 build
is selected for this release. No manylinux/musl, universal2 or physical-desktop claim.
The exact CI ARM wheel passes installed-live delegation, read-only child tool use,
Help without submission, no-replay resume and second turn with both presets, outside
the checkout with no workspace source map. Installed native SHA-256 matches the receipt:
`b9948be05d4d9f7d0ee42a2a9976840c04184dfd265d325ac925f15f016d5f0e`.

A fresh-context privacy reviewer inspected all 195 decompressed members/five receipts,
verified every ZIP/RECORD and wheel/native digest, and matched packaged source to the
release commit. Four wheel/receipt pairs are published in the private
[rc4 prerelease](https://github.com/bkrabach/amplifier-app-tui/releases/tag/v0.3.0rc4).
All eight release assets were downloaded again and matched the reviewed local bytes;
the release tag resolves to the exact tested source above. Temporary CI run/uploads
were deleted after local copies were retained; the API returned HTTP 404. Existing
rc1/rc2/rc3 releases and the checkout-backed development launcher remain unchanged.

The earlier rc4 run at `28090a6` was cancelled/superseded by the native confirmation
correction. Its intermediate artifacts were retained privately, never released; the
temporary run/uploads were deleted and the API returned HTTP 404.

## Explicit remaining scope

Older persistent receipts without relocation fingerprints; arbitrary private/nested
interrupted reconstruction; crash-uncertain recipe effects/subprocess isolation;
uncertain steering replacement and detached/remote cleanup; exclusive external-writer
causality or semantic test coverage; exact context wire/occupancy and vendor-private
conversion; source-character-exact structural reflow and last unflushed keys;
physical desktops, remote clipboard and musl. No automatic replay or shared CLI migration.
No raw captures, user transcripts, credentials or contributor machine paths are published.
