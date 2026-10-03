# Explicit D03 development-review save/read entry

The new `tools/vnext_d03_model_review.py` removes manual assembly of the already-reviewed pending package. It consumes a concrete manifest and actual raw development wires, uses the existing complete-source mapper, and reuses the existing immutable file writer. It does not execute a model, select answers, change old defaults, create provider attempts, grant semantics or connect itself to the normal production update route.

## Actual implementation and verification

Tested base `2ab895d45b5051f415e07c62f87e74179afd086d` plus the recorded uncommitted new CLI/test delta; exact bytes and unchanged mapper hash in [binding-impact.json](binding-impact.json). Old V13/V14 authority lists do not bind these new paths. The pending mapper/Spec and its precise `ccb0c5e6` limited review are reused, not reopened.

Input [input.json](input.json) names the six actual persistent raw request/response paths and external hashes, original source5c4aae9c, and company. These are computing-side development artifacts, not SEC sources or live execution proof. Output root is explicit and must be outside code, the real ledger, and active publication roots; aliases are refused. No output requires personal HOME, writable code, root privileges or unshare. The current actual input data root is still the original checkout; this does not prove OpenShift/package portability.

[exercise.py](exercise.py), [exercise-summary.json](exercise-summary.json): authenticated original Marriott source plus all six original responses save in4.127s; identical repeat3.372s changes no file bytes. A controlled local interruption before the fourth immutable write exposes no final records, then a3.398s resume preserves every already-written byte and yields the same complete package. `records.jsonl` is written last, only after full source/input validation; partial package cannot be read as completed. The underlying writer provides no-overwrite writes and file locks; a conflicting manifest/body refuses, rather than clearing or replacing previous data. This is reuse of existing persistence machinery, not a new workflow platform.

Both normal and resumed outputs retain Candidate `sha256:92dcda707632a0fbf661cd0704661e70ec5b8391bd6519fcb5cb55a3040b0cec` and ReviewUnit `sha256:7d4d085ed67f317e6f2e78a11be1751fd1b60f1cfe4d5096942ebc4154e2e705`, exactly the preceding pending package. `development-input.json` adds provenance outside the unchanged four native records, not a new accepted source or an amended answer.

[cold.py](cold.py) invokes the actual CLI reader in another process with socket/subprocess disabled; [cold-summary.json](cold-summary.json) records4.135s. It independently reauthenticates original sources and reconstructs the six wires, records, complete review context and display.25 classifications/18 unresolved remain PENDING, scope empty/SYSTEM disabled via the unchanged mapper. No company Result/Run/public row/390 or DeepSeek credit exists.

Eleven short tests passed0.177s: four new CLI cases (actual CLI save/read/repeat, partial rejection/exact resume, changed answer/digest/manifest refusal without overwriting, code/real-ledger/alias root refusal), plus seven existing mapper cases. The prior154 selectors' unchanged evidence is reused; no complete155 local suite rerun is claimed. The new selector is appended only, runner functions unchanged. Exact new CLI patch `f5db8911a47ef1b6e08551f7a2946ec5734e68ee` received [PASS_LIMITED_DELTA](independent-review/conclusion.md):43 conservative tools/two messages/6.65min. Reviewer personally ran four tests, actual source cold read4.155s and46 meaningful probes, including every write interruption and conflicting/aliased package cases. Parent tests are not that review.

**Read limitation:** `development-input.json` is a locator-provenance attachment outside the original native identity. The reader does not authenticate that attachment; deleting/changing it leaves the verified source/wire/native identities unchanged. The cold-read conclusion covers original source, actual request/response, metadata, records/context/display and external identities, not all17 saved files or historical locator paths. Using the attachment as a later authority would require its own digest check. No such authority is granted here.

## Usage and remaining boundary

```
PYTHONPATH=scripts:tools python tools/vnext_d03_model_review.py save \
  --manifest /absolute/development-input.json --data-root /absolute/source-root \
  --output-root /absolute/development-pending-root
PYTHONPATH=scripts:tools python tools/vnext_d03_model_review.py read \
  --data-root /absolute/source-root --output-root /absolute/development-pending-root \
  --company marriott_international --candidate-hash sha256:EXTERNAL_CANDIDATE \
  --review-unit-hash sha256:EXTERNAL_REVIEW_UNIT
```

The reader requires external identities, not only identities stated inside the package. This new entry reduces development-side file assembly; it is not evidence that the complete normal new-filing update route is automated or that human semantic approval can be skipped. Positive/negative original business validation, final actual factory resource mapping, live purpose permission, wiring and eventual Review/Result/Run remain separate gates.

New business calls0/0/0. Original ledger143/143/52, remaining97/97/28, batch21/66. No old pending bytes, Run/Result, active, peer working tree/ledger/snapshot or original call history was modified. Whole390 and production readiness remain incomplete.
