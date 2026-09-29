# The SEC ledger lost with the container, and how the acquisition resumes

## What happened

The acquisition runs in the executor's cloud container (plan revision 6). The
driver acquires one company at a time and, after each, exports the ledger and
the sources to `evidence/issue47_acquired/` and pushes them.

- 12:21:56Z: the export after Enphase's second round was committed as
  `cd50ded9` ("70 captured (0 failed), cumulative [0, 0, 288]") and pushed at
  12:22:00Z. The driver then started `acquire --company ford_motor_company`.
- 12:22:16Z: `c984303f`, a record commit (the FY2021 Run-level probe), was
  pushed. It is not an export.
- 12:28:24Z: the executor's process listing still showed the Ford invocation
  running, 6 minutes 18 seconds of CPU time since 12:22 - it was planning,
  which is CPU-bound; captures are held to the client's rate limit.
- Between 12:29:11Z (the last check that showed it) and 12:32:06Z (the
  harness's notice), the container was restored from an older snapshot. The
  checkout went back to `f231fd3f`; the ledger root
  `/root/.local/state/sec_metrics/issue47-historical-sec-cloud-v1`, its
  anchor, its claim-log mirror and its start record were gone, and so was the
  driver's log. The branch kept everything up to `c984303f`, including the
  export at 288.

The times after the last push come from the executor's session record, not
from anything the branch carries; the branch shows only that no export
followed `cd50ded9`.

## What was lost, and its bound

Whether the Ford invocation sent any request is not known. In Enphase's second
round, planning and all 70 captures took under nine minutes, so it may have.
What is known is how much it could have sent:

- **Only Ford.** The driver starts the next company only after the current
  one's export is pushed, and no export followed `cd50ded9`.
- **At most Ford's due set at the export state.** `measure_due_sets.py`
  computes, on the data root the export restores to, exactly what
  `capture_pending` would claim: the planner's declared frame, the rows that
  need a new acquisition, minus the URLs the exported slots already claimed,
  each asked of the grants. For Ford: 273 declared rows, **224 due and inside
  the grants** - 220 `FISCAL_EVENT_FILING` and 4
  `GOVERNANCE_DISCLOSURE_FILING` - none outside the grants, none already
  claimed, no limitations (`due-sets-288-ford.json`, 1,473 seconds, zero
  calls). A URL is claimed at most once and nothing is retried, and capturing
  an event filing or a proxy declares nothing new, so no later pass could have
  claimed more. For Enphase, the company before it, the same measurement gives
  0 (`due-sets-288-enphase.json`).

So the lost segment spent between 0 and 224 SEC requests.

## What the resume charges

Resuming is the owner's decision. An earlier draft of this file said the owner
had allowed the acquisition to run again after being told of the loss; that
came from the executor's session summary, not from the owner. The transcript
holds one "允许运行 SEC 取数" from the owner, at 08:37:18Z, before the
acquisition started; every message after the loss was the harness's own
"continue". So nothing was resumed on it, and the decision was asked for. At
16:18:13Z the owner chose to resume with the loss charged at its upper bound,
224 (`../../owner-decisions-2026-09-29/resume-decision.json`, the question and
answer as the executor transcribed them). The resume
(`scripts/vnext/historical_sec_resume.py`, `tools/vnext_historical_sec.py
resume`):

1. restores the ledger exactly as the branch's export carries it (slots, claim
   log, binding, attribution, data root), through the same restore that checks
   every archive and replays the frozen checkpoint;
2. charges the lost segment: the due rows of the companies the lost host could
   have been acquiring, computed the same way as above - 224 for Ford. It
   refuses, rather than understates, if any such row is of a class whose
   capture could declare more rows;
3. writes a resume record beside the root, whose random number stays local,
   and prints a marker comment for issue 47 carrying the record's public view,
   its digest and the owner's decision as the executor transcribed it.

The ledger counts the reserve: `snapshot()` adds every resume's reserve to the
SEC count, so a claim is refused once the slots plus the reserves reach the
cap. The restored ledger has not claimed Ford's 224 rows, so re-acquiring Ford
spends up to 224 more. **Cumulatively: 288 exported + 224 reserve = 512 of
1,354 before Ford is acquired again, up to 736 after.** The other eight
companies share what is left, which the plan's own measurements suggest is
not enough for all of them; the acquisition stops at the cap and the
remainder is reported by class. The cap stays a true upper bound on what
reached the SEC; the cost of keeping it true is the up-to-224 requests the
lost segment may never have made.

Two of the eight were measured the same way on the same state, to size what
is left: JPMorgan has nothing due inside the grants - 180 rows are due and
all fall outside every grant, 176 of them event filings of FY2021-FY2024
windows the plan left to a later application
(`due-sets-288-jpmorgan.json`, written per company by a run the restart
stopped after JPMorgan) - and Macy's has 114 due inside them, 112 event
filings and 2 proxies (`due-sets-288-macys.json`). Lumen, Marriott,
Paramount, Pfizer, Salesforce and Southwest were not measured.

The live path then requires the resume to be published: the issue's resume
markers must be exactly the local chain's public views (one more on the issue
is a resume made elsewhere, one fewer is one not yet published), the start
marker every resume names must be the approval's earliest, unedited, and the
ledger must not be behind the branch's export of it. Every later export
carries the chain's public views (`ledger/resumes.jsonl`), and an export that
would drop it is refused.

