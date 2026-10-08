# Security review of the D04 egress patch (2026-09-27)

**Who reviewed.** A separate agent started for this review with a fresh context
and no access to the executor's reasoning: a subagent of the same model family,
not a human and not a different vendor. The owner's instruction was that the
executor's own review does not count; this is the closest independent reading
this environment offers, and it is labelled as what it is.

**What was reviewed.** HEAD `92da6f2f` plus both patches in
`../egress-registration.patch`, applied and minted in temporary copies. The
receipt's bound hashes matched those copies. All probes ran with DNS, sockets
and SEC raising, a controlled opener and a stubbed GitHub reader. Nothing was
written to the checkout; all copies were deleted. Real network behaviour,
`gh`, macOS filesystem case behaviour and D04 acceptance semantics were not
reviewed.

**Verdict.** PASS_WITH_FINDINGS - for applying both patches in #47's runtime
copy only, where they enable no call by themselves. **Not ready for live
calls: M1-M3 must be fixed before any model allowance is granted.**

## Findings (reviewer's, lightly condensed)

- **M1 (medium) - deleting ledger files resets the cap and the stops.**
  `historical_model_calls.py` builds all ledger state from whichever
  `calls/NNNN` directories exist. Probe: cap `[2,2,0]`, slot 0002 ended
  HTTP_402; `rm -r calls/0002` gave counts `[1,1,0]`, no stop, and the same
  request could be claimed again; `rm -rf <root>` gave `[0,0,0]`. Issue #28's
  `CallLedger` refuses both (binding.json, an initialization anchor in the
  parent directory, an append-only `claims.jsonl`, a `previous_intent_id`
  chain, a directory lock with an alias check). Also: recompute the stop from
  evidence rather than from the self-hashed terminal.
- **M2 (medium) - approval parsing is weaker than #28's.** Plain `json.loads`
  accepts duplicate keys (last wins): an approval body showing `[4,4,0]` with a
  later duplicate `[400,400,0]` was accepted as `[400,400,0]` on the
  GitHub-verified path. An edited comment was accepted too
  (`created_at != updated_at`). Use strict JSON and require an unedited comment.
- **M3 (medium) - "by the approver" means "posted by the wlvh account".** The
  executing agent can post as that account (Issue #28's approvals 5791560371
  and 5811139877 were transcribed by the executor and show login `wlvh`,
  `author_association` OWNER, `performed_via_github_app` null). The approval
  binds no code identity, no request digests or contract and no cost cap.
  Suggested: an owner signature against a pinned key the agent cannot use; the
  receipt id and per-grant request digests restated in the approval and
  enforced at claim; cost caps kept out of band (D-36).
- **L1** - ledger-root separation is lexical: `//`-prefixed, symlinked and
  case-variant spellings of #28's root, and `/tmp` (an ancestor of the
  checkout), were accepted. Compare real paths both ways; reject symlinks at
  lock time.
- **L2** - `_Transport.send` never checks that a counted slot exists; a
  directly constructed transport reached the opener with 0 slots (in-process
  only; #28 has the same gap).
- **L3** - `validate()` never re-derives the request text from the saved
  filing; an edited block with recomputed ids reached the opener (#28 same).
- **L4** - a large token-count mismatch does not stop the channel
  (`CONTEXT_LIMIT` is returned before the reference comparison and is not a
  stop); the reference check is skipped without the tokenizer (#28 same).
- **L5** (pre-existing) - the egress gate matches names only.
- **L6** - the patch's tests overwrite and delete
  `config/issue47_historical_model_calls_v1.json` in the tree they run in.
- **L7** - the GitHub re-check runs whatever `gh` is on PATH with the full
  environment, including `DEEPSEEK_API_KEY`.

Test spot-check: three checks neutralized at once (the send-time owner/marker
re-check, the live ledger-root check, the ledger/allowance binding check) and
the patch's suite still passed - none of them is exercised by a test.

## What the executor does with it

- M1, M2 and L1 describe the SEC path as well as the model path: the SEC ledger
  had the same deletion weakness and the SEC gate the same parsing and root
  checks. They are fixed for SEC before the owner's SEC run
  (`../../acquisition-wiring/README.md`), because that allowance is about to be
  spent. Two of the gate changes are shared and so already apply to model
  approvals: an edited comment is refused, and the budget root is compared as
  a real path. The rest of the model side - strict JSON in
  `historical_model_calls.py`, the ledger port, L2-L7 - goes with the model-call
  application, because changing that module invalidates the sealed offline
  verification and it has to be re-run once, after all of them, not once per fix.
- M3 is a limit of approving through a GitHub comment, not a bug either path
  can fix alone: the owner delegated posting under their account for SEC,
  knowing the agent can post as them. For model calls it goes to the owner as
  a decision (a signed approval) in the application.
- L2-L7 are recorded against the model path's application; none gates the SEC
  run.
