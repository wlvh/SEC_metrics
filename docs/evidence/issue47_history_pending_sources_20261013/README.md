# Historical source continuation: exact pending requests are not visible

Actual main385 public `sources --fiscal-year-start 2024 --fiscal-year-end 2025 --metric B01` is exercised on the existing small source fixture. Its SEC replies and ledger are explicitly constructed inside an isolated temporary test directory; the production company/source/fiscal-label readers are used. No real HTTP, metric factory or calculation is called.

Three distinct source conditions all return exit2 / FISCAL_RANGE_UNRESOLVED and the generic COMPANY_FISCAL_RANGE_LABEL_SOURCE_MISSING, category SOURCE_OR_READER_ERROR. The exact URL is absent from the public JSON:

- A latest recorded503 after a previous saved FY2024 original: should preserve that failed outcome and exact source URL, not reuse the older success.
- Missing FY2024 primary: should preserve SOURCE_UNAVAILABLE and the primary URL.
- Missing CompanyFacts: should identify the CompanyFacts dependency rather than suggesting the primary is absent.

`_Requirements.require` has already observed the real URL/status/error, but the public fiscal-label loop replaces it with one generic error. This blocks a precise future same-company acquisition/completion stage from consuming the available dependency observations. It is a program/manifest gap, not permission to fetch, a business non-applicability or a proved zero. The existing unresolved-year and ambiguity protections should remain.

#28 owns the finite public-loop repair; it will expose known requests and their original errors. Historical side does not create another label collector, selector, acquisition client or ledger. `probe.py` and its three outputs are sufficient to reproduce; run from code root with `PYTHONPATH=scripts:tools:. python3 -B docs/evidence/issue47_history_pending_sources_20261013/probe.py`. It writes only to `work/history-source-continuation` and isolated temporary fixtures. The noncalendar positive is reused from the already executed Salesforce package/source consumer13fb: issuer FY2026, raw DEI2025, actual2025-02-01–2026-01-31. No complete-original or five-year replay is performed merely to supply the positive.

Initial probe attempted an absent `get_bytes` convenience method and failed before adding a test response. The final probe uses the existing fixture's recorded response method; no production source was edited. Each formal sources call preserves its fixture tree bytes. New real SEC/provider/paid **0/0/0**. This evidence is not a standalone source-acquisition feature or full historical source completion; the next public repair must be consumed and verified through the same company entry.
