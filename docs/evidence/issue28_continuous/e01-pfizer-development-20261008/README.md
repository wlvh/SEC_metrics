# Pfizer E01 content development — first blind extraction

Actual saved FY2025 Item8.01 texts: Metsera acquisition completed; two separate note offerings. The parent read each complete candidate item and checked the saved HTML before writing the reference. An independent development context received only the request, prompt and output requirements, with no reference answer. Its original output is retained byte for byte.

The fixed shared contract is [b4b57e7c historical_ma_confirmation.py](https://github.com/wlvh/SEC_metrics/blob/b4b57e7cba3d2f8ea82a22b7510d5aba27bb9b05/scripts/vnext/historical_ma_confirmation.py). `validate_answer` accepted all three entries and exact quotes; decisions match the independently formed reference 3/3. Pure `confirmed_count` returns one confirmed item, **not an E01 MetricResult or accepted annual count**. No correction trial used. Initial harness called a nonexistent function; correcting the name did not alter the request or model response.

Scope: the three candidate own-text classifications in nine already-saved filings. No exhibit interpretation, completeness of all announcements, dedup/count-policy decision, DeepSeek validation, new native Run or company result. Old E01 wrong zero stays withheld. Program/source-input construction used original checkout7a5b328b4df55fdbe2a60878832d2ae9b4076b4b; this commit only archives the small developer evidence and does not change production code.

Blind context:9 tools including nested calls,1 final message,2026-10-08T15:14:21Z–15:15:10Z. Detailed scope/resource record is `blind-context.md`. New provider/paid/SEC calls0/0/0; original cumulative143/143/52 unchanged.

Reproduce form checking with `verify.py`; the fixed contract is read from the local Git object, never substituted from the moving peer branch. Canonical helpers use this original evidence branch. A later semantic/code change requires its own verification.
