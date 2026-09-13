# Current-instant CI job timeout

Run34701689688 on4e025650ff61de6e2b8a549f7a11e6780447f929 ended CANCELLED. Fast and source-material jobs passed; native-runs reached the final current-instant attack step, then exceeded its existing20-minute job limit. The actual GitHub check annotation says: `The job has exceeded the maximum execution time of 20m0s`. The operation cancellation is not an assertion failure or a passing native check.

The added current-instant creation and attack steps are now a separate independent job, retaining their exact commands, environment, Pythonversion and20-minute limit. Existing shared/lodging native steps retain their own20-minute limit. No test, assertion or source was dropped and the original run is not rerun unchanged. Observe the next actual CI independently.

This is CI scheduling repair, not source/semantic/runtime-rule change. V14 remains41a74984de39cdb073d3744f061cc0dae01a7088076da527066c0f1fe5cae2bd/327. R6 source/review prototypes currently in the working directory are separate uncommitted work and receive no CI credit from this repair.
