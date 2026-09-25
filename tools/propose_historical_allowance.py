"""Build Issue #47's allowance request and check the code would accept it.

The plan asks for a cumulative cap of SEC request attempts. What the
code reads is an object with nine fields plus an approval comment that
restates three of them, so an ask written as a sentence is not checkable and
an ask written as JSON that nobody ran is only probably checkable. This
builds both halves and runs them through the real verifier in a temporary
tree, so what is proposed is known to be a thing the gate accepts rather than
a thing that looks like one.

Nothing here grants anything: the policy is written to a proposal path, not to
config/issue47_historical_calls_v1.json, and the delegation body has to be
posted by the owner before its digest exists.
"""
import json, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from vnext.canonical import sha256_bytes
from vnext.historical_source_acquisition import (POLICY_PATH, REQUIRED_POLICY_FIELDS,
                                                 TRUSTED_APPROVER, TRUSTED_REPOSITORY,
                                                 acquisition_allowance)

# Every value below is measured, not chosen: the companies from the registry,
# the dependency classes and the window from what the frame's declaration
# actually produces, and the cap from the acquisition plan. The first version
# of this listed the classes by hand; when C02 and C03 were wired the
# declaration gained GOVERNANCE_DISCLOSURE_FILING and the hand list did not,
# so every proxy the plan counts would have been refused as out of scope.
from vnext.historical_source_acquisition import declared_frame  # noqa: E402

COMPANIES = sorted(line.split(",")[0] for line in
                   (REPO / "config/company_registry.csv").read_text().splitlines()[1:]
                   if line.strip())
_FRAMES = [declared_frame(repo_root=REPO, company_id=company, years=5) for company in COMPANIES]
CLASSES = sorted({row["dependency_class"] for frame in _FRAMES for row in frame["requirements"]})
_DATES = sorted({date for frame in _FRAMES for date in frame["target_report_dates"]})
WINDOW = (_DATES[0], _DATES[-1])
PLAN = json.loads((REPO / "docs/evidence/issue47_history/acquisition-plan.json").read_text())
CAP = PLAN["cumulative_cap"]["requested"]
BUDGET_ROOT = "<OWNER CHOOSES: an absolute path on the executing host, and not Issue #28's>"

approved = {
    "record_type": "ISSUE_47_HISTORICAL_SEC_DELEGATION",
    "requirement_id": "issue_47_v1",
    "maximum_additional_provider_paid_sec_calls": [0, 0, CAP],
    "budget_root": BUDGET_ROOT,
    "scope": {"purposes": ["ISSUE47_HISTORICAL_SOURCE_DEPENDENCY"],
              "company_ids": COMPANIES, "dependency_classes": CLASSES,
              "earliest_report_end": WINDOW[0], "latest_report_end": WINDOW[1]},
    "production_authorized": False,
}
body = json.dumps(approved, indent=1, sort_keys=True)
digest = sha256_bytes(content=body.encode("utf-8"))

# A stand-in comment with the shape the verifier requires, so the offline
# checks can run. The id and the URL are placeholders until the real comment
# exists; the fetched-comment check is not run here and cannot be.
COMMENT_ID = 1
policy = {
    "requirement_id": "issue_47_v1", "repository": TRUSTED_REPOSITORY,
    "approver_login": TRUSTED_APPROVER,
    "delegation_url": ("https://github.com/" + TRUSTED_REPOSITORY + "/issues/47"
                       "#issuecomment-" + str(COMMENT_ID)),
    "delegation_body_sha256": digest,
    "delegation_record_path": "docs/evidence/issue47_history/acquisition-wiring/"
                              "delegation-comment.json",
    "budget_root": BUDGET_ROOT,
    "maximum_additional_provider_paid_sec_calls":
        approved["maximum_additional_provider_paid_sec_calls"],
    "scope": approved["scope"],
    "sec_wiring_receipt_path": "docs/evidence/issue47_history/acquisition-wiring/"
                               "offline-wiring-receipt.json",
}
record = {"html_url": policy["delegation_url"], "id": COMMENT_ID,
          "issue_url": "https://api.github.com/repos/" + TRUSTED_REPOSITORY + "/issues/47",
          "user": {"login": TRUSTED_APPROVER}, "body": body}

