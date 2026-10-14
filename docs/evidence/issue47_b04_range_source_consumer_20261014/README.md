# Public B04 source preflight: historical consumer

Consumes actualPR266/6d9c4cd6, same tree as publiclocal37952. No production/controller/planner/runtime/metric change is made. The source-only metrics includeB04; RANGE_CASE_METRIC_IDS remainsB01/B02, and export/online historical capture are not extended. This is a readonly consumer check, not B04 calculation or income correctness.

Actual same-company sources CLI uses existing complete saved originals, with network, actual historical factory and every Calculator forbidden:

- Macy'sFY2023–FY2024/B04:29.487573s/exit0, FISCAL_RANGE_RESOLVED, seven known source requirements and zero pending. ActualFY2023 is2023Jan29–2024Feb3 (53weeks); FY2024 is2024Feb4–2025Feb1. No raw-year or date arithmetic substitutes for issuer labels.
- FordFY2024–FY2025/B01+B04:31.613018s/exit0, nine known source requirements, zero pending, actual annual2024/2025 dates. Mixed selection retains the original income source union; B04 does not removeB01's native inputs.
- Macy'sFY2026/B04:7.507613s/exit2, FISCAL_RANGE_UNRESOLVED/FISCAL_YEAR_MISSING_OR_AMBIGUOUS. The availableFY2025 is not borrowed asFY2026; the missing year is not zero or structuralN/A.

All required original source bodies are hashed against the returned actual proof (exact count and identities in source-body-controls.json). Source registry/GET log/manifest hashes are unchanged, and every output hasfetch_authorized/metric_executed/metric_acceptance_provenFalse. No task state, Result, calculation or new business call is produced. The source-only status cannot replace financial/subject/amendment verification or the remaining full-five-year responsibility.

Copyable commands from the fixed266 program, existing source root and a new output capture:

```sh
PYTHONPATH=scripts:tools:. python3 tools/vnext_company.py sources --company macys \
  --fiscal-year-start 2023 --fiscal-year-end 2024 --metric B04 --source-root /your/restored/source-inputs
PYTHONPATH=scripts:tools:. python3 tools/vnext_company.py sources --company ford_motor_company \
  --fiscal-year-start 2024 --fiscal-year-end 2025 --metric B01 --metric B04 --source-root /your/restored/source-inputs
```

Current/latestB04 already exists separately; this preflight does not activate historical online discovery, fill missing sources or grantGET allowance. Original phase outputs/arguments/timings are retained in summary.json; no source/company first calculation or previous1950/census is replayed. New SEC/provider/model0/0/0; no authorReady/merge/adoption/deploy/active. Progress on #47.
