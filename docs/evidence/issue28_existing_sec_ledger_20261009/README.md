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

## Counted compatibility increment (not live executed)

The explicit historical binding now selects an existing-ledger adapter; the
continuous #28 default is unchanged. It keeps old intent/terminal types and
allowance_binding_id, original initialized root/claims mirror, append-only
numbering, additive extension and conservative reserve. Capture requires the
exact restored source-inputs and one bounded URL; refresh/other root/raised cap
refuse. Original binding remains1354; the adapter retains1867 total and1772
narrow purpose cap. The live root was only read: actual-bounded-preflight.json
checks schema/scope without constructing HTTP transport or claiming a slot.

The recorded tiny ledger capture uses the real SecHttpClient persistence,
immutable body/headers, one appended request row, old-format next intent/plan,
raw wire files, request proof, receipt and terminal. The original checkpoint
validator actually accepts the new capture (recorded test prefix only, no
source credit transferred). Existing claims remain an exact prefix, source
proofs point to the real saved bytes, failure/unknown/plan interruption charge
the opportunity and block redraw. Unclaimed new log tails are refused instead
of being classed as old history; only the prefix before claimed rows is treated
as imported history. New403/429 stops persist. Context is an existing-use
configuration, not new approval or a model invocation.

final-stop-and-prefix-tests.log is the current small test terminal; earlier
failures are retained. The first two capture fixtures lacked real document_name
and source registry, so the client diagnosed/migrated their malformed setup;
fixtures were corrected rather than weakening receipt/registry checks. The
checkpoint-test log imported the reader class and executed five duplicate
reader cases; the final module uses a module import, so tests are not doubled.
No old full material/batch rerun, ledger creation, private-root writes, real
SEC/provider call or account operation. Limited review and receiving consumer
preflight remain required; no Draft PR or delivery/production claim yet.
