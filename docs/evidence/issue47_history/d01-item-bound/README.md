# D01: the item bound, raised through the revision mechanism

D01 reproduces every emphasized heading of the complete Item 1A, never a
subset, and its frozen Spec (`catalog/r6/D01_risk_factor_headings.md`) allows
at most 64. Enphase's FY2021 annual report has 68, so the frozen route refused
it by name (`DETERMINISTIC_TEXT_HEADINGS_EXCEED_BOUND`) and the position had no
result at all, though its 12,530 rendered characters fit the character bound.

The pinned route now compiles `catalog/r6/D01_risk_factor_headings_v2.md`,
registered in `historical_spec_revision.REVISED_TEXT_SPECS`, which proves the
successor is the ordinary Spec with only `max_items` raised - to 192, the
ceiling the same mechanism already proves D02 and C02 against. Runs frozen
under the old Spec keep declaring it.

## Measured

`measured.json`, from `measure_d01_bound.py` on the data root restored from
the branch's export at 288 SEC calls, with the route before the revision: 50
positions, 43 reached the heading scan with 26 to 68 headings, and Enphase
FY2021 is the only one over 64 (Enphase's other four years have 60 to 62).
Five JPMorgan originals are not saved, and Macy's FY2022 and FY2021 stopped
before the scan on their fiscal-year label (`../fiscal-label-forms/`). The
same script under the revised route (`measured-revised.json`, the tree of
`fbded78a`): Enphase FY2021's 68 headings are selected, its other years
unchanged, and with the fiscal-label repair Macy's FY2022 and FY2021 reach the
scan with 35 and 39. All 45 positions whose original is saved now have 26 to
68 headings and a candidate.

## Verification

- `tests/vnext/test_historical_risk_headings.py`,
  `test_the_pinned_route_s_spec_is_the_ordinary_one_with_only_the_bound_raised`.
- `injections.py`: 3 injections (the route keeps the frozen Spec; the revision
  is not registered; the successor moves another field), each caught by that
  case (`injections.json`, run in a clone of the branch holding the same files).

Zero SEC or provider calls.
