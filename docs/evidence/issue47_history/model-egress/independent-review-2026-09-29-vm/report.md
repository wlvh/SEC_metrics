<!-- Saved verbatim by the executor. The reviewer is a separate agent with a fresh context (same model family, not a human); its harness refused the file write, so it returned the report as text and the executor wrote it here unchanged below this line. Its probes are in probes/ (hard-coded scratch paths as it ran them). -->

VERDICT: PASS_WITH_FINDINGS

The delta may be sealed by verify.py. Before the owner approves a call application for real calls from the executor's VM, two conditions apply:
1. The owner-facing claims must be corrected: F1, plus the durability wording in F2 and F4.
2. F2 and F3 should be fixed first. Both are small. Neither opens a spending path alone, but together they let one approval be spent again from zero with one file copy.

In the VM the gates constrain the executor's code path, not the executor.

Reviewer: a separate agent with a fresh context (same model family, not a human).

## Setup
- What I read: the two delta diffs, plus what they touch: the SEC session's use of the shared start; historical_source_export helpers; historical_counted_calls.ledger_binding; invocation_control.execute_invocation around transport.send; and the owner-facing text (call-application.md, the proposal tool's EXECUTION block, owner-decisions-2026-09-29/decisions.json).
- The checkout moved during the review, not by me: HEAD went from 6923b19e to 66cb8320, with concurrent uncommitted edits to the patch, verify.py and the proposal tool. None of the delta's repository files differ between those two commits.
- My copy: egress-vm-c without .git/objects or __pycache__. Every process had PYTHONPYCACHEPREFIX set to a fresh temp dir, TMPDIR in the scratchpad, and a sitecustomize guard that makes inet connect, getaddrinfo and create_connection raise (I tested that it blocks urlopen). The provider opener was the suite's controlled opener. Zero network requests, nothing posted.
- Repository probes (F1, F2, F3, F5) imported the checkout's modules read-only with bytecode redirected, and wrote only to scratchpad temp dirs.
- Baseline: TheLiveLedgerNeedsItsPublishedStart passes, 7 tests in 105 s.

## Findings

