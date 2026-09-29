"""Append the VM-run injections to fault-injections.json, which the wiring receipt hashes."""
import json
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]
base = REPO / "docs/evidence/issue47_history/acquisition-wiring"
record = json.loads((base / "fault-injections.json").read_text(encoding="utf-8"))
results = json.loads((base / "vm-start-injections.json").read_text(encoding="utf-8"))["results"]
why = {
 "THE_LIVE_PATH_SKIPS_THE_START": ("the check that makes a count outlive the container; without it a new container with an empty ledger spends the allowance again", "live_historical_session() no longer calls require_published_start()"),
 "ANY_MARKER_WILL_DO": ("a second container that posted its own marker later would pass; only the earliest start is the start", "require_published_start() accepts any marker equal to the local record, not only the earliest"),
 "THE_LATEST_MARKER_DECIDES": ("same as above through the ordering: the latest marker would decide", "start_markers() sorts newest first"),
 "AN_EDITED_MARKER_COUNTS": ("an edit can make an old marker carry a new number", "require_published_start() no longer requires created_at == updated_at"),
 "A_STRANGER_S_MARKER_COUNTS": ("issue 47 is public; a stranger's comment could block a start or stand in for one", "start_markers() no longer requires the owner's association"),
 "ANOTHER_APPROVAL_S_MARKER_COUNTS": ("a marker for another approval would decide this one's start", "start_markers() no longer compares the approval digest"),
 "A_LOST_LEDGER_STARTS_AGAIN": ("a container that lost its ledger could write a new start record and begin again", "start_ledger() no longer refuses when this approval already has a marker"),
 "ONLY_THE_FIRST_PAGE_IS_READ": ("the issue already has more than a page of comments; a marker on page two would be missed", "start_markers() reads only the first page"),
 "THE_READER_TAKES_ANY_PATH": ("the REST reader could be aimed at another repository's or issue's comment", "github_rest_reader() no longer checks the path"),
 "THE_PROXY_S_CREDENTIALS_ARE_RECORDED": ("a proxy URL with credentials would be written into receipts the branch carries", "_transport() records the proxy URL as given"),
 "THE_TRANSPORT_IS_NOT_RECORDED": ("a receipt silent about the proxy reads as a direct fetch from SEC", "_receipt() no longer records the transport"),
 "A_DELETED_MARKER_LETS_A_NEW_START": ("the executor acts on GitHub as the owner and can delete a marker comment; without this an empty ledger starts again once the marker is gone", "start_ledger() no longer refuses when the checkout carries this approval's export"),
 "AN_UNREADABLE_EXPORT_READS_AS_NONE": ("an export index nobody can read would read as 'nothing was spent'", "_exported_here() returns False for an index it cannot parse"),
 "AN_APP_S_POST_COUNTS_AS_THE_OWNER_S": ("the container writes GitHub as the owner through the Claude app; without this a comment it posted directly would pass as the owner's approval", "_posted_by_the_approver_directly() always passes"),
 "A_DROPPED_FIELD_READS_AS_NO_APP": ("a record or reader that drops the field would read as 'no app'", "_posted_by_the_approver_directly() reads a missing field as None"),
 "THE_SAVED_RECORD_IS_NOT_READ_FOR_THE_MARK": ("an offline read would take an app-posted record for an approval", "_delegation() no longer checks the saved record for the mark"),
 "THE_FETCHED_COMMENT_IS_NOT_READ_FOR_THE_MARK": ("a saved record cleaned of the mark would pass against a comment GitHub marks", "_delegation() no longer checks the fetched comment for the mark"),
 "REGISTRATION_DOES_NOT_READ_THE_MARK": ("registration would write the policy and record from an app's comment before any gate refused it", "register_approval() no longer checks the mark"),
 "MORE_THAN_LINE_BREAKS_IS_FORGIVEN": ("forgiving leading whitespace or a lone CR accepts a text the owner did not post as approved", "posted_text() also turns a lone CR into LF and strips leading whitespace"),
 "LINE_BREAKS_ARE_NOT_FORGIVEN": ("a body pasted into github.com may come back with CRLF and would be refused although it is the same record", "posted_text() returns the body unchanged"),
 "THE_DIGEST_IS_OVER_THE_RAW_BODY": ("registration would accept a CRLF body the gate then refuses, leaving a written policy that never grants", "_delegation() hashes the raw body instead of posted_text()"),
 "THE_MARKER_CARRIES_THE_WHOLE_RECORD": ("a marker that carries the record, random number included, can be copied back beside an empty root on any host and be the start (VM-delta review F2)", "marker_comment_body() publishes the whole record and require_published_start() compares the record itself"),
 "A_LEDGER_MAY_BE_BEHIND_ITS_EXPORT": ("a host that kept its start record but lost or reset its ledger would count from less than the branch's export says was spent (VM-delta review F2)", "require_published_start() no longer calls require_not_behind_export()"),
 "A_MARKER_FROM_ANYWHERE_COUNTS": ("a comment relayed from another issue, or by another account with the owner's association, would stand in for the start (VM-delta review F9)", "start_markers() no longer checks the comment's issue and account"),
 "AN_EXPORT_MAY_GO_BACKWARDS": ("an export of a shorter ledger, or of another approval, would be written over the record of what was spent (VM-delta review F3)", "_only_forward() always passes"),
 "A_REDIRECTED_READ_IS_TRUSTED": ("urlopen follows redirects; a reply from anywhere else would be read as this issue's comment (VM-delta review F9)", "github_rest_reader() no longer compares the final URL with the one asked for"),
}
record["injections"] = [item for item in record["injections"] if item["id"] not in why]
for result in results:
    reason, edit = why[result["id"]]
    record["injections"].append({
        "id": result["id"], "edit": edit, "caught_by": [result["expected_case"]] if result["outcome"] == "CAUGHT" else [],
        "outcome": result["outcome"], "suite_result": result["suite_result"],
        "why_it_matters": reason,
        "run": "2026-09-29, main checkout, vm_start_injections.py; failed cases " + ", ".join(result["failed_cases"])})
(base / "fault-injections.json").write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(len(record["injections"]), "injections recorded")
