# Ordinary update reuse: exclude an unused legacy session

Base main9493ed0e. The current source verifier calls saved_source_checks;
RecordedSourceSession appears only in the old register_recorded_session path.
The inherited policy still lists ordinary_source_session.py, so an unrelated
platform edit forces the ordinary producer to run again. Peer read-only
processing-differences.json identifies exactly that one changed digest; the
FY2025 Paramount C01 result has no explicitly declared session dependency.
No peer state or stored configuration was edited.

The small fix removes that one inherited file from _configuration. Consumers
can still declare it through processing_files, which is hashed separately.
Actual normal_annual_input, saved_source_checks, calculator and declared
consumer dependencies remain; no all-repository dependency scanner or old
permission system was added. Existing records are not rewritten. Installing
this code changes the processing configuration once; it does not relabel old
configuration bytes as current or guarantee reuse across that installation.

before.log preserves the pre-fix failure: four metric configuration subcases
and a real saved-source company C01 repeat wrongly enter calculation when the
unused session hash changes. after.log:39 tests pass,15.996s,zero skips.
Normal annual-selection change still recalculates once, then reuses; explicit
session dependencies do the same; stable withheld/current/historical and
interruption regressions remain passing.

saved-entry-timing.log adds same-scenario measurements: actual Marriott C01
FY2025=3,count,2025-01-01 through2025-12-31; first1.906464s, repeat0.332565s,
independent read0.002599s. Repeat uses an exception-raising calculation factory
and preserves all six result files plus the success pointer. The class setup
reads genuine saved source bodies/headers and uses actual calculation and
ordinary records; only the unrelated digest is simulated. No SEC/model calls,
new business result credit or full historical validation. Tests were run on
base9493ed0e plus the stated three uncommitted code/test files; the committed
product SHA is recorded below/through Git, not asserted to have been the dirty
tree's tested HEAD. Original peer result remains unchanged and its receiving
consumer check is separate.

Limited independent review of0ff6fc9e passes:19 small tests after commit,
24 supported metric configurations compared to the base, and only the unused
session entry differs. Real saved-source integration remains author evidence,
not an independent rerun.30 tools/3 messages; conclusion and logs retained.
