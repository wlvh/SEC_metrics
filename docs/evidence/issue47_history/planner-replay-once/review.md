# Independent review of the first version (fresh-context agent, same model family, not a human)

Scope: the working-tree diff of `scripts/vnext/normal_history_plan.py` and
`scripts/vnext/historical_source_acquisition.py` before the fixes, the test
module, and this folder. No repository edits, commits, pushes, GitHub posts or
network requests; scratch under the session scratchpad. Verdict:
**PASS_WITH_FINDINGS**.

## What it ran

- The memo-mode `declared_frame` on the root restored at 288 captures, one
  replay each: Macy's `sha256:98c6ac2f...` in 100 s, Ford `sha256:8cbcd21f...`
  in 137 s - the same hashes as the first `measure.py` run's memo frames. The
  root was read only (`find -newer` showed no writes).
- A minimal acquisition root (baseline registry and log plus two recorded
  captures appended by the unchanged `SecHttpClient`, sealed as an
  `ORDINARY_SEC_ACQUISITION_CHECKPOINT` the frozen `_validate_checkpoint`
  accepts) for the divergence probes below.
- The test module unchanged plus two probe cases: all passed.
- `_replay_state` on the 288-capture root: 0.12-0.19 s a call (1,831 evidence
  files).

## Findings

**M1 (medium). The real-root equivalence evidence was contaminated, and as
recorded it said the frames differ.** `measure.py` recorded Macy's once
`98c6ac2f...` against frozen `4124293b...` (57 replays, 1,961 s) and Ford once
`8cbcd21f...` against frozen `44a91998...` (65 replays, 2,181 s). The injection
run rewrote `normal_history_plan.py` in place in the shared checkout during the
measurement, and the planner hashes its own file when a plan ends
(`module_sha256`, which feeds `plan_id`). Replacing only the plan's
`module_sha256` in a fresh memo frame with the hash of an injected planner
variant reproduced both frozen hashes exactly: Macy's with
`THE_KEY_IS_SET_BEFORE_THE_REPLAY` (on disk about 20:51:10-20:53:12) gives
`4124293b...`, Ford with `THE_FROZEN_REPLAY_IS_NOT_PUT_BACK_ON_FAILURE` (about
20:53:12-20:55:13) gives `44a91998...`. Every other byte of the frozen frames
equals the memo frames. Fix: rerun only while the checkout is quiescent, hash
the code files before and after and refuse if they moved, store a field-level
diff, run injections where nothing else imports.

**M2 (medium). The memo lived in a file the live acquisition's receipt did not
pin.** `REQUIRED_WIRING_EVIDENCE` did not include `normal_history_plan.py`, and
the live path pins code only through `verify_offline_wiring`; it never checks
the Requirement closure at run time. A weakened memo would run live unnoticed.
Impact: weaker saved-source verification only; it cannot admit undeclared URLs.
Fix: add the planner to the receipt, or move the memo to a pinned module.

**L1 (low). The key missed state the frozen replay checks.** Verifying proof 2
inside a block, changing something, verifying again inside and then outside:

| Change | Key changed | Memo in block | Frozen replay |
|---|---|---|---|
| Second hard link to capture 1's body, outside `evidence/` | no | accepted | refused (`st_nlink != 1`) |
| Same-size rewrite of capture 1's body, mtime put back | no | accepted | refused |
| `data_root/config` replaced by a symlink to an identical copy | no | accepted | refused (`SourceError`) |
| Empty directory named `<doc>.<64 hex>.headers.json` beside capture 1 | no | accepted | refused (iterated as a sidecar) |
| Control: ordinary rewrite that moves mtime | yes | refused | refused |

The verified proof's own `_proof` check still runs, so the exposure is other
captures' files changed by a non-cooperating writer during one block;
acceptable under the flock and append-only attempts, but the README overstated
it. Hardening suggested: link count, change time and device in the
fingerprint; directories fingerprinted; the registry read through
`resolve_repository_file`; the key recomputed after the replay and the answer
stored only if unchanged. Opposite direction (benign): a symlinked
`requests_log_manifest.json` makes the key raise where the frozen code accepts.

**L2 (low). Test gaps.** The registry and code-manifest components could be
removed with every case still passing (and a registry byte change inside a
block was then accepted where the frozen code refused); the fingerprint's one
case changed the checked proof's own file, where the per-proof check refuses
regardless; the frame-equality case cannot detect staleness.

**L3 (low). Not thread-safe**: the attribute swap is process-global and the
memo unlocked. Nothing is threaded today; document it or guard it.

## Answers to the questions put

1. The memo could make a check succeed that the frozen code refused only
   through the misses in L1. Everything else the replay reads is keyed; the
   journal and the imported checkpoint are read by the verifier outside the
   memo and only select the checkpoint, which is keyed by content. The replay
   has no side effects.
2. The stat fingerprint is acceptable for cooperating writers under the ledger
   lock; it missed link count, rewrites keeping size, mtime and inode,
   directory entries, symlinked ancestors under `config/`, and the device.
3. `try/finally` restores the attribute on every exit; nesting keeps the outer
   memo; no module binds `_validate_checkpoint` by name; the direct
   `validate_acquisition_checkpoint` calls (registration, export, restore)
   bypass the memo, which costs time only. Nits: the assignment sat before
   `try`; a mocked `_validate_checkpoint` has a truthy `replayed_once`.
4. No live-path guarantee weakened beyond the above: registration still calls
   the frozen validator once, outside the block; the gate checks are
   unchanged; a divergence can only suppress a refusal, never admit an
   undeclared URL.
5. Equivalence is tested for spurious raises, not for stale answers; at real
   scale the only evidence was the contaminated output, which once
   decontaminated shows identical frames for Ford and Macy's.
