# Historical D01 explicit namespace receiving

This follow-up responds to PR133 receiver comment6125200359. Main c7a8428b delivered the heading route but its `release_aware(d01_emphasis_results)` view did not adapt the new text_coverage namespace API. Actual FY2021 `dei/2021q4` facts were skipped, producing a misleading `TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING`. Main2f24282c subsequently receives193/195/196; the follow-up is normally combined with that main, without changing their source/core or the company controller.

The existing D01 source/results functions now accept `namespace_policy`, default YEAR_ONLY. Historical D01 passes YEAR_QUARTER_OR_DATE explicitly through candidate construction, evidence reconstruction, reviewed observations and final replay; the historical processing list includes the actual policy module. This route no longer uses a dynamic release_aware view. The no-source-policy default cannot silently consume an alternate namespace option. There is no company/year special case, caller regex, new heading selector, text_coverage change or second saver. Public/current D01 ownership remains separate; the public owner confirmed these two thin business modules are modified by the historical side alone.

Before fix, an actual new Enphase FY2021 company task takes5.172s and fails the entity check (`enphase-before.json`). The short quarter-namespace regression reproduces the same error (`before-test.log`). After fix, that same ordinary task processes7.809s, produces68 complete ordered headings, and uses the existing128-item capacity successor. All68 strings equal the previously read original reference; the new Result ID is distinct and is not artificially changed to the old identity. Factory/candidate/text-Calculator-forbidden repeat0.729s performs zero calculation and creates no result directory. Independent subprocess results/CSV0.327s changes no state. The old failed check remains; reading an old68-heading result was never proof that the previous main could recompute it.

Second actual company sample is Salesforce FY2022: new task processing7.185s,46 headings, actual2021Feb1–2022Jan31, reporter1108524; forbidden repeat0.702s and independent CSV0.317s. These two company results are TEXT_QUAL/text; the first execution harness wrongly expected numeric status OK and failed after Enphase's three completed phases. Actual output was then checked as TEXT_QUAL without replaying those phases. Execution before the final default-guard test was added uses fcc9a4d1; the later addition is test-only, not a production version retro-assignment.

`remaining-source-controls.json` checks the other nine FY2021 selected originals through the same explicit source policy. Their official DEI URI is2021q4; identity, actual period and complete document checks pass. Eight complete D01 source views are proved. Salesforce FY2021 then retains `D01_MULTISPAN_HEADING_UNSUPPORTED`; the fallback in this verification only inspects the shared base document to distinguish the passed identity check from the unsupported heading representation. It does not create a D01 result. The initial batch stopped at that legitimate downstream rejection after five sources; only the four uncompleted sources were resumed. JPM source reading takes54.721s, other readings5–13s; no fifty-position computation is repeated.

Required controls:74 historical/source/capacity/dispatch/state tests0.824s, and55 default/text-result replay controls7.497s, all zero errors/failures/skips. Fake DEI URI, invalid quarter, wrong entity/date, missing sections and scope restrictions still fail; default and no-policy routes retain YEAR_ONLY. Current/module defaults and old native contracts are tested separately from the explicit historical consumer. Full default/current company D01 remains public PR135's responsibility.

Use the already committed saved sources restored from retainedPR52 `evidence/issue47_acquired`, confirm the returned source-inputs root, and run the same company entry with new output. No source acquisition or model call is required:

```sh
python3 tools/vnext_company.py run --company enphase_energy --period fiscal-years \
 --fiscal-year-start 2021 --fiscal-year-end 2021 --metric D01 \
 --source-root SOURCE_INPUTS --work-dir NEW_STATE --output-dir NEW_RUNS
python3 tools/vnext_company.py results --company enphase_energy \
 --state-root NEW_STATE --output-root NEW_READER
PYTHONPATH=scripts:tools:. python3 docs/evidence/issue47_d01_namespace_20261012/verify_source.py \
 --source-root SOURCE_INPUTS --company enphase_energy --fiscal-year 2021 --output NEW_SOURCE_CHECK.json
```

Repeat the identical run: source factory and Calculator should not be called. For the second sample substitute salesforce/FY2022. The small regression runs in the existing required historical module, whose source path is already in the company workflow; no runner is added. Real company phase outputs, CSV row and source-reference identities are in the two after JSON files. Nine other source checks are not nine new saved results or full D01 business acceptance. Amendments, successor entities, multi-span headings, online history sources and complete1950 business remain unfinished.

The receiver's optional suggestion to make every dynamic release_aware call fail after a dependency API changes is not implemented globally here. D01 instead consumes the explicit API directly, removing the faulty view from the touched path. A general call-graph/wrapper redesign would affect unrelated old consumers and is unnecessary to fix this concrete failure. Original sources, failed checks, old results/Run and call ledgers remain; new SEC/provider/paid/model calls0. No author merge/Ready/adoption/deployment/active.
