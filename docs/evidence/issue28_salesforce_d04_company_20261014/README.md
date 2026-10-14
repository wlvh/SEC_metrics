# Salesforce FY2026 D04 through the current company entry

The ordinary `run`/`results` path can consume the existing five real D04 answers,
save the complete company conclusion, reuse it without reconstruction, and read
CSV/evidence in an independent process. This is another current company export
of an existing native candidate, not a new model execution or an increase from
the ten existing D04 candidates.

Executed code: local `e089d73eabbd856f6d81f0cf61ce9d6cf1af577a`, public
`5c65dbe8123446adaf9b096319bde255e7ae59ff`, identical tree
`e3f782e236ce11e5831bcb0efcb01efc96cebfe9`. Its business code is the actual main
`17569516a8be63002f0a6336041421ac14d33459`; the only additional code-tree change
is the fast CI deadline/comment. The later evidence commit is not the tested
program version. Python 3.12.10 used the already installed tokenizers 0.22.2.

## Actual source, calls and result

- Company Salesforce, CIK 1108524, accession `0001108524-26-000060`.
- Actual period **2025-02-01 through 2026-01-31**, issuer fiscal label **2026**.
  The original DEI/Company Facts label remains in source binding.
- Original successful calls **152--156**, 25 source units, source
  `sha256:7ba5e8d3406fe94d10249e8936f05086221fa831dda5c0b8450fd72576284cd2`.
  Current source equivalence, original requests/responses/wire, full partition
  and existing native assessment gates run before the result writer. No old
  answer is relabelled as a new execution.
- Result `sha256:04d871d8e70b59a77db1b2aa305d21c2588c2600be542bb87920b27735f55207`
  matches the original native result in
  `native-candidate-results-20260922/salesforce/summary.json` and the original
  Run records. Business status remains `WITHHELD/null`, reason
  `D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE`; public format is `TEXT_QUAL`.
- This means no doubt disclosure found within the defined saved source scope.
  It does not guarantee financial health, independently prove model completeness
  or authorize production adoption. The saved reader explicitly says
  `SAVED_RECORD_CHECKED_CONTENT_NOT_ACCEPTED`.

## Formal entry and measured checks

Original source/answer archive remains at
`/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13`.
The current saved D04 adapter uses that archive via the existing runtime
configuration; SEC sources and saved model processing inputs remain separate.
An operator must have those original materials and the tokenizer dependency,
not just an old CSV. The test used a fresh state directory, denied sockets,
DNS and `CallLedger.claim`, and ran the real selection, native assessment,
calculation, saving and reading implementations.

```sh
python3 tools/vnext_company.py run --company salesforce \
  --source-root /Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs \
  --metric D04 --work-dir <fresh-state-root> --output-dir <run-output>
python3 tools/vnext_company.py results --company salesforce \
  --state-root <same-state-root> --output-root <new-read-output>
```

The retained harness and actual state are in
`/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/salesforce-d04-company-20261014`.
`run.py` is the existing Ford company harness adapted only to this company;
`worker.py` records terminal exit without retrying. Initial launch used an absent
Python path and failed before any state/request existed; `launch-error.txt`
retains it. The corrected launch resolved the actual interpreter; the worker
finished with exit 0. No successful company calculation was restarted.

| Phase | Seconds | Observed behavior |
| --- | ---: | --- |
| Fresh company processing | 95.137430 | `CANDIDATE_WITHHELD`, actual complete saved result |
| Same input, factory forbidden | 0.070303 | `PREVIOUS_INPUT_WITHHELD`, same result, no calculation/new result |
| Independent `results` process | 0.455286 | Correct period/FY2026, CSV/evidence; no update or calculation |

The ordinary run exits 2 for the stable withheld conclusion; that is not a
numeric success and was not swallowed as an exception. Seven result files,
33,395 bytes, are unchanged on repeat; no second result directory is created.
Seventeen saved state files remain byte-identical during independent reading.
The harness compared 100 protected files, including the original call/source
files and ledger/binding records, before/after. This is that explicit set, not a
claim to have rehashed the entire source root or all historical installations.

## Negative controls and evidence limits

`controls.log` records **25 tests, 0 skips, 0 failures**, Python 3.14.7,
0.455 seconds:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.vnext.test_current_d04_company tests.vnext.test_saved_d04_replay -v
```

These are small controls for missing/failed/duplicate groups, stale completeness
flags, unresolved/failed evidence, wrong year, changed raw answer/wire, retained
failure terminals, business input changes and interruption recovery. Their
constructed negative inputs are not additional full Salesforce company replays.
The actual company trace is the positive/repeat/independent-read sequence above.

`summary.json` contains the compact actual timings, result and public row; raw
requests/responses stay in the original private archive. Additions to real
SEC/provider/paid counters are **0/0/0**. Historical success/failure, usage/cost,
original fiscal labels and production authority are unchanged. This evidence
does not establish all-company D04 omission review, B13/D03, complete 390,
online acquisition or final Issue closure.
