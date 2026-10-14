# D03 complete offline set: explicit registered source root

The existing complete offline response-set interface could not name the external
registered data root used by current request preparation. It rebuilt from the
code root and omitted the external-replay marker. Four small routing tests first
failed (`before.log`); no before-fix whole-material run is claimed.

The existing APIs now accept optional `source_root`; `repo_root` remains the
processing-code root. Omitting the new argument retains the old in-code source
default. Marked inputs retain `ordinary_registered=True`; a nonboolean marker,
changed source, altered partition, missing/extra response or changed raw file
still fails. Anchored semantic checks receive the same source root. This does
not change prompts, category meaning, transport, budgets or model execution.

Creator module digest is still stored, but current reading no longer requires
its equality to today's code. This implements trusted-internal-20261006, not an
unsafe mode: current source, request census, response bytes, complete rows and
unresolved counts are still reconstructed. The old packet and its creator are
not rewritten. All recorded execution-credit fields remain false/zero.

## Executed controls

Product `1b55184f1eb1ecc90dc071d04b43ecd33bf8300d`, based on actual main17569516.
Tests ran on the same source worktree immediately before the product commit;
the later evidence commit is not a tested program SHA.

```sh
PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest \
  tests.vnext.test_d03_recorded_source_root \
  tests.vnext.test_d03_source_root_seam \
  tests.vnext.test_d03_raw_navigation \
  tests.test_foundation_ci tests.test_selector_registry -v
```

33 controls/0.424s, zero skips/failures. They cover explicit/legacy roots, marker
validation, anchored-validator routing, old creator metadata, unresolved/raw
preservation, changed source/bytes, incomplete inputs and interrupted final
index write. A partial write has no complete packet and cannot grant credit;
automatic recovery of that partial packet is not implemented by this patch.
Routing/source-builder and semantic replies are substitutes in the small tests,
not whole-source proof. The new module is declared once in the existing fast
registry; no workflow, runner body or timeout is changed.

## Actual source seam, isolated recorded replies

Original source root:
`/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs`.
Harness and retained packet:
`/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/d03-recorded-root-20261014`.
It uses real `prepare_d03_replay_only_requests`, source reconstruction,
response parsing, file saving and re-reading. Only the replies are deliberately
constructed: every required reference is `UNRESOLVED`, and every unit carries
`ISOLATED_RECORDED_CONTROL_NOT_BUSINESS_ACCEPTANCE`. No model made them.
Sockets/DNS and ledger claims are forbidden; original ledger metadata remains.

Actual Enphase source: eight groups,29 units,zero anchor groups. Preparation
16.115s; recording9.540s; same-process disk replay9.571s. All eight groups remain
unresolved; all8,420 raw response bytes match. This positive does not exercise
the anchor branch; that new root propagation has only the small control above.

A new Python3.12 process under clean product1b55184f re-read the actual packet
in9.977s. Creator digest differs from the current module because its docstrings
changed after recording; the original digest/packet ID stayed intact. Current
source and all eight replies were reconstructed, ten packet files remained
unchanged, unresolved8/calls0/native-result-false. This is actual older-creator
reading, not rewriting a real packet to match today's code.

Usage of the existing module, not a new CLI/platform:

```python
recorded = record_offline_set(
    output_root=new_packet, source=prepared_source,
    responses_by_original_id=raw_replies, source_root=saved_sources)
checked = replay_offline_set(
    packet_root=new_packet, expected_packet_id=recorded['packet_id'],
    source_root=saved_sources)
```

Raw source/replies remain in the private packet. `material.json` and
`independent.json` contain the compact actual results. This is a working
development persistence seam, not semantic model accuracy, DeepSeek acceptance,
Candidate/Evidence/Run/company output or a no-investigation conclusion. The
native/complete-interpretation consumers still need their own explicit source
root integration; those unchanged modules are not claimed fixed. No new
SEC/provider/paid calls, allowance, historical retry or production authority.
