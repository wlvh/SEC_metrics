# Public company period routing — 2026-10-10

Base actualmainf6ef7886. Peer fixed reproeeda8fc1 discovered the public CLI silently discarded fiscal-years/start/end in the call-context online branch and ran latest. This is source/period correctness and accidental-paid-acquisition prevention, not new online functionality.

Before regression: five failure instances across five methods (including subtests); unsupported history and latest-with-years reached the stubbed online runner. Stubs solely observe dispatch; no context/ledger/state/HTTP/real source/Calculator result or acceptance is fabricated.

Fix: five lines at the actual CLI after parse and before any runner/context/ledger. Fiscal-year bounds require fiscal-years; call-context only accepts latest-complete-fy. Existing saved-source history forwards the exact requested range. Supported current online args are unchanged. Clear argparse error exits2 and no writable task/context access; no duplicate caller, branch migration or added permission gate.

After:35 tests/2.175s, zero failures/errors/skips under Python3.14.7, existing recorded capture/count/UNKNOWN/no-retry/pending controls and current-reader/failure/isolation tests. Existing workflow executes test_company_online in its real step; no new runner. User-facing doc at the exact online command records latest-only and saved-history limitation. No new SEC/provider/paid, no account operation, merge, Ready, adoption or deployment. Main whole financial and recorded online calculation evidence reused, not repeated just for these argument checks.

#47 independently uses the same CLI in its receiving tests; it does not implement another online pipeline. Public future selected-period discovery remains separate work, not silently satisfied by latest plans.
