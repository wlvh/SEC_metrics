# Known but unimplemented historical metric blocks a mixed company command

Actual main99249a45, existing Marriott five-year hotel task, request only FY2024 B10+D02. Both IDs are defined project metrics, but D02 is not yet wired to this saved-source historical entry. `tools.vnext_company.main` calls `company_local._run_saved_history` and raises `LOCAL_HISTORY_SAVED_FAMILY_NOT_IMPLEMENTED` before the shared controller handles B10. Stdout is empty and even B10's existing successful result cannot be reused by this command. This is the current explicit fail-fast contract, not a claim that D02 has an accepted value.

`actual.json` records the actual argument vector, exception, timing0.200974s and unchanged152-state-file hashes. Original correct hotel results remain. Network and entry into the **real** lodging factory are prohibited; no fake producer replaces its source metadata. The initial observation script did not catch this ValueError and stopped before writing its receipt; the corrected observation catches only that expected error and confirms the same authoritative behavior. It does not restart a business operation or hide the exception.

For the original39-metric single-company goal, a known unfinished metric and an invalid/misspelled metric are different conditions. A future integrated entry needs either all requested families implemented or an explicit incomplete-family observation while allowing supported neighbors to continue. Such an observation cannot be a financial zero, structural N/A, accepted Result or finished business position. Unknown/duplicate IDs and malformed invocation may still be rejected before any work. Whether to prioritize that partial-entry behavior or first implement remaining model families belongs to the public CLI/model owner; this reference does not silently alter the current contract.

Public #28 owns company_local/controller/state/source planning and the shared model chain. The historical owner supplies this actual existing task counterexample and subsequent consumer checks; no competing fallback/controller/store/provider or second queue is implemented here. This is a concrete integration gap, not authorization for a D02 request. It is independent of already delivered PartIII236 and hotel230 candidates, whose scopes remain stable.

Recover the source root through the existing PR52 restore, or use an already registered complete root. In a scratch task, the current command is:

```bash
PYTHONPATH=scripts:tools:. python3 tools/vnext_company.py run \
  --company marriott_international --period fiscal-years \
  --fiscal-year-start 2024 --fiscal-year-end 2024 --metric B10 --metric D02 \
  --source-root /your/restored/source-inputs --work-dir /your/existing/hotel-state \
  --output-dir /your/new/mixed-output
```

There is no model/SEC allowance from this repro. Real SEC/provider/model calls0; Source/ledger/oldRun/answer/state bytes unchanged. Full1950 goal remains incomplete; a new readable unsupported row would not by itself close it. No new feature PR, review pack, runner, approval rule, Ready/merge/adoption/deployment/active action.
