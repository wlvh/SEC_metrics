# B0 shared interface baseline

This is PR-B implementation, not production semantic freeze, a cycle, Stage-A,
live authority, a benchmark acceptance receipt or current qualification credit.

## Interfaces committed before source-specific work

1. `source_scope.build_source_scope_manifest` / `validate_source_scope_manifest`
   / `load_source_scope_manifest`: separate required-generation record with
   source SHA/full asset/task/Requirement identity, one/two original-order
   windows, target/reference, synthetic Candidate/native Evidence, deterministic
   estimate, full table audit census, out-of-window dispositions and navigation/
   layout proof. A separately supplied fixture-authority content ID prevents
   self-rebound deletion/addition/reorder from changing an approved scope.
2. `scoped_reader.prepare_scoped_reader_request`: immutable request bytes and
   a separate request subtype; only the certified compact tables are sent.
   `validate_scoped_reader_response` and `replay_scoped_offline_attempt` bind
   the same scope/request/task to a native Candidate and native Evidence check.
   Full local Evidence payload and actual scoped outbound are distinct objects.
   Synthetic reference answers are never packed. All four non-positive classes
   fail before request preparation. No network implementation is present.
3. `OfflineExecutionSession`: exact path/hash/size file bindings; one source,
   one DerivedAsset and one Requirement construction; immutable bytes across
   the child seam, terminal failure/UNKNOWN stops later children, and one final
   callback receiving disk locators rather than cached inputs. The B0 counters
   measure these boundaries. The performance track must additionally instrument
   internal canonicalization, semantic hashes and prior-Run work on real inputs.

The complete local DerivedAsset is not a filtered asset and never gets renumbered.
The legacy Reader manifest/payload, native Evidence implementation, canonical
semantics, historical runtime paths and retained V1 engine are unchanged.

## Actual B0 validation

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_source_scope tests.vnext.test_scoped_reader tests.vnext.test_offline_execution_session`

Result: rc 0, 10 tests PASS, 0.436 seconds. Tests use a complete three-table
synthetic source and the actual A03 catalog task/Reader/Evidence path. They cover
native Evidence PASS, original coordinates, pinned-ID rebind negatives,
delete/add/reorder/source/task/asset drift, invalid windows, B06/B13 exclusion,
request/attempt tamper, all zero-call classes, six children with one build,
one independent disk replay, UNKNOWN stop and exact file hashes.

The first run failed because a pending R5 Decision intentionally has no choice;
the policy selector was corrected to select only APPROVED policy records. The
pending Decision was not given R4 credit or modified.

The expanded fast suite passes 23/23 entries in 8.049 seconds; the original
20 entries and 30-second cap are unchanged. Provider call-graph and semantic
scans pass. No A/B/C or historical publication/source evidence path changed.

## Following tracks, with one integrator

- C: complete strict nested schemas, production file loaders, identity propagation
  and tamper negatives on these seams.
- A: real source inventory, independent navigation, source-specific audited
  windows, native synthetic Evidence, reference/no-anchor/out-of-window closure,
  versioned fixture authority and exact six-metric ReleasePlan evidence.
- B: actual unoptimized baseline with at least six historical FROZEN Runs,
  process-local reuse, comprehensive operation counters, same-input/interpreter
  measurements and >=10x aggregate improvement including independent final replay.

Real-source positives, acquisitions, production-safe full materialization and
the 10x measurement are not inferred from this small interface fixture.
