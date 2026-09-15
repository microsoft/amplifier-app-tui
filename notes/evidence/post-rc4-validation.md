# Post-rc4 development validation — 2026-09-15

Runtime source: `d45f913d654246feb4e76d136341577d910c4011`.
Development version: `0.3.0rc5.dev0`. No new release or tag; published rc1–rc4 assets
remain unchanged. Relaunch the checkout-backed development command to load changes.
All governing contracts remain DRAFT; these observations are not formal verdicts.

## Seven delivered increments

1. Legacy interrupted direct-child receipts can prove their policy using the original
   app-owned persistent-store location when the newer relocation fingerprint is absent.
   Execution still requires explicit adoption into a new ID and fresh store, with exact
   public-message readback. Original receipt/transcript bytes stay unchanged. Eight real
   module combinations cover current/legacy receipts, simple/persistent context and
   same/historical roots; changed policy and unsupported private state refuse.
2. An uncertain correction can be copied into an empty idle composer after confirmation.
   Native tests cover occupied-draft refusal, Escape, deliberate copy, unchanged original
   status, zero new turn/queue admissions and saved unsent text. Copying does not retry,
   reverse effects or claim the earlier correction was never inserted.
3. A strict private prepared-policy comparator checks ordered inventories and exact
   fingerprints, rejects invalid evidence and refuses output overwrite. Fresh actual
   CLI 0.1.1 / TUI 0.3.0rc5.dev0 preparations on core 1.6.1 differ in session, instructions
   and tool/hook counts. No normalization removes these differences. Masked credential
   equality would not establish credential or request-time equivalence either.
4. Explicit model discovery displays bounded provider-reported context/output limits
   and known capabilities. Invalid values are omitted; native inspection retains its
   draft with zero admitted turns. Catalog limits are not effective budget or occupancy.
5. Resume restores bounded historical source-version observations without running tools
   or rereading source files to reconstruct them. Later command observations link only matching unchanged
   digests; an external edit breaks the match. Historical provenance remains labelled,
   bounded to 256 paths, and is not exclusive authorship or semantic test coverage.
6. Linux clipboard acquisition tries PNG, JPEG, WebP and GIF under one total deadline.
   Six real utility-process fixtures cover JPEG/WebP/GIF through both wl-paste and xclip.
   Original bytes survive; malformed, animated, oversized or mismatched successful
   responses refuse. These fixtures are not physical desktop or SSH clipboard proof.
7. Provider setup accepts an explicit credential environment-variable name, never its
   value, and requires exact lowercase `.yaml`/`.yml` paths that Foundation can load.
   Invalid names/suffixes do not write; confirmed output remains exclusive and mode 0600.
   This is explicit API-key-reference setup, not OAuth/keychain migration.

## Integrated, terminal and live gates

- Final suite: **498 passed in 223.79 seconds**, candidates/presets/independent swaps
  enabled, no warnings. Rust: 36 normal/NO_COLOR tests and all-target Clippy; Bun: 3.
  Ruff and format pass for 149 files. Direction: 587 contract lines / 49 production files;
  method archive integrity verified separately. No kernel or upstream source changes.
- Both live presets pass read/no-replay resume, Stop then exit during a child question,
  interrupted parent/child accounting, stopped unanswered question, uncertain checkpoint
  and clean terminal exit. The probe changes only its freshly generated test receipt
  into the legacy shape, then adopts through the actual recovered-work menu. A newly
  authorized child completes in fresh persistent storage without tools; original
  receipt/transcript bytes remain identical. Recovery/correction/model captures inspected.
- Exact CI ARM wheel passes installed-live delegation, read-only child tool use, Help
  without submission, no-replay resume and a second turn with both presets outside the
  checkout and without a workspace source map. Installed native SHA-256 matches receipt:
  `6432da3db7916e027796c9204f1a83484fc3a33eeeb8aa855a8b05d2bd6e9aa3`.

## Isolated renderer timing

Thirty alternating fresh-process pairs, warm OS cache, Linux PTY/pyte at 120x40:
native first paint p95 **46.4 ms**, first usable composer **62.1 ms**, scene ready
**112.2 ms**. Across nine native 1k/10k/100k-history by 30/100/500-update cells,
editing p95 **19.4–21.0 ms**, Stop acknowledgement **16.9–20.4 ms**. A separate
100-block syntax simulation reports editing p95 **21.4 ms**. Observer/scheduler costs
are included. Nine historical OpenTUI cells also ran, with a different projection.
These are synthetic renderer observations, not cold-cache, provider or matched CLI
latency. The prepared-policy comparison above still prevents a CLI parity verdict.

## Five-platform candidate artifacts

Private CI run `34996146517` at the runtime source above passed every job: native unit
tests, compiler-free install, native loading, installed PTY fixture tool use, Help/draft
safety, resume without replay, second turn and terminal-mode restoration. Both macOS
runners also passed actual installed-adapter PNG pasteboard acquisition and cleared
the disposable fixture. No physical desktop, musl or broader live-platform claim.

| Runner | Wheel SHA-256 |
|---|---|
| Ubuntu 22.04 x86-64 | `8d4c92a13b366ec3eb16d1baaa44d5d1e3b96eada7d41dc7d6e1d1ed34fa8485` |
| Ubuntu 24.04 x86-64 | `8db1885acd37985e0e81b08ec915ee2b1829df3a0ebe4a1a581b989152ffe908` |
| Ubuntu 24.04 ARM64 | `f148173dc1709a701a2d25710556ec808d9e87ad6dd9c15bf7f7353826194ba8` |
| macOS 14 ARM64 | `6e92c8877547a0c11122d72efa53e7d13b6fa475ee64a3b081ca523eea46ae48` |
| macOS 15 Intel | `4e9614f6923787a0c46f55d2d9eac405578f33c5c1fe08d837ec8c330a39a42f` |

The x86 Linux wheels share a filename, not bytes; separate runner copies are retained
privately. Fresh-context privacy review found no blockers across 195 decompressed
members and five receipts, verified ZIP/RECORD and wheel/native digests, and matched
all packaged source/assets to the commit. Receipts do not embed a source commit;
native build provenance also depends on the recorded CI run/source association.
Temporary CI run/uploads were deleted after local evidence retention; direct API HTTP
404 confirmed removal. No new release was created; existing releases remain unchanged.

## Remaining boundaries

Adequate original-policy evidence is still required for legacy recovery. Arbitrary
nested/private interrupted state, crash-uncertain recipes, detached/remote cleanup and
interrupted-tool replacement remain unresolved. Neither exclusive change causality,
semantic coverage, current context occupancy nor vendor-private conversion is claimed.
General exact structural reflow, last unflushed keystrokes, physical/remote clipboard,
OAuth and musl remain beyond these gates. Matched-policy CLI latency is still open.
Raw captures, policy receipts, transcripts and machine paths remain private.
