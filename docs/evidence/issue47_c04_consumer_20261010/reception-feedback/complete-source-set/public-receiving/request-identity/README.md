# PR143 request identity dependency feedback

Feedback r4240920702 is reproducible from the processing tuple: historical C04 calls request_log_attempt_id through the source reader but did not include scripts/sec_http.py. The tuple now includes it alongside sec_urls.py. Production extraction and sources are unchanged.

22 actual historical C04 case/selection controls pass in 0.125s, zero skips. The constructed withholding state control uses the ordinary updater configuration: unchanged input reuses without invoking the factory; a simulated request-identity implementation change produces one new processing version, repeats reuse it, and original result files remain byte-identical. This control is labelled constructed, not a financial zero. The source URL change control remains.

The added processing dependency causes one ordinary reprocessing after upgrade; this is deliberate because source-reference identity semantics are relevant. The existing real Ford source/extraction evidence remains under its recorded implementation and is not retagged. No financial recalculation or source/provider request is performed for this dependency-only repair. Saved old record reading does not use this processing tuple. Reproduce from this head with the existing project Python environment:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py tests.vnext.test_historical_auditor_case tests.vnext.test_historical_auditor_selection
```

Previous bc71c225 CI reached terminal SUCCESS in all five workflows (38125574578/585/592/614/650). The following head requires its own CI and receiver recheck. No Ready, merge, adoption, deployment or active switch.
