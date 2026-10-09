# Historical B01 reported revenue scope — 2026-10-10

Base main `f6ef7886d6630f7675c25cd42e306c373ab05769`; this candidate consumes public PR118 `b962b6c9a69d3d7fd85541f6b92346a7b651c093` and PR119 `83eaa4da5d18c7accc0c093b1ef4db5f5158da16` plus repairs `62243bfdce042a79508f242df65cc897fcfaf035` and `2a6d2fbd64778139e4d96a9a00b409068f0ad8e1`. These public candidates are not main or business acceptance. The historical change stays in the existing selected-statement adapter and tests; no second controller, parser, renderer or caller.

## Actual company entry

The selected original primary/XML now establish any demonstrated component/total scope before existing Calculator selection. Original facts and the frozen Spec priority stay unchanged. Exact selected-filing CompanyFacts must contain the reported total; later filings cannot substitute it. Existing selected original amount and visible short-period checks remain. Source identity uses original DEI fiscal label; output retains resolved issuer fiscal label with unchanged actual dates. No demonstrated split preserves prior behavior and grants no additional complete-scope proof.

`actual-company.json` records an actual saved-source Pfizer FY2023 B01 correction through the company CLI, forbidden-factory repeat and a new-process default results reader. Final native-row affected refresh 10.140s, repeat 0.965s, read 0.575s, exits 0. Initial pre-review combination 10.464/0.999/0.599s is preserved in `initial-actual-company.json`. CSV contains 58,496,000,000 USD / 2023-01-01…2023-12-31 / Result `128c170a19b5505f3ce22e837aaea836159b4652e334aa4b5bdf298e007786da`. The previous component Result `a6e31052…` and all other period/metric results remain; exact defect hold from PR118 does not hold the corrected ID. No other year was recalculated. All twenty Pfizer coordinates are readable, including existing growth holds; this does not accept all twenty values.

Full scope, original rows, locators and source evidence persist in the existing input binding/assessment. Daily selection fields carry scope ID/status/proof flag and observation/source-role summaries. Display summaries do not remove underlying evidence. The final refresh consumes the consolidated-title/local-scope repair, actual composite_scope dependency and bounded display. It processes only this affected coordinate. Repeat then calls neither preparation factory nor Calculator. 178 existing files (all but this coordinate’s two current metadata files) are preserved; 187 result/pointer/check files remain after the final refresh, repeat and read. Each actual processing revision added seven ordinary saved files; the subsequent unchanged repeat and reader added none. Native Result identity remains 128c, but the ordinary saved version is new because processing configuration changed. Earlier 10.836/1.024/.613s title-repair run remains in `title-repair-actual-company.json`.

## Reproduce using saved sources

Use this branch with the two public candidate commits already included. Create a new source directory using the committed PR52 SEC export (no network):

```bash
python tools/vnext_historical_sec.py restore --export /path/to/PR52/evidence/issue47_acquired --out /new/source-directory
```

Read the restore result's actual `source-inputs` root. A fresh review state avoids changing the original task. The following uses that root:

```bash
python tools/vnext_company.py run --company pfizer --period fiscal-years --fiscal-year-start 2023 --fiscal-year-end 2023 --metric B01 --source-root SOURCE_INPUTS --work-dir NEW_STATE --output-dir NEW_OUTPUT
python tools/vnext_company.py results --company pfizer --state-root NEW_STATE --output-root NEW_READER
```

The committed source-only Pfizer reference at `0dc5de75:docs/evidence/issue47_growth_reference_20261010/` binds accession `0000078003-24-000039`, primary SHA `e8439987e90aeb5170db8daf9cddf9c2c9e2a4567c87ef8e4bc6722a83c905c0`, table000113 and original XML. Product 50,914m plus Alliance 7,582m equals reported Total 58,496m. These are source evidence, not manual Calculator operands.

## Tests and pending receiving

`directed-tests.log`: 74 tests, 0.345s, zero skips after the public scope repair. `workflow-directed.log` is the actual existing workflow command: 64 tests, 0.218s, zero skips. Actual historical adapter/Calculator controls include admission before selection, later-filing refusal, original/resolved date agreement, full assessment retention and bounded display; shared scope tests preserve year/unit/subject/quarter/partial-block and XML assertions. Existing historical dispatch, stable success/withhold, source-change and local failure controls are reused. Constructed controls are not registered financial results.

Initial constructed tests accidentally retained an unrelated standalone revenue fact from the shared fixture and then asserted a nonexistent `status` field. Both failures were saved under work/revenue-scope; the fixture/assertion was repaired, business checks unchanged.

Public limited review found a local/segment/exclusion qualifier counterexample; public 62243bfd corrects it with actual consolidated title/caption/local context and preserves unsplit inputs. The historical consumer has received that correction and passed the affected actual company path. The later 2a6d2fbd fixes the remaining native-row qualifier hole identified by that review; its affected historical check is above. This does not rewrite the retained P2 review into PASS. Public receiving conclusion and remote CI remain separate. Remote company job114031473233/run37992926691 actually executed all five new class tests in the existing step: 64 tests/0.544s/zero skip; complete job log is committed. It does not generalize this split method to all revenue layouts, resolve existing FY2021/23/24 growth comparability holds, online source discovery, amendments or unreceived indicators. No SEC/provider/paid calls, new Run credit, merge, Ready, adoption, deployment or active change.
