# One retained D02 Item 8 response through the public reader

The existing public D04 saved-response route is D04-only. This finite adapter
reads a retained D02 Item 8 call for the complete request supplied by its
consumer. It does not borrow D04 acceptance, call a model, alter a ledger,
create a native Result/Run or claim an empty subreview is a company conclusion.

`scripts/vnext/saved_legal_review.py::read_saved_legal_review(call_root, request)`
reads seven original call members: semantic request, source metadata, provider
body, assistant bytes, HTTP response, wire journal and terminal. Original
terminal file hashes detect accidental mixed/changed files; only these needed
files are compared, without old permission/approval/recursive proof machinery.
The reader checks the exact current request and provider messages, wire IDs,
HTTP success, complete output, matching assistant bytes and token counts.
Then it reuses the current pure H1 quotation/decision contract. No legal
classification rules or model prompts change.

The returned assessment preserves original mode, execution/wire/terminal IDs,
counts and source proofs separately from zero new calls. Missing usage remains
null and `usage_known=false`; unknown cost remains null. It always declares
`complete_company_result=false`, `semantic_correctness_verified=false`,
`current_source_verified=false` and `run_created=false`. Consumers must prepare
and verify current sources, assemble every necessary subreview and retain
undecided/missing groups before creating a full-company result. A RECORDED
fixture is not renamed LIVE.

## Actual retained material

The fixed peer handoff was actually read at
`44ed9a9d9cc9997de4f057c57cb97213632cb7ae`:
`docs/evidence/issue47_d02_saved_consumer_contract_20261013/README.md`,
`ford.json` and `main-source.json`. It distinguishes the original full request
from the quote-only regression projection.

`verify_original_ford.py` reads original Git bcc0c0bc's model-ledger archive
in memory, exports only seven members to an isolated temporary input directory
and removes no existing material. No new archive or ledger is created. Using
original SourceReference/RawBlob metadata and actual saved SEC bytes, the main
D02 source preparation reconstructs Ford FY2025's one-block Item 8 request.
No old metric values are calculation operands; no old answer enters the
source package. Request ID is the original
`sha256:7f0d2be204ae60689397a55ac102ec07f3ad0923c57ab00db59060abd9fe8908`.

Actual preparation took 2.490268 s, then this reader took 0.000484 s. The full
parsed source candidate count is 53, but the saved response concerns only the
one-block Item 8 subrange. All original seven members and five protected
source/registry/log files retain their bytes. Original execution was LIVE,
SUCCEEDED, counts `[1,1,0]`, input 963/output 13 tokens, cost null. The reader
returns zero added Item 8 blocks and no undecided block; it does **not** return
zero litigation, N/A, a new whole-company result or new model success.

The full source's 53-versus-old-45 excerpt/page-header issue is separately
owned by #47. This adapter neither crops them to the old answer nor edits the
business core. General multi-block Item 8 pool preparation, complete D02
aggregation and public company run/repeat/results remain necessary consumer
work; this one-block fixture does not prove them.

## Controls and reproduction

Small fixtures cover a nonempty legal quote, changed company/CIK/period/raw
reference, projection instead of full input, mismatched provider messages or
parallel wire response, changed bytes, complete JSON with `length`, HTTP402,
failed/UNKNOWN/unfinished original, missing mandatory decision, explicit
uncertainty and absent/contradictory usage. Fixtures test mechanics, not the
model's correctness. The existing H1 and documented SDK parser tests are reused.

```sh
PYTHONPATH=scripts:. python3 tests/required_unittests.py \
  tests.vnext.test_saved_legal_review \
  tests.vnext.test_legal_review_contract \
  tests.vnext.test_securegpt_documented_response

PYTHONPATH=scripts:tools:. python3 \
  docs/evidence/issue28_saved_legal_review_20261013/verify_original_ford.py \
  --source-root /absolute/registered-source-inputs \
  --receipt /absolute/new/original-ford.json
```

Actual original receipt records code root/base main731 and working-tree test,
source root, archive hash/member paths and each byte hash, request/document ID,
original execution and zero new calls. The original call/Run/Result and #47's
own count ownership remain intact. Source proof revalidation and complete
company result creation are not hidden inside this read-only function.

The implementation was committed as local 5f2f6b07 before normally receiving
actual main18fa (PR235/234/236 reception). Combined code e27a4ff3 has tree
076aec44d475e9234df9ad4c218038552f13f512. The four processing files and D02
source-preparation module did not change between main731 and main18fa;
original-Ford execution is reused with its actual working-tree provenance.
`received-main-controls.log` records 32 tests in 0.028 s, zero errors,
failures or skips on the committed combined code. Only this log was untracked
during that run; this paragraph is a later documentation addition.