checks = {}
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / Path(POLICY_PATH).parent).mkdir(parents=True, exist_ok=True)
    (root / POLICY_PATH).write_text(json.dumps(policy, indent=1, sort_keys=True))
    (root / policy["delegation_record_path"]).parent.mkdir(parents=True, exist_ok=True)
    (root / policy["delegation_record_path"]).write_text(json.dumps(record, indent=1))
    try:
        allowance = acquisition_allowance(repo_root=root)
        checks["accepted_offline"] = True
        checks["limits_read_back"] = allowance["maximum_additional_provider_paid_sec_calls"]
        checks["provenance_verified_against_github"] = allowance.get(
            "provenance_verified_against_github")
    except Exception as error:                          # noqa: BLE001 - reported
        checks["accepted_offline"] = False
        checks["refusal"] = type(error).__name__ + ": " + str(error)[:300]
    # And the negative that says the check is doing something: widen the cap in
    # the policy only, leaving the approved body as it is.
    widened = {**policy, "maximum_additional_provider_paid_sec_calls": [0, 0, 5000]}
    (root / POLICY_PATH).write_text(json.dumps(widened, indent=1, sort_keys=True))
    try:
        acquisition_allowance(repo_root=root)
        checks["a_policy_that_grants_more_than_the_comment"] = "ACCEPTED - BAD"
    except Exception as error:                          # noqa: BLE001 - expected
        checks["a_policy_that_grants_more_than_the_comment"] = str(error)[:120]

out = {"record_type": "ISSUE_47_PROPOSED_SEC_ALLOWANCE",
       "issue": "https://github.com/wlvh/SEC_metrics/issues/47",
       "this_is_a_proposal_not_a_grant": {
         "where_a_grant_would_live": POLICY_PATH,
         "where_this_lives": "docs/evidence/issue47_history/acquisition-wiring/"
                             "proposed-allowance.json",
         "what_is_still_missing": ["the owner posts the comment body below on "
                                   "issue 47, which is what creates its id, "
                                   "URL and digest",
                                   "the owner chooses budget_root - an absolute "
                                   "path on the executing host, and not Issue "
                                   "#28's",
                                   "the saved comment record is fetched from "
                                   "GitHub and must match byte for byte"]},
       "required_policy_fields": list(REQUIRED_POLICY_FIELDS),
       "the_comment_body_to_post": approved,
       "the_comment_body_as_text": body,
       "how_the_values_were_obtained": {
         "company_ids": "config/company_registry.csv",
         "dependency_classes": ("the classes all ten companies' declared_frame "
                                "output carries: %d rows in these %d classes"
                                % (sum(len(f["requirements"]) for f in _FRAMES), len(CLASSES))),
         "window": ("the frame's own %d target report dates, %s through %s. The "
                    "prior-period dependencies each carry the TARGET period as "
                    "their consumer, so the window does not need to reach back "
                    "a sixth year even though the materials do."
                    % (len(_DATES), WINDOW[0], WINDOW[1])),
         "cap": ("docs/evidence/issue47_history/acquisition-plan.json - "
                 + PLAN["cumulative_cap"]["arithmetic"]
                 + ", a stop-cap rather than an estimate")},
       "verified": checks,
       "calls": {"provider": 0, "paid": 0, "sec": 0},
       "production_authorized": False}
(REPO / "docs/evidence/issue47_history/acquisition-wiring/proposed-allowance.json").write_text(
    json.dumps(out, indent=1, sort_keys=True) + "\n")
print(json.dumps({"verified": checks, "digest_of_the_body": digest}, indent=1))
