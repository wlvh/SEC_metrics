# Local source registration and comparison-base continuation

The linked worktree remains the development checkout. Normal historical source
preparation for newly acquired JPM filings failed at the frozen trusted-journal
check because it requires a .git directory. Initial worktree restore returned
journaled=false; earlier baseline-only B06 source preparation was not proof of
this acquired-source path. No frozen #28 check was loosened.

A separate private local clone of commit41949f67, with no hardlinked/shared Git
object option, restored the committed SEC export and registered its checkpoint
in its own .git journal through the original full validation. It copies no
private journal or credentials from another checkout. Restore returns1547 rows,
LIVE provenance, journaled=true and0/0/0 new calls. This retains old-source credit
only; it is not a new acquisition or approval.

A first helper incorrectly resolved the venv Python symlink to the base interpreter,
losing tokenizers; that environment failure is retained. The corrected interpreter
prepares four complete JPM C02 inputs with4413/4630/3993/4106 blocks and
441/455/402/409 tables. Input tokens156910/161678/126892/129805 all fit the original
200000 context with4096 reserve. These are prepared inputs, not new answers.
The full original reference reading is still in progress; only current-year
B0–B434 has been semantically read in this new continuation at this checkpoint.

The first install helper used a source root inside code and was correctly refused
by the external-root guard. A fresh external restore is used for installation/
independent cold replay; no source/output guard is changed. Final outcome is
recorded separately when complete.

New comparison base c7a96eae was fixed and read. Ordinary C02 table input/native
pending Review development paths, blind-reference evidence and the configured
protected-ledger-root repair are additive. Peer defect rows are unchanged; no
historical business method or acceptance is borrowed. The actual merge-tree
conflict was only the fast registry. Preflight24 cases passed in the isolated
private clone, then post-merge41 focused/snapshot cases passed. All seven new
registrations are retained; the inherited Requirement authority remains unchanged.
A new full fast run and final-head CI follow the merge rather than borrowing
previous-head green status. No Ready, merge to PR43, formal adoption or active switch.

Merged-head full fast188 selectors PASS, jobs1,196.168s, original30s cap.
Source/actual model/full-company acceptance is not inferred. Imported original
peer inspection logs contain trailing whitespace, and the received formatter
has a final blank LF; those bytes are retained rather than editing peer evidence.
Own merge-resolution/evidence paths pass whitespace checks.
New current-source reading now covers B0–B882, with the tool-truncated B630–634
recovered explicitly. This is still a partial full-document reference, not credit.
