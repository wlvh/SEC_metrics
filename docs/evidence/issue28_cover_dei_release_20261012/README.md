# Explicit SEC cover-name release option

The prior FY2021 original used by Marriott FY2022 B02 has official SEC DEI
`2021q4`. The revenue source helper accepted that registrant name, but its
cover-document reader and cover-name binding still used year-only DEI. This
reproduced `TEXT_DOCUMENT_ENTITY_MISMATCH_OR_MISSING` before any calculation.

`reported_revenue_scope(..., dei_release=YEAR_QUARTER_OR_DATE)` now passes an
explicit SEC option through the issuer-header helper, text-document reader
and same-source registrant binding. This option is separate from the existing
FASB `namespace_policy`; defaults remain `YEAR_ONLY`. Nondefault SEC options
are recorded in the new scope proof. Custom namespaces, foreign registrants,
wrong periods, cover/name conflicts and unsupported policy values remain
unusable. No D04 or historical caller is automatically opted into this path.

## Actual execution

Base tested tree: main `2f24282ca9cdefbae07f788b91d88b204c01ed2e` plus the
listed working-tree patch. Code root was
`/Users/lyuhongwang/.codex/worktrees/issue28-cover-dei-release/SEC_metrics`.
Source root was the existing read-only saved material at
`/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs`.
There is no runtime installation or writable source-root change in this
source-helper validation. Exact delivery commits identify the patched tree;
the working-tree tests are not represented as having run at a future SHA.

- `before.log`: six newly introduced tests failed on the unchanged base,
  including the missing SEC option.
- `first-repair.log`: the first code repair exposed an overly strong test
  expectation. A heading-only helper with a foreign entity produces no alias;
  it need not raise from an unused cover branch. The corrected test verifies
  the empty headings and the real text-document reader's entity rejection.
- `targeted.log`: 113 affected small controls passed in 1.096s, no skip.
- `final-targeted.log`: the actual required-unittest runner passed 101
  controls in 1.014s, zero errors, failures or skips. This includes D04 saved
  replay/provenance and default source behavior; it is not full ten-company
  material or model acceptance.
- `original.json` and `original.log`: network-disabled reads of the actual
  FY2021 and FY2022 originals. The FY2021 original SHA256 is
  `54effe78b84966cd0793dcb23b8db4ad30b0614ea3d42074f3ece89adebe8bf5`.
  Its explicit quarter-release cover proof now binds the real charter caption
  and current registered DEI name (1.500153s). FY2022's default-year proof is
  identical to the base helper's output (1.648378s). The first driver run
  completed those assertions but could not serialize binary timing floats
  through the existing exact-JSON helper; the original failed log is retained
  as `original-first-output-error.log`, and timing strings fixed the driver.

Reproduce the small controls with:

```sh
PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py \
  tests.vnext.test_cover_dei_release tests.vnext.test_statement_group_totals \
  tests.vnext.test_single_revenue_line tests.vnext.test_selected_reported_revenue_v2 \
  tests.vnext.test_text_coverage tests.vnext.test_xbrl_namespace_policy \
  tests.vnext.test_d04_processing_scope tests.vnext.test_saved_d04_replay \
  tests.vnext.test_d04_provenance_reuse
```

Reproduce the saved-source probe with `PYTHONPATH=scripts:. python3
docs/evidence/issue28_cover_dei_release_20261012/verify_original.py
--source-root <existing-saved-source-root> --output <isolated-json>
--baseline 2f24282ca9cdefbae07f788b91d88b204c01ed2e`.

## Consumer and acceptance boundary

This is a public source-interface repair. #47 owns explicit historical
consumer selection and processing identity, including `dei_release`, the
corresponding annual-period reader and already-declared source dependencies.
The prior USD caption/EPS change in PR199 is separate. Complete Marriott
FY2022 B02 needs both the applicable source repairs and a normal company
recovery, forbidden-calculation repeat and independent CSV read. None of
those company results is created or credited by this cover proof. Existing
failures, old results, original responses and ledger entries are unchanged.

New SEC/provider/paid requests: **0/0/0**. No model response is generated or
relabelled.

## Actual main combination

During delivery, main advanced normally to
`8030f851e467c456bb9c9267280a45e2c515d05e` (receiver merged PR197). This
branch merged that main without conflicts, preserving its historical consumer
and tests. Tested combination commit:
`c7dc7d4cebd2fb6a5f19e0ae1a2d4ebe65f279b0`; only its generated evidence log
was then untracked. `main-combination.log` records 154 required small controls
in 1.241s, zero failures/errors/skips, including the actual new historical
statement caller. Production code is unchanged in the following evidence
commit. The cover-original proof's source inputs and changed functions did
not change on that merge, so it is reused without another full material run.
Remote CI remains a separate check of the published head.
