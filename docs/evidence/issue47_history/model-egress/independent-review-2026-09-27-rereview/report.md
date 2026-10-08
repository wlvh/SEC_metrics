# Independent security re-review: #47 model-call path (133a7bd6 + both patches, minted)

Reviewer: a separate agent with a fresh context (same model family, not a human), asked to re-review the fixes of the first review and the E01/D02 extensions. It did not see the author's reasoning. What follows is its report as returned, unedited apart from this header; it is model output, and each finding was reproduced by the author before it was fixed (`README.md` beside this file).

**Setup.** I cloned 133a7bd6 into /tmp/claude-0/native/review-sec-egress, applied both patches and minted (44 rule files, 434 authority files). Nothing was written to /home/user/SEC_metrics.

**Network guard.** Every process ran with a sitecustomize that makes `socket.connect`, `connect_ex`, `sendto`, `getaddrinfo`, `create_connection` and `gethostbyname` raise. A fake `gh` was first on PATH, and GH_TOKEN, GITHUB_TOKEN and DEEPSEEK_API_KEY were unset. The provider opener and the GitHub reader were stubbed. No request left the machine. One neutralization (the live ledger-root check removed) let a call go on to the real opener, and the suite's own `SOCKET_FORBIDDEN` guard stopped it.

**Baseline.** The 104 unmodified target tests pass (1,869 s).

## Verdict
**PASS_WITH_FINDINGS**, but only for applying the patches in #47's runtime tree. The patches open nothing by themselves:
- The egress gate passes with exactly one new caller, `historical_model_egress._Transport.send`.
- E01 and D02 reach the (stubbed) opener only through the chain `execute_historical_semantic > execute_invocation > send > complete > _open_provider_request`.

**Live calls should not be granted after the owner decides M3 alone.** Before any grant:
1. Fix N1 and N2 in code.
2. Fix the M1 residual, N3 and N4, or have the owner explicitly accept them as part of the M3 trust decision. All three reduce to "whoever can write the runtime tree or the ledger's parent directory can reset counts or run unverified code under the approval".
3. Re-run verify.py and re-seal. The committed `offline-verification.json` is stale anyway: it binds 9 files, not all of `CALL_PATH_FILES`, and hashes of older versions. The live path therefore refuses today, which fails closed.

## Prior findings
I neutralized each check one at a time, ran the relevant classes fail-fast, then restored and re-minted. The tree was clean after every run. "By message" means the test fails only because a different, later check refuses with another message; the behaviour did not regress.

