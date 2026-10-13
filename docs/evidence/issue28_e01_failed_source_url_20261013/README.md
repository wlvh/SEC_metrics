# E01 source preflight preserves the latest failed dependency

Finite follow-up to actually read receiver [4253637700](https://github.com/wlvh/SEC_metrics/pull/223#discussion_r4253637700) and original [4253633825](https://github.com/wlvh/SEC_metrics/pull/223#discussion_r4253633825). Base is actual received main `99249a4556fa544e31c7bcb5c9146b9d48021a9f`, tree `ea4111f7462370b89c5e52c6e0ad9194e12b0a12`, already containing PR218/223, public B06 docs227 and empty-registration228. No reimplementation of those completed deliveries.

## Actual failure and minimal correction

The historical annual reader can encounter a failed Company Facts GET before the outer source plan registers that URL. `saved_source` raises `LATEST_SOURCE_REQUEST_FAILED: <url>`. The preflight retained the original error text and stayed incomplete, but only extracted URLs from `SAVED_SOURCE_MISSING:`; `unresolved_dependency_urls` was empty. The same seam can affect an event document read before registration. This was a missing recovery locator, not a false successful business result.

The exception branch now recognizes both existing source-error prefixes and removes only separator whitespace. For an actual failed GET it reads the existing validated request log and retains the latest matching GET's request ID, timestamp, HTTP status, error and retry ordinal. Failure category is `SOURCE_ACCESS_FAILED`. A previous successful GET or an older failed GET cannot substitute for the actual latest observation. No guessed media, source proof or successful checked row is generated for a source not registered in the plan. An unrelated reader error receives no invented URL. No new source selector, controller, acquisition permission or retry is added.

## Verification scope

`before-controls.log`: three new controls, one failure and one error: the formal E01-only sources command lost the exact failed Company Facts URL. The unrelated-error control already passed. The fixture records real HTTP-boundary responses in a temporary package and then runs the real source discovery/selection/preparation until the failure; source and request-log bytes stay unchanged during preflight. Network and calculation are forbidden.

`after-controls.log`:83 affected controls /3.629s /zero failures/errors/skips. `final-controls.log`:84 /3.572s /zero failures/errors/skips, additionally covering a failed event read before plan registration. This event test uses the existing explicit source-dispatch fixture with a prepared-input stub, but the reader and failed request log are real. It is not a complete historical event-source or M&A acceptance run.

`formal-recorded-source.json` is actual formal CLI output from the constructed Company Facts503 fixture, not a real SEC execution. It remains `SELECTED_SOURCE_DEPENDENCIES_UNRESOLVED`, `complete_known_source_graph=false`, with exact unresolved URL `https://data.sec.gov/api/xbrl/companyfacts/CIK0001048286.json`, the503/error metadata and calls0/0/0. It creates no Result, model answer, metric count or fetch grant. A later404 test confirms the observation is the current failure rather than the older503 or earlier200. Existing missing-source and annual/E01 mixed-route controls remain.

```sh
PYTHONPATH=scripts:. python3 tests/required_unittests.py tests.vnext.test_company_event_source_preflight tests.vnext.test_company_fiscal_range tests.vnext.test_selected_source_requirements tests.vnext.test_historical_e01_company_case
python3 tools/vnext_company.py sources --company marriott_international --source-root /absolute/saved/source-inputs --report-end 2025-12-31 --metric E01
```

The second command reads the supplied real package; its outcome depends on those actual saved sources. No supplied answer or fabricated response is required to reproduce the three small controls. Tests used base992 plus the recorded working-tree changes, not a committed-head claim. No large-source batch is rerun for the exception-branch repair.

This does not make missing event originals available, authorize GET, calculate M&A counts, complete a fiscal window or change the historical owner's core. Public preflight is owned by #28; #47 was notified directly of the finite difference. No SEC/provider/paid calls, ledger or old result changes; no author Ready, merge, adoption or deployment. Receiver verification and exact-head CI remain separate.