## The resume as run

`tools/vnext_historical_sec.py resume --in-flight-company ford_motor_company`
ran from 17:42:08Z to 18:14:34Z at branch tip `8cb1036d`, with the owner's
answer and its time as the decision. It restored the export at 288
(`sha256:788aceca...`), charged 224 - 220 event filings and 4 proxies, none
outside a grant, the same count as the two measurements above - and returned
`LEDGER_RESUMED` with zero calls. The marker was posted as issue 47 comment
5895989753 and read back through the live path's own reader: one marker,
unedited, equal to the local chain's public view. The export that followed
(`sha256:c6356dd9...`, still 288 rows) carries the chain, which the live path
requires before any claim.

## What an independent review found, and what changed

A separate agent with a fresh context (same model family, not a human)
reviewed the resume before any request: PASS_WITH_FINDINGS, three medium and
five low. It computed Ford's reserve itself from the committed export - 224,
the same 220 event and 4 proxy rows - and reproduced each medium finding:

1. **A resume did not stop the host it replaced, or a session already
   running.** A host that still held its start record passed the live path
   beside a published resume. Now the start path refuses once the issue shows
   a resume of this approval (`ISSUE_47_SEC_LEDGER_RESUMED_ELSEWHERE`), and a
   live session runs the published check again before every pass, stopping
   the acquisition if it no longer holds.
2. **A resume trusted whatever export the checkout held.** A checkout older
   than the branch - which is what this loss did to it - restored an older
   export and charged only what came after it. Now the resume and the live
   path fetch the checkout's upstream, require HEAD to contain the tip and the
   checkout's export to be the tip's, and the resume records the tip commit.
   The same check closes an older gap the review named: a snapshot restore that
   takes the ledger, what is beside it and the checkout back together passed
   the live path, because every check compared with the checkout alone.
3. **Deleting the resume record mid-session lowered the count**, and captures
   ran past the cap. Now the live ledger is held to the charge the published
   check verified (`ISSUE_47_LEDGER_RESUME_RESERVE_CHANGED`), and a LIVE ledger
   with neither a start nor a resume beside it is not exported.

The low findings: the guards the review found untested now have cases and
injections (a resume of another start, a claim log that is not what was
restored, an edited marker, a second resume on the same host, the review's
two mutations); a resume holds an exclusive sentinel, moves the data root
last and never removes another resume's staging directory; a resume marker
must start with its title, and the same record posted twice is one resume;
and nothing is claimed until the branch's export carries the whole resume
chain. Not changed: the reserve's premise that capturing an event filing or a
proxy declares nothing new is checked by reading the declarations, not by a
case that captures a real frame; and the in-flight companies are the
executor's record.

## What this does not guard

The same as the start (see `../README.md`): the gates bind the executor's code
path, not the executor; a marker comment can be deleted by the account the
executor acts as. In addition, the reserve rests on the executor's record of
which companies the lost host could have been acquiring. What the owner can
check is the branch: the export before the loss, the resume marker, and every
export after it.

## Verification

- `tests/vnext/test_historical_sec_session.py`,
  `ALostHostResumesFromTheExportAndPaysForWhatItMayHaveSpent`: 12 cases - a
  lost LIVE ledger resumes from its export, its count carries the reserve, one
  more capture reaches the cap, the next export carries the chain without the
  random number, a tampered or dropped chain is refused, a second loss resumes
  again; a host that kept its start or its root does not resume; the export
  must be this approval's and the branch tip's; the start marker is required
  and unedited; a decision and in-flight companies are required; the reserve's
  own cases; a running session stops when a resume is published elsewhere; a
  host that still holds its start may not spend after a resume; the resume
  charge cannot shrink while a session holds the ledger; a resume already
  running or left over is not disturbed; and the guards the review found
  untested. `TheResumeIsHandedTheBranchTipThroughGit`: 3 cases over a
  temporary git repository - a checkout behind the branch is handed the
  branch's newer export, a tip with no export hands none, a checkout with no
  upstream is refused.
- The whole module in the checkout: 183 cases, all passing except the seven
  that read the committed wiring receipt, which listed the evidence set before
  this module was added (`ISSUE_47_OFFLINE_WIRING_EVIDENCE_SET_CHANGED:
  missing=scripts/vnext/historical_sec_resume.py`); the receipt was rebuilt
  afterwards with `tools/vnext_historical_wiring.py`.
- `../resume_injections.py`: 28 injections, each undoing one part of the
  above, all caught by the case written for it (`../resume-injections.json`,
  merged into `../fault-injections.json`, which the wiring receipt hashes).
  The first run caught 27: removing the rule that only a comment beginning
  with the marker's title is a marker passed, because the case's status
  comment quoted the published record itself, which collapses into the marker
  by digest. The case now also posts a status comment quoting a record no
  marker carries; the same injection is caught there, and the run was
  repeated whole with the final test file. After that run the repository's
  literal scan flagged a fixed date in the resume module's docstring and in
  one refusal's message (this folder's dated path); both were reworded, the
  message keeping its reason code, and the injection on that refusal was run
  again against the reworded module and caught.
- The independent review above, before any request, and its findings fixed
  before the resume ran.

Zero SEC or provider calls in all of the above.
