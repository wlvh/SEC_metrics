# E01 next-item boundary with native lettered subsections

Receiver PR114/6118308893 found Southwest FY2024 failing with EVENT_ITEM_END_HEADING_NOT_UNIQUE:1.01:5.02. Main302074f4's selected annual consumer reproduces it on saved primary0001193125-24-242286/d899498d8k.htm (SHA2ce01e9c). The first5.02 caption and5.02(b)/5.02(d) are consecutive parts of one section. The reader groups consecutive own-item headings, but its end check counts raw headings, creating an internal layout inconsistency. `source-boundary.json` records exact positions and the full selected1.01 span.

The existing historical reader admits a known-caption base heading followed by distinct, consecutive lettered parts as one end section. Repeated bases/letters, a different intervening item, extra body text before the first part, hidden/linked captions or headings and parts crossing signatures remain ambiguous. Single next headings, own-item uniqueness, signatures, visibility, header/document consistency and the separate combined-body caption policy keep their behavior. Endpoint recognition adds the standard5.02 caption only. No source class, candidate code, model method, second parser/controller or business definition is added. The public current E01 port remains separately owned and unchanged.

Eleven short layout/source methods are added to the already-required historical company test module, so the existing company workflow's E01 step actually loads them. Final `required-event.log`:64tests/.131s,zero errors/failures/skips. The prior62-check and initial36-check logs retain their own versions. Constructed9.01 subsections demonstrate the generic branch; saved Southwest metadata has only one1.01+5.02 example, so no second real sample is claimed. No runner, extra CI platform or relaxed assertion.

Real new empty Southwest FY2024 state: same company CLI source preparation→request→withheld record→CSV12.401s; correct2024Jan1..Dec31/CIK92380, Result29806686. Full6candidate request34507016 is stored in `saved-request.json`; the1.01 span2201..6499/textSHAd60068b8 is complete. No matching semantic response exists, so value remainsnull/E01_CONTENT_RESPONSE_NOT_AVAILABLE_FOR_REQUEST, not a partial or inferred count. Immediate source/candidate/request/both-calculator/network-forbidden repeat.804s computes0/creates0,seven resultfiles remain unchanged; separate-process results.407s preserves17statefiles and result/period/status/evidence. Timings include subprocess startup. Source registry/ledger/manifest hashes remain unchanged. `actual-company.json` supplies commands and compact results; full unchanged context/evidence remains in the real saved CSV/assessments.

The company execution preceded two additional caption-visibility/signature guard controls. Final code then reconstructs all6 items from the saved48 original claims/80 source records into a request byte-equivalent as a JSON object to the saved one (`final-request-replay.json`), with the same request/source identity and texts. No second company processing or model execution was used to obtain that evidence. Final source span replay also agrees. This differentiates the exact executed working version from the final source check; it does not rename an earlier run.

Reproduce with restored read-only source-inputs and a new external output directory:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
 docs/evidence/issue47_e01_subsections_20261012/verify_company.py \
 --source-root SOURCE_INPUTS --output-root NEW_EXTERNAL_DIRECTORY
```

The two other receiver failures remain separate. PfizerFY2023 still rejects EVENT_ITEM_HEADED_BUT_NOT_LISTED:0001193125-23-294930:2.01: header2.02 and visible document2.01 conflict. SalesforceFY2021 lacks exact primaryhttps://www.sec.gov/Archives/edgar/data/1108524/000110852420000008/crm-20200225.htm. The restored source root/request ledger and committed1.584MB export inventory contain no such original; no GET is attempted. `negative-sources.json` retains the precise failures. They are not this layout cause.

The real company test executes uncommitted main302 code plus the two-file repair. Main later2741821e only adds PR186's two unchanged decision JSON files; this branch receives it without any runtime change or financial rerun. The final64 controls/request reconstruction run on that source composition. An evidence packaging command used a nonexistent CSV key and was corrected to the actual context_or_dimension field without changing or rerunning production. Original full summary and source files remain.

Main's50-grid survey and unchanged zero years are reused. This repairs complete source preparation and ordinary save/repeat/read behavior, not full content-confirmed counting, online source completion, all five years or formal acceptance. Original35model calls/responses/failures/Runs and SEC1772 attribution remain; added SEC/provider/paid0/0/0. Author does not Ready/merge/adopt/deploy/switchactive.
