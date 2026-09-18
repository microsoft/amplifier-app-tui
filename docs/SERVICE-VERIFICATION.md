# Verify an account or service deliberately

Local tests use disposable memory storage and loopback HTTP. They prove integration
behavior, not that your personal destination is healthy. A mounted hook, successful
HTTP response, authenticated provider or fluent answer each proves something different.

## Before any personal-service test

Agree on the account, exact destination, selected bundle/configuration, synthetic test
content, maximum requests/time/cost, and who will clean up. Check the service's current
documented deletion and verification methods first. If deletion is unavailable, obtain
explicit agreement to retain the marker before creating it. Do not test against all
configured destinations just because they are present in settings.

Use a fresh conversation and a unique, non-sensitive marker such as
`tui-verification-<random-id>`. Keep account names, URLs, tokens, raw responses and
screenshots in private local evidence. Record created external resources in the
workspace manifest immediately, then record actual cleanup outcomes. Redact separately
for a shareable receipt; hashes are correlation aids, not anonymity guarantees.

## Memory: save, return, inject

1. With the owner's explicit request, save the marker through the actual memory tool
   using human-origin policy. Do not edit its store to simulate success.
2. Verify the saved record through the module's supported read/list interface.
3. Close the first conversation. Open an independent new conversation using the same
   authorized memory destination, without the marker in the new prompt.
4. Use a controlled request observation to establish that the injection hook actually
   placed the saved marker in the provider request. A model repeating it is weaker
   evidence; old conversation context alone is not cross-session memory.
5. Delete only the created marker using the supported mechanism, then independently
   verify its absence. Do not replace or truncate an existing personal memory file.

Local regression uses a real memory module and separately opened runtime sessions,
with `timer=False`; it does not install background jobs or touch personal memory.

## Context intelligence: delivery is not indexing

1. Confirm the selected destination and exclusions before emitting one synthetic event.
2. Correlate the app's session/event identity with local forwarding diagnostics and the
   service's accepted response. Record transport failure separately from policy exclusion.
3. Query the intended service through its documented interface until the agreed deadline.
   Require the unique marker and expected fields; HTTP 200 alone is not queryability.
4. Report accepted-but-not-queryable as incomplete, not success. Respect indexing delays
   and do not repeatedly resend to conceal a failed observation.
5. Delete the test record where supported and verify cleanup, retaining an honest residual
   record if removal is delayed or unavailable.

## Provider login

The account owner completes any browser/device authorization. Do not put codes into
conversation input, save screenshots of them, or paste them into reports. Supported
asynchronous module login uses `/provider login NAME`, then Actions → Provider login
prompt; other providers require their external entrypoint. The module owns tokens.
Test cancelled/expired login without deleting existing credentials. Stop is cooperative
cancellation, not token rollback. Confirm status separately from a deliberately bounded
model-access probe; neither proves all models, routes or future refreshes work.

## Receipt and stop conditions

Record tested source/artifact, policy, time bounds, observed save/delivery/query results,
and cleanup status. Publish only reviewed, allowlisted findings. Stop on unexpected
destinations, unapproved writes, ambiguous identity, missing cleanup authority or a spent
budget. Preserve the failed receipt. A new test requires a new explicit scope, not an
unbounded retry loop. See [migration](MIGRATION.md) and [safe reports](SUPPORT.md).