**M1 — PARTIALLY FIXED.**
- Tested and caught:
  - Claim-set comparison removed → `test_deleting_a_stopped_slot_refuses_rather_than_releasing_it`: "HistoricalModelCallError not raised".
  - Anchor moved into the root → `test_deleting_the_root_refuses_rather_than_resetting_the_count`.
  - Stop read from the terminal → `test_a_resealed_terminal_that_drops_its_stop_is_refused`.
  - intent≠claim-line check removed → `test_a_changed_slot_is_refused`, by message only (the test's edit is not re-sealed).
- **NOT FIXED: deleting `calls/` together with `claims.jsonl`, keeping `binding.json` and the anchor.** Probe output: `after deleting calls/ + claims.jsonl: [0, 0, 0] []`, then the HTTP_402-stopped request was redrawn and a third one claimed (4 claims under a cap of 2). Tail truncation (last slot plus last claim line) gives `[1, 1, 0] []` and the stopped request is claimed again. No test covers this. #28's CallLedger has the same shape.
- Untested sub-checks (all 18 tests green with each removed): the predecessor chain, the `binding.json` comparison and the anchor-content comparison. The last two are redundant with each other.

**M2 — FIXED; strictness tested only incidentally.**
- Edited comment → caught (`test_an_edited_approval_comment_is_refused`: "ValueError not raised").
- Fetched-vs-saved body → caught.
- Both strict-JSON sites fail their tests by message only: the fixtures keep the policy at [4,4,0]/[12,12,0], so the restatement check refuses anyway.
- I replayed the first review's exact scenario (policy [400,400,0]; body shows [4,4,0] then a duplicate [400,400,0]):
  - as shipped: `ISSUE_47_MODEL_DELEGATION_BODY_IS_NOT_A_RECORD`
  - with last-key-wins parsing: `ACCEPTED with limits [400, 400, 0]`
  - No test replays this scenario.

**L1 — FIXED-AND-TESTED.**
- SEC root compared as text → `test_the_sec_ledger_root_respelt...`.
- #28 root real-path and checkout-ancestor checks → `TheApprovalIsReadGrantByGrant.test_a_budget_root_is_its_own_absolute_path` ("HistoricalAcquisitionError not raised").
- Lock-time symlink check → caught by message (a later write refuses "Immutable receipt parent is unsafe").

**L2 — FIXED at `_Transport.send`, NOT at the boundary.**
- The send-point check is caught by message only (the next check refuses: WB3_OWNER_CONTEXT_REQUIRED). `claimed_slot`'s open-slot condition is caught.
- Probe: `ai_adapter._TRANSPORT_FACTORIES["deepseek"](policy).complete(prepared_request=<#47 request>, egress_capability=getattr(adapter, "_RESERVATION_" + "OWNER_EGRESS_CAPABILITY"))` gave `direct complete reached the opener: 1 call(s)`, with no ledger slot and no WB-3.
- The adapter hook (`historical_model_calls.py:682` `transport_payload`, reached from `ai_adapter.py:1064`) never asks for a counted slot. See L5.

**L3 — D04 FIXED-AND-TESTED; E01/D02 FIXED-NOT-TESTED.**
- D04: the dedicated `test_a_source_edited_and_resealed...` fails with "HistoricalModelCallError not raised" when the rebuild check is removed.
- E01/D02: edited, resealed requests are refused as shipped (`ISSUE_47_MODEL_REQUEST_NOT_IN_ITS_SOURCE`).
- Removing either the source-rebuild or the request-vs-rebuild comparison in `_validate_single` leaves all 8 E01/D02 tests green. With the request comparison removed, `E01 edited request: VALIDATES` and `D02 edited request: VALIDATES`.

**L4 — FIXED-AND-TESTED.** Each neutralization is caught by its live test:
- reference comparison → `test_a_service_count_that_differs...`
- CONTEXT_LIMIT removed from STOPS → `test_a_context_overrun...`: 'CONTEXT_LIMIT' != ''. The unit `test_every_stop_reason_stops` iterates STOPS itself, so it cannot notice a removed reason.
- estimator requirement → `test_a_live_call_is_not_planned_without_the_reference_tokenizer`

**L5 — NOT FIXED (pre-existing).** The gate still matches names only. A module using `getattr(..., "_RESERVATION_" + "OWNER_EGRESS_CAPABILITY")` plus `_TRANSPORT_FACTORIES[...]` passes: `status PASS`.

**L6 — FIXED for the allowance, NOT for the creator journal.**
- Both allowance neutralizations are caught. The exclusive write still refuses (FileExistsError) even without the SkipTest.
- The suite writes LIVE registrations into `.git/issue47-historical-assessments/LIVE/...` of the tree it runs in, and verify.py runs in the runtime tree.
- Probe: SIGTERM right after the runner test's write gave `test process ended with -15`, left one `LIVE/D04/9514c6f7…/313dda56….json` plus the fixture allowance, and `load_historical_assessment(...)` (default → LIVE) accepts it. The batch-path case carries `assessment_input_id sha256:313dda56…, mode LIVE`, built from synthetic outputs.

**L7 — FIXED-AND-TESTED.** `test_the_environment_is_narrowed` catches the full-environment variant.

**Three previously unexercised checks.**
- Send-time re-check: the whole condition is caught. Every sub-condition except `len(markers)==1` (owner pid, owner token, execution id, marker plan id, transport kind) removed together left the **whole live class (18 tests) green**.
- Live ledger-root check: caught (the neutralized run hit SOCKET_FORBIDDEN), but it can be bypassed; see N2.
- Ledger/allowance binding: the delegation_url condition is caught; with the limits condition removed the ledger class stays green.

**M3 — NOT FIXED (owner decision).** Code-held parts verified:
- **(i) Snapshot binding holds for source bytes.** Weakening E01's quote check or the inherited D04 `validate_response`:
  - without re-mint → authority drift / "rule bytes differ"
  - with re-mint → `live_model_ledger` refuses `ISSUE_47_MODEL_WIRING_FILE_CHANGED:requirements/issue_47_v1/baseline_manifest.json`
  - restored → accepted.
  - It does not hold for executed code; see N3 and N4.
- **(ii) Request digests.** `planned_request_digests` equals the claim-side digests for D04 (4), E01 (1) and D02 (1).
  - Prompt changed in code → refused at scope (`…DIGEST_NOT_GRANTED:D04:marriott…`) and at the ledger. 0 slots.
  - Saved 8-K header bytes changed → refused at the rebuild (`HISTORICAL_E01_WINDOW_HAS_NO_REQUEST`) before any slot.
- **What an approval cannot bind:**
  - The poster: the check reads the login only. `performed_via_github_app`, `author_association`, numeric user id and type are ignored; a comment with an app, association NONE, or a different user id and type is `ACCEPTED`.
  - The reader: gh from PATH with its config, proxy and CA environment.
  - Whether the receipt came from the harness: a fixture-shaped receipt passes.
  - Money: count caps only.
- **Can repo code obtain or forge an approval?**
  - Obtain: yes, by posting the proposal body with any credential for wlvh (not tested; no posting).
  - Bypass without one: tampered bytecode can remove any check (N3).

## New findings
- **N1 (high) — LIVE registrations without any call, allowance or ledger.** At `historical_ma_confirmation.py:284`, `historical_legal_review.py:355` and `historical_semantic_results.py:200` the public register functions accept `mode="LIVE"`. The `historical_semantic_results.py:40` docstring claims "There is no way to register LIVE today".
  - Probe results:
    - E01 Pfizer 2025: `WITHHELD → PUBLISHED 3 | registered mode: LIVE`.
    - D02 Marriott 2025: the default consumer carries a LIVE review.
    - D04 Marriott 2024: the default loader accepts it.
  - Consequence: rows read as model-produced, and "a registration only from the slot's own answer" holds only for `register_from_slots`.
  - Fix direction: LIVE records carry the slot evidence (intent, terminal, execution receipt, wire hashes, approval digest, receipt id) and consumers verify it; the mode is derived from a ledger object, never a parameter.
- **N2 (medium) — the caller's allowance mapping picks the ledger.** `_allowance_hashes` (`historical_model_calls.py:485`) omits budget_root and the receipt path/id. The egress checks `ledger.root == prepared.allowance["budget_root"]` (`historical_model_egress.py:201`), and the send-time GitHub re-check (`:112`) never compares the file's root with the ledger.
  - Probe (cap 1): the approved ledger stopped at `HTTP_402`, then `FORGED-ROOT call: SUCCEEDED mode LIVE`.
  - Result: `opener calls in total: 2 (limit granted: 1)`, `same request body sent twice: 2`, while the approved ledger still reads `[1,1,0] ['0001=HTTP_402']`.
  - This bypasses the cap, the stops and no-redraw using the genuine approval and authority.
- **N3 (medium) — bytecode caches are unbound.** The receipt and the authority hash `.py` files, and Python runs timestamp-validated `.pyc` files.
  - Probe: a tampered `__pycache__/historical_model_calls.cpython-311.pyc` that drops the digest checks, with the source untouched and git clean.
  - Receipt and approval verify, the authority re-hash passes, and `request the approval does NOT name: SUCCEEDED`. The genuine cache refuses it.
  - Fix direction: run with a fresh `pycache_prefix` (or `-I`, or checked-hash pycs).
- **N4 (medium-low) — unbound files shadow lazily imported modules.** `tools/vnext_historical_model.py:38` puts `scripts/` first on sys.path; `tokenizers` and `gzip` are first imported during planning (`continuous_request_context.py:9, :65/:80`).
  - Probe with a new `scripts/tokenizers.py`: verification, authority and gate still pass (PASS).
  - The position regroups from 4 requests (167,650 / 182,060 / 197,869 / 28,954 context tokens) into **1 request of 1,692,009 bytes planned at 4,097 tokens**, and it was sent.
  - An approval computed without the shadow would not name that digest, but a shadow can return true counts where the grouping needs them.
- **N5 (low) — D04 approval digests do not name every model-visible byte.** `continuous_semantic_calls.py:113` excludes company_id, document_context (except filing), record_type, request/source ids and unit metadata. Other layers cover these (the snapshot and source proofs).
- **N6 (low) — a deeply nested answer escapes the form check.** The `historical_model_egress.py:227-237` wrappers do not catch RecursionError. A 5,000-level answer raised out of the call path, leaving the slot as `0001=UNKNOWN_PENDING_RECONCILIATION` with the outcome actually known.
- **N7 (low, read only, not probed) — evidence lost after a charged call.** `transport_observation_mismatch` raises after the charge (`historical_model_egress.py:119`) before the wire journal is written, so the raw response is dropped.

**Item 3 results (E01/D02 extensions).**
- **(a) Request type bound to metric — holds.** Renamed metrics and relabelled bytes are refused with 0 slots.
- **(b) Form failures count and are not registered — holds.** Wrong shape and unhashable ids give `FAILED_TERMINAL`, `[1,1,0]`, no stop, and registration is refused. The exception is N6.
- **(c) Registration only from this ledger's own slot, in its mode — holds for `register_from_slots`.** Another request's slot, a LIVE ledger over recorded slots and an edited output are all refused. The exception is N1.
- **(d) No socket and no unregistered caller — holds.** The live path hands the opener exactly the prepared bytes. The exception is L2/L5.
- **(e) D02 review — holds.** Only Item 8 changes (keyword [1113,1321,1322] → review [703,735]; non-Item-8 identical), a review of another request is refused by name, the default does not read a RECORDED review, and a RECORDED record in the LIVE journal is refused. Caveat: an installed RECORDED export flips that root's default (by design, and labelled).
- HTTP 429 without usage stops the channel after one call (USAGE_UNKNOWN), so an outage does not burn the approved requests.

## Not reviewed
Real network and gh behaviour, macOS specifics, the semantic correctness of the contracts, #28 beyond comparison, verify.py (read only, not re-run), cross-machine ledgers, the whole suite in one run, and the D02 output-size risk (Pfizer has 65 must-decide blocks).

**Copy deleted.** /tmp/claude-0/native/review-sec-egress is gone; disk is back to 16 GB free. The original checkout's HEAD moved to ba003938 during the review, through the other agent's work.

## 中文摘要
结论：**PASS_WITH_FINDINGS**，仅限补丁应用于 #47 运行树；**不能仅凭所有者决定 M3 就授予真实调用**。

- **已修好**：M2、L1、L4、L7 修好且有用例覆盖；L3 对 D04 修好有用例，对 E01/D02 修好但无用例。
- **部分修好**：
  - M1：删除 `calls/` 连同 `claims.jsonl` 仍可清零计数并解除停止；
  - L2：只在发送点修好，适配器传输仍可在无槽位时直达连接器；
  - L6：修好了许可文件；但套件会把 LIVE 登记写进真实日志，中断后残留并被默认读取。
- **未修好**：L5、M3。
- **新发现**：
  - N1（高）：公共登记函数接受 `mode="LIVE"`，无调用即可产生被默认批次发布的"LIVE"结果；
  - N2（中）：调用方传入的许可映射可换账本根，绕过上限、停止与禁止重抽；
  - N3（中）：`.pyc` 缓存不受绑定，篡改后可发出未批准请求而校验全部通过；
  - N4（中低）：`scripts/` 下新文件可遮蔽 `tokenizers`，让上下文门禁失效。
