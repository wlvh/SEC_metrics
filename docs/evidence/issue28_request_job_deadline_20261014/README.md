# Request-limits job deadline, retaining all tests

Progress on #28. Base actual main681b35d865af9660ad03ffbbb20ec93cd499d9cd. This addresses the [receiver's concrete request6163113131](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-6163113131), separately from fast-job PR268.

Only `.github/workflows/request-limits.yml` job deadline changes5→10 minutes, plus an explanatory comment. Python setup, pinned install requirement, both exact required-unittest commands, their names/env, coverage, individual material limits and failure behavior are byte-for-byte unchanged. No skip, wider exception, removed source check or whole-CI retry is introduced.

Evidence boundary: Root actually read the receiver's server comment. It reports original job115697781007 cancelled after314 seconds while NativeCurrentRequestTest was still passing, followed by a successful218-second rerun; PR274 has since been accepted into main. Direct raw-log reads in this turn failed with tool transport errors and are not claimed as independent log reproduction. Local difference verification confirms every byte outside the two-line deadline/comment change is retained. This is runner/setup headroom, not a business assertion fix or a claimed test speedup. Newhead CI is separate.

No finance/source/model replay is needed for this one job-level deadline edit. Existing applicable completed tests stay evidence for their original trees. New provider/paid/SEC calls0/0/0; no Ready/merge/protection/adoption/deployment action.
