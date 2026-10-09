# Existing historical SEC ledger: read-only compatibility checkpoint

Base main 73ead3b4. Fixed peer reading 0918862a, existing restored root named
in actual-read-only-state.json. No source/ledger writes or real requests.

The read-only prototype reconciles actual1547 old intents/slots, terminal and
receipt relationships to2531 request rows, original limit1354, additive
extension513 and conservative reserve224. Cumulative1771/effective1867, no
unresolved claimed slots, and narrower one-URL maximum1772 remain. Five small
reader regressions pass in0.016s/zero skips. Initial temp fixture had an
unnormalized macOS path; the fixture was corrected without loosening checks.

This prototype is not called by company_online and grants no capture.
Claim/write/finish compatibility, URL enforcement, concurrency, old-reader/
checkpoint compatibility and full recorded transport remain unimplemented/
unreviewed. Original binding, claims, receipts, resumes and extensions are not
rewritten; no new ledger is created. It is not a delivered live interface.

Main Capture's log-wide403/429 scan needs scoped compatibility review: old
imported request failures are outside the1547 claimed slots, whose terminals
are known. This does not authorize clearing new stops. Only the existing
one-URL purpose may be considered after actual integration.

No Draft PR created for the unfinished adapter. Continue here with a minimal
existing-ledger/recorded-transport implementation; do not declare acquisition
complete from this read-only result. All new business calls0/0/0.