| id | sev | summary | where | reproduced |
|---|---|---|---|---|
| F1 | high (as a stated guarantee; can't be closed in code) | The executor controls the reader in its own VM. call-application.md:8's claim "所以执行者造不出一条会被门禁接受的批准" is false. | historical_source_acquisition.py:451-457, :427-448 | yes |
| F2 | medium | The marker publishes the whole start record (nonce included), and the live path never consults the export guard. Copying the marker back after a lost container spends the approval again from zero, and the same request is sent twice. This applies to the SEC ledger too. | historical_ledger_start.py:121-127, :188-212; historical_model_calls.py:1235-1251 | yes, end to end on the LIVE path |
| F3 | medium | `export` on a host whose ledger is gone creates a fresh ledger at the granted root and overwrites the export with a [0,0,0] one that verifies. | historical_model_export.py:56-89 | yes (recorded and LIVE) |
| F4 | low | `restore` beside a surviving start record gives a spendable ledger, contrary to the docstring and EXECUTION.durability. The export is also re-read after it is verified. | historical_model_export.py:12-14, :142-157 | yes |
| F5 | medium | No-redraw, the cap, and the start and export guards are all keyed on one approval digest. A re-approval (expected after any re-seal) re-sends the same 35 digests. | exported_here, HistoricalModelLedger.claim, propose_model_allowance.py | start part yes, rest reasoned |
| F6 | low, operational | A GitHub read failure at the send-time re-check (after the claim and the egress marker) counts the slot and stops the channel as UNKNOWN, with no socket opened. | _Transport.send; invocation_control.py:2754 | the suite already asserts it |
| F7 | low | Export reads the ledger files after releasing the lock. | historical_model_export.py:64-65 | reasoned |
| F8 | low | Restore's only path-traversal guard is in historical_source_export, which the model receipt does not bind. | verify.py BOUND; _write | reasoned |
| F9 | info | Markers are not bound by issue_url; urlopen follows redirects; issues/comments/{id} can read any comment in the repository. | historical_ledger_start.py:94-118 | reasoned |
| F10 | info, should be stated | The VM proxy re-terminates TLS for every host: the DeepSeek key, prompts and responses, and the GitHub read-back all pass through it. Every process can act on GitHub as the owner (GH_TOKEN/GITHUB_TOKEN are `proxy-injected` placeholders). | env, EXECUTION.transport | env observed |
| F11 | low | One injection is message-only; nothing covers F2-F4; one assertion checks a literal constant; the model CRLF fixture is single-line; the committed patch doesn't contain the patch-side delta yet. | see F11 | yes |

### F1: the executor controls the reader
- live_github_reader() picks anything named gh on PATH; the VM has no gh, so a shim becomes "GitHub".
- The REST reader trusts whatever HTTPS_PROXY and SSL_CERT_FILE the environment names. Here that is 127.0.0.1:45267 with /root/.ccr/ca-bundle.crt.
- The app-mark check stops an approval the executor posts, not one it reads back.

probe_f1_fake_reader.py uses the repository's real model proposal and a 3-line gh shell script that prints a never-posted comment:
```
live_github_reader() -> github_comment_reader | which gh -> .../bin/gh
register_model_approval: MODEL_APPROVAL_REGISTERED [35, 35, 0] ...
model_allowance with the live reader: provenance_verified_against_github = True
require_published_model_start via the same gh: ...#issuecomment-9999999998
```
It also wrote granted-model-ledger.json. Separately, the executor holds DEEPSEEK_API_KEY and could call the provider without this code at all. The previous re-review listed "gh from PATH, its proxy and CA" as unbindable (M3); in the VM that limit now sits with the executor.

Fix:
- Correct the text: in the VM these gates guard against accidents and make the owner's decision auditable; they are not a boundary against the executor.
- The real controls are external: a dedicated key with a provider-side credit limit, revoked after the run, and comparing the exports with the provider's usage log.
- In code, choose the reader explicitly, and record the reader, proxy and CA digest in the start record and the export, as the SEC receipts already do for transport.

### F2: a lost container can match the marker by copying it
Component probe (probe_f2_reconstructed_start.py): `start` is refused ALREADY_EXPORTED and the live check STARTED_ELSEWHERE. After writing marker_record(...) beside the empty root, the live check passes, while exported_here is still True.

End to end (review_probe_live.py::test_p1): one call, a real-tool export, container reset, record copied from the marker:
```
P1 export: 0 EXPORTED [1, 1, 0]
P1 checkout carries this approval's export: True
P1 live ledger on the new host: [0, 0, 0]
P1 opener calls: 2 | same body twice: True
```
The "lost container cannot match / cannot start again" claims are overstated. They appear in the historical_ledger_start docstring, in decisions.json and in EXECUTION.durability. There is also no designed resume path; the only two ways to resume are copying the record (unguarded) and re-approving (F5).

Fix:
- (a) The marker carries a digest of the nonce or record, not the record itself.
- (b) After the start check in live_model_ledger and live_historical_session, refuse unless the checkout's export for this approval has requests ⊆ the local snapshot and counts ≤ the local counts.

### F3: export initializes a ledger and overwrites the export
Recorded probe (probe_f3_export_overwrite.py):
```
export after one claim: [1, 1, 0]
second export on the new host: EXPORTED [0, 0, 0] | index now says [0, 0, 0]
the new host now has an initialized ledger: ['binding.json'] True
verify of the committed export now: [0, 0, 0]
```
LIVE probe (test_p2), same result through the real tool: VERIFIED [0, 0, 0], anchor present.

The start guard still holds, but:
- the working tree's record of spend becomes empty; if committed, the true record survives only in history;
- restoring from it restores an empty ledger;
- with F2, this fresh ledger is what a copied record spends from.
The SEC export refuses first, at its journal checkpoint.

Fix: refuse unless binding.json, the anchor and the mirror already exist (checked before locked()), and refuse to overwrite a same-approval index whose requests aren't a subset of the new state's.

### F4: restore beside a surviving start record
test_p3: remove the root, anchor and mirror but keep the start record, then restore:
```
P3 restore: 0 RESTORED [1, 1, 0] start_restored: False
P3 after restore the ledger spent again: [2, 2, 0] | opener calls: 2
```
start_restored is a literal False in the return value, so asserting it proves nothing. Restoring an older export would resume from an undercount.

Fix: refuse restore while start_record_path(root) exists, and write the members that were verified instead of reading the export a second time.

### F5: a re-approval starts over
probe_f5_reapproval.py: a start for approval B beside approval A's export of the same digests returns LEDGER_START_WRITTEN. The proposal tool recomputes the same digests and never reads earlier exports. One export.json path serves every approval, so B's first export also overwrites A's record. On a persistent machine, the reused budget root would at least have collided with the old ledger; in the VM, a lost container removes that collision.

Fix: the proposal tool excludes (or lists as previously claimed) the digests in the committed export, or `start` refuses when another approval's export claimed digests in the new grants.

### F6-F10
- F6: record a re-check failure as a named, counted, stopping terminal with the slot closed, instead of leaving an unterminated slot. The REST reader (30 s timeout, no retry, through the proxy) makes transient failures likelier.
- F7: read the members inside the same lock as the snapshot.
- F8: bind historical_source_export.py in BOUND, or give _write its own relative-path check.
- F9: check markers' issue_url and user id/type the way _provenance checks approvals, minus the app mark.
- F10: also state that the key is visible to the egress proxy; that "verified against GitHub" means "as the proxy relayed it"; and that before the first export is pushed, a deleted marker plus a lost container has no guard at all.

### F11: tests and injections
I ran the 10 new and 2 updated injections in my copy, judged as verify.py judges them (expected class, fail-fast, private bytecode per run, files restored byte for byte). All 12 were caught by named cases in their expected classes:

| injection | first failing case | note |
|---|---|---|
| THE_LIVE_LEDGER_SKIPS_THE_START | test_a_marker_the_owner_did_not_post_does_not_count | |
| AN_EDITED_START_MARKER_COUNTS | test_an_edited_marker_opens_nothing | |
| A_STRANGERS_START_MARKER_COUNTS | test_a_marker_the_owner_did_not_post_does_not_count | |
| THE_LATEST_START_MARKER_COUNTS | test_an_earlier_start_from_another_host_wins | |
| THE_START_MARKER_NEED_NOT_BE_THIS_HOST_S | test_an_earlier_start_from_another_host_wins | |
| A_LOST_START_IS_NOT_NOTICED | test_a_new_container_meets_the_published_start | message only |
| THE_START_IGNORES_THE_EXPORT | test_an_export_blocks_a_later_start_and_restores_only_as_a_record | |
| THE_EXPORT_NAMES_NO_APPROVAL | test_an_export_blocks_a_later_start_and_restores_only_as_a_record | |
| THE_MODEL_START_IS_THE_SEC_START | test_a_model_start_writes_a_model_record_and_its_marker_verifies | literal-string check |
| THE_REST_READER_READS_ANY_PATH | test_only_this_issue_s_comment_resources_are_readable | |
| THE_APPROVAL_IS_READ_LAST_KEY_WINS | test_a_duplicate_key_in_the_approval_body_is_refused | |
| NO_GITHUB_RECHECK_BEFORE_THE_SOCKET | test_the_approval_is_rechecked_on_github_before_the_socket | |

- A_LOST_START_IS_NOT_NOTICED breaks nothing: the live path still refuses, only with NOT_STARTED instead of STARTED_ELSEWHERE. The property its name describes is start_ledger's marker check; that has no model-side injection (the SEC list's A_LOST_LEDGER_STARTS_AGAIN covers the shared line). Replace or retarget it.
- THE_MODEL_START_IS_THE_SEC_START is first caught by the literal record_type assertion. The designed separation case also fails (per the repository's model-start-injections.json).
- Nothing covers F2's copied record, F3's uninitialized-root export, or F4's surviving start record.
- The model CRLF tests use a single-line body, so interior CRLF and "lone CR" never run on the model side. The shared posted_text is covered only by SEC cases outside the model receipt's suite.
- The committed egress-registration.patch doesn't contain the patch-side delta: `git apply -R --check` fails in egress-vm-c, so verify.py step 1 will refuse. Diff the regenerated patch against patch-side-delta.diff.

## Verified to hold
- (a) Every documented live entry checks allowance, then wiring, then start, before a ledger exists. No accidental path found.
- (b) Model and SEC markers and exports are separated by record_type, digest and index path. An unreadable export index blocks a start.
- (c) The REST reader refuses every path shape except the two allowed ones before building a request (subject to F1 and F9).
- (d) CRLF forgiveness is sound:
  - acceptance requires posted_text(raw) == the proposal bytes, so the parsed approval is exactly the proposal; raw bodies can differ only by CRLF-for-LF and trailing whitespace, and nothing visible can be added;
  - the saved raw body must equal a fresh read byte for byte;
  - both proposal files end without whitespace, so registration is possible.
- (e) Restore refuses to overwrite (target check plus open("xb")), member names go through _safe_member, and verify reruns the ledger's own snapshot (subject to F3 and F4).
- (f) With the export module imported in the sending process, the call is refused ISSUE_47_MODEL_UNBOUND_CODE_LOADED:scripts/vnext/historical_model_export.py with 0 opener calls. historical_ledger_start.py is in both CALL_PATH_FILES and BOUND.
- (g) ORDER, EXPECTED and BOUND are consistent; CALL_PATH_FILES ⊆ BOUND.
- An export after one LIVE call (20 archive members plus the index) contains no provider key and no Authorization/Bearer header.

## Not reviewed
Real network, GitHub and proxy behaviour (including whether GitHub returns performed_via_github_app by default); a full verify.py run; the whole suite in one run; semantic contracts; #28 code beyond the named functions.
