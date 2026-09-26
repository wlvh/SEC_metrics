"""Build Issue #47's allowance request and check the code would accept it.

The plan asks for a cumulative cap of SEC request attempts. What the
code reads is an object carrying every field REQUIRED_POLICY_FIELDS names,
plus an approval comment that restates three of them, so an ask written as a
sentence is not checkable and an ask written as JSON that nobody ran is only
probably checkable. This builds both halves and runs them through the real
verifier in a temporary tree, so what is proposed is known to be a thing the
gate accepts rather than a thing that looks like one.

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
BUDGET_ROOT = PLAN["revision_4"]["ledger"]["proposed_budget_root"]
EVERYONE = COMPANIES
BANK = "jpmorgan_chase"
OTHERS = [company for company in COMPANIES if company != BANK]
# One grant per measured class and company group, so the gate admits what the
# plan's text counts and nothing it does not. COMPANYFACTS is in no grant
# because no class counts a Company Facts request.
GRANTS = [
    {"grant": "A_ANNUAL_CHAIN", "company_ids": EVERYONE,
     "dependency_classes": ["ACCESSION_INSTANCE_DISCOVERY", "ANNUAL_PERIOD_IDENTITY"],
     "earliest_report_end": WINDOW[0], "latest_report_end": WINDOW[1]},
    {"grant": "A_JPMORGAN_METADATA", "company_ids": [BANK],
     "dependency_classes": ["SUBMISSIONS_HISTORY", "SUBMISSIONS_INDEX"],
     "earliest_report_end": WINDOW[0], "latest_report_end": WINDOW[1]},
    {"grant": "B_EVENT_WINDOWS", "company_ids": OTHERS,
     "dependency_classes": ["FISCAL_EVENT_FILING"],
     "earliest_report_end": WINDOW[0], "latest_report_end": WINDOW[1]},
    {"grant": "B_JPMORGAN_FY2025_KNOWN_HEADER", "company_ids": [BANK],
     "dependency_classes": ["FISCAL_EVENT_FILING"],
     "earliest_report_end": "2025-12-31", "latest_report_end": "2025-12-31"},
    {"grant": "G_GOVERNANCE_PROXIES", "company_ids": OTHERS,
     "dependency_classes": ["GOVERNANCE_DISCLOSURE_FILING"],
     "earliest_report_end": WINDOW[0], "latest_report_end": WINDOW[1]},
    {"grant": "G_JPMORGAN_FY2024_PROXY", "company_ids": [BANK],
     "dependency_classes": ["GOVERNANCE_DISCLOSURE_FILING"],
     "earliest_report_end": "2024-12-31", "latest_report_end": "2024-12-31"},
]
GRANTED_CLASSES = sorted({value for grant in GRANTS for value in grant["dependency_classes"]})

approved = {
    "record_type": "ISSUE_47_HISTORICAL_SEC_DELEGATION",
    "requirement_id": "issue_47_v1",
    "maximum_additional_provider_paid_sec_calls": [0, 0, CAP],
    "budget_root": BUDGET_ROOT,
    "scope": {"purposes": ["ISSUE47_HISTORICAL_SOURCE_DEPENDENCY"],
              "company_ids": COMPANIES, "dependency_classes": GRANTED_CLASSES,
              "earliest_report_end": WINDOW[0], "latest_report_end": WINDOW[1],
              "grants": GRANTS},
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

# The alignment itself, measured: every row the declaration says still needs a
# fetch, asked of the proposed scope exactly as the gate will ask it. What the
# grants refuse must be what the plan's text says it does not cover, and
# nothing else. This covers the rows declared today; the rows a catalog cannot
# declare yet are asked about below.
from vnext.historical_source_acquisition import (HistoricalAcquisitionError,  # noqa: E402
                                                 request_is_in_scope)
census = {"admitted_by_grant": {}, "refused": {}}
for frame in _FRAMES:
    for row in frame["requirements"]:
        if not row.get("new_acquisition_required"):
            continue
        try:
            admitted = request_is_in_scope(
                allowance={"scope": approved["scope"]}, company_id=frame["company_id"],
                dependency=row, purpose="ISSUE47_HISTORICAL_SOURCE_DEPENDENCY",
                frame_report_dates=frame["target_report_dates"])
            for name in admitted["grants"]:
                census["admitted_by_grant"][name] = census["admitted_by_grant"].get(name, 0) + 1
        except HistoricalAcquisitionError as error:
            reason = str(error).split(":")[0]
            key = frame["company_id"] + ":" + row["dependency_class"] + ":" + reason
            census["refused"][key] = census["refused"].get(key, 0) + 1


# The census can only ask about rows the declaration makes today. The grants are
# company x class x target window, so they also decide the rows it will make
# once a catalog reaches further back. The plan once said JPMorgan's three
# periods its saved shards do not reach needed a separate application, while
# A_ANNUAL_CHAIN admitted their annual chains: the text described one grant and
# the object was another. So the plan now states, as data, what the grants do
# with each target a catalog does not reach yet, and this asks the same gate the
# same question - one row per probed class, the target as its consumer, which is
# how the planner ties even the earliest target's prior-year documents to a
# target inside the window. The proposal is not written if the two disagree.
def _unreached_targets(frame, years):
    """Targets a frame's catalog does not reach yet, stepped back a year at a time.

    Exact for a calendar fiscal year; for a 52/53-week year the stepped date can
    miss the real period end by days, which matters only if that moves it across
    a grant's window edge.
    """
    from datetime import date
    reached = sorted(frame["target_report_dates"])
    if not reached:
        raise SystemExit("NOT_YET_DECLARABLE_HAS_NO_REACHED_TARGET_TO_STEP_FROM:"
                         + frame["company_id"])
    earliest = date.fromisoformat(reached[0])
    stepped = []
    for step in range(1, years - len(reached) + 1):
        day = min(earliest.day, 28) if earliest.month == 2 else earliest.day
        stepped.append(earliest.replace(year=earliest.year - step, day=day).isoformat())
    return sorted(stepped)


PROBED_CLASSES = ("ACCESSION_INSTANCE_DISCOVERY", "ANNUAL_PERIOD_IDENTITY",
                  "FISCAL_EVENT_FILING", "GOVERNANCE_DISCLOSURE_FILING")
not_yet_declarable = {}
for frame in _FRAMES:
    targets = _unreached_targets(frame, years=5)
    if not targets:
        continue
    by_class = {}
    for target in targets:
        for dependency_class in PROBED_CLASSES:
            try:
                request_is_in_scope(
                    allowance={"scope": approved["scope"]}, company_id=frame["company_id"],
                    dependency={"dependency_class": dependency_class,
                                "consumers": ["period:" + target]},
                    purpose="ISSUE47_HISTORICAL_SOURCE_DEPENDENCY",
                    frame_report_dates=frame["target_report_dates"])
                answer = "admitted_once_declarable"
            except HistoricalAcquisitionError as error:
                # Only "no grant covers it" is an answer about the grants; a
                # refusal for any other reason means the probe asked badly.
                if not str(error).startswith("ISSUE_47_REQUEST_OUTSIDE_EVERY_GRANT"):
                    raise SystemExit("NOT_YET_DECLARABLE_REFUSED_FOR_ANOTHER_REASON:"
                                     + str(error)[:160])
                answer = "outside_every_grant"
            by_class.setdefault(dependency_class, set()).add(answer)
    # One answer per class across the unreached targets, or the plan's
    # per-company statement cannot say it truthfully.
    mixed = sorted(name for name, answers in by_class.items() if len(answers) > 1)
    if mixed:
        raise SystemExit("NOT_YET_DECLARABLE_ANSWER_DIFFERS_BY_TARGET:"
                         + frame["company_id"] + ":" + ",".join(mixed))
    not_yet_declarable[frame["company_id"]] = {
        "targets": targets,
        **{answer: sorted(name for name, answers in by_class.items() if answer in answers)
           for answer in ("admitted_once_declarable", "outside_every_grant")}}
stated = PLAN["revision_5"]["not_yet_declarable"]
if stated != not_yet_declarable:
    raise SystemExit("THE_GRANTS_DO_NOT_MEAN_WHAT_THE_PLAN_SAYS: plan "
                     + json.dumps(stated, sort_keys=True) + " gate "
                     + json.dumps(not_yet_declarable, sort_keys=True))
checks["not_yet_declarable_matches_the_plan"] = True

out = {"record_type": "ISSUE_47_PROPOSED_SEC_ALLOWANCE",
       "issue": "https://github.com/wlvh/SEC_metrics/issues/47",
       "this_is_a_proposal_not_a_grant": {
         "where_a_grant_would_live": POLICY_PATH,
         "where_this_lives": "docs/evidence/issue47_history/acquisition-wiring/"
                             "proposed-allowance.json",
         "what_is_still_missing": ["the owner posts the comment body below on "
                                   "issue 47, which is what creates its id, "
                                   "URL and digest",
                                   "the owner confirms or replaces budget_root: "
                                   "proposed beside Issue #28's root on the "
                                   "executing host, and the gate refuses #28's "
                                   "root, anything inside it and anything inside "
                                   "the checkout",
                                   "the saved comment record is fetched from "
                                   "GitHub and must match byte for byte"]},
       "execution_scope_census": {
         "what": ("every declared row that still needs a fetch, across all ten "
                  "companies' frames, asked of this scope exactly as the gate asks "
                  "it: which grant admits it, or why it is refused"),
         **census},
       "grants_for_dependencies_not_yet_declarable": {
         "what": ("for every target a company's saved catalog does not reach yet, "
                  "whether the grants admit each probed class once the declaration "
                  "can name its rows, asked of the same gate with the target as the "
                  "row's consumer"),
         "measured": not_yet_declarable,
         "stated_in": "docs/evidence/issue47_history/acquisition-plan.json revision_5",
         "meaning": ("inside the grants' companies, classes and target window, a "
                     "dependency the declaration comes to require is admitted and "
                     "draws on the one cumulative cap, whether or not it could be "
                     "counted when the cap was measured; outside them it needs a "
                     "measured increment. The proposal is not written when the "
                     "gate's answers differ from the plan's statement.")},
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
