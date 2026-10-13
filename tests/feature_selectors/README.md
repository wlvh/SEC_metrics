# Additive feature tests for the existing runner

Add one JSON file for a feature rather than editing the last line of
`tools/run_fast_tests_v2.py`. For example:

```json
{"fast": ["tests.vnext.test_new_feature"], "source-material": ["tests.vnext.test_new_feature.SavedOriginalTest"]}
```

Choose the existing correct layer and use nonoverlapping selectors. A whole
module plus a class from that same module would execute those tests twice;
keep each actual test in one layer. Files are read in filename order, so use
a later date/number prefix for new features. Order within each list is retained.
Only test registration belongs here, not expected business values or results.

Malformed declarations, duplicate fields/selectors, missing directory and
unreadable files fail visibly. A loaded selector still uses the existing
unittest runner, timeouts, shard handling and actual failure report. This is
not a plugin loader or a new test platform. Existing frozen runner and earlier
declarations stay in their saved versions. Tests in this directory do not
provide business/model acceptance or permission for external requests.
