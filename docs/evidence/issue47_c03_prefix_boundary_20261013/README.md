# C03: a broken structured proxy cannot switch routes by changing XML prefix

On actual main99249a45 the historical adapter permits ordinary summary-compensation-table fallback only after the native reader reports no contexts and the raw file lacks the literal `<ix:`. XML prefixes are arbitrary: real native parsing of `alt:nonFraction`, `i:nonNumeric`, a default inline namespace or an XML fact with contextRef but no context returns the same no-context error. The old literal check misses them and calls the SCT resolver. This violates the existing rule that corrupt structured files cannot become successful by switching paths; it is not a new salary definition or source policy.

The historical adapter now reuses the existing bounded `_FactAttributes` namespace/contextRef machinery to recognize actual structured markup. Any fact with contextRef, official2008/2013 inline namespace element or actual bare ix tag preserves the original native error. Namespace declarations alone, comments, scripts or escaped examples are not facts. No person, amount, year or table is interpreted by this guard. Shared ECD/SCT parser, public controller/writer/renderer, first-disclosure selection, actual fiscal dates, identity/currency and multi-person refusals remain unchanged; its existing governance_signals dependency already covers the reused helper.

Five native no-context representations are tested, with the actual native parser determining the failure and the historical adapter forbidden from invoking SCT. The initial harness lacked proxy_inventory and recorded KeyErrors; after fixing that harness the four original representations still genuinely failed by invoking SCT (`before-corrected.log`). A default-namespace case and harmless-markup positives were then added. The first combined command used one nonexistent test module; its ImportError remains in `after.log`. Correct existing modules pass **55 tests /0.292s /zero failure, error or skip** (`after-corrected.log`), including prior wrong-unit/person/source/period checks. No expected business value is relaxed.

Three already saved original proxies are checked only for route eligibility, without recalculating finances or rereading their complete tables: Macy's FY2021 remains genuinely unstructured (0.161284s), Marriott FY2021 remains unstructured with its original two-CEO withholding (0.110610s), and Marriott FY2022 remains structured ECD (0.062167s). Exact original proof/hash is verified before and after; see `actual-source-eligibility.json`. Their earlier138/78-second SCT processing and original table readings are reused, not repeated or relabelled.

Independent ordinary company reads preserve Macy's12,290,931USD result/19state files and Marriott FY2021 null/two-CEO result/18state files, taking0.347845s and0.181340s. The third harness expected one row, but that existing Marriott task already has six annual rows/checks: reading completed without mutation, then its row-count assumption failed. Saved output is `old-read-2.json`; no reading failure is claimed. Only its corrected target-year assertion is rerun in a new read directory:0.359087s, all92state files remain identical, six rows retained, FY2022 keeps18,686,271USD/full719ccfd2ID. All three old read views and the corrected receipt are committed. These are saved-record compatibility checks, not fresh financial processing under changed configuration.

The source selection remains the original first-report convention, and a damaged structured source still cannot become a table success. New SEC/provider/model calls are0; raw originals, request ledger, answers, Run/Result and failure histories are unchanged. No ordinary long computation, five-year matrix, new company, model method trial, runner or review package is introduced. The change is isolated from PR230/232 and public PartIII work. Author does not Ready/merge/adopt/deploy/activate.

Run local counterexamples with project dependencies:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py \
  tests.vnext.test_historical_compensation_case tests.vnext.test_proxy_compensation_source \
  tests.vnext.test_organization_name_core tests.vnext.test_history_company_dispatch
```

Existing company CI already watches `tests/vnext/test_historical_compensation_case.py` and directly executes it. New-head CI and receiver delta review are distinct from the local result. The1950-position goal, full C03 source gaps and first-proxy amendments remain incomplete.
