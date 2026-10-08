import json, sys, subprocess, tempfile
from pathlib import Path
REPO = Path("/home/user/SEC_metrics")
sys.path.insert(0, str(REPO / "scripts"))
from vnext import historical_coverage as cov
from vnext.historical_run_receipts import read_run_receipt
S = Path(sys.argv[1])  # the scratch directory holding frame4/ (the batch root)
named = json.loads((REPO / "docs/evidence/issue47_history/native-run-batch-2026-10-01/version-releases.json").read_text())
keys = [(n["defect_id"]) for n in named["named"]] + [x["defect_id"] for x in named["left_as_withdrawn_by_another_entry"]]
reg_now = json.loads((REPO / "docs/evidence/issue47_history/known_result_defects.json").read_text())
before_text = subprocess.run(["git", "-C", str(REPO), "show", "e517de36^:docs/evidence/issue47_history/known_result_defects.json"],
                             capture_output=True, text=True, check=True).stdout
reg_before = json.loads(before_text)
acceptances = cov.independent_content_acceptances(repo_root=REPO)
frame = {}
for f in (S / "frame4").glob("*/matrix-*.json"):
    for p in json.loads(f.read_text())["positions"]:
        frame[(p["company_id"], p["metric_id"], p["report_end"])] = p
rows = []
for defect in reg_now["defects"]:
    if defect["defect_id"] not in keys:
        continue
    key = (defect["company_id"], defect["metric_id"], defect["period_end"])
    p = frame[key]
    run_dir = S / "frame4/runs" / ("run-" + p["case"] + "-" + p["metric_id"])
    receipt = read_run_receipt(run_dir=run_dir)
    (result,) = [r for r in receipt["results"] if r["metric_id"] == p["metric_id"]]
    out = {"defect_id": defect["defect_id"], "position": list(key), "result_id": result["result_id"][:20],
           "publication": result.get("publication"), "value": result.get("value")}
    for label, reg in (("before", reg_before), ("after", reg_now)):
        d = cov._matching_defect(defects=reg["defects"], company_id=key[0], metric_id=key[1], report_end=key[2],
                                 result=result, receipt=receipt)
        out["withdrawn_" + label] = d["defect_id"] if d else None
    acc, why, _ = cov._acceptance_for_position(acceptances=acceptances, company_id=key[0], metric_id=key[1],
                                               report_end=key[2], result=result)
    out["accepted"] = acc["acceptance_id"] if acc else why
    rows.append(out)
print(json.dumps(rows, indent=1, ensure_ascii=False))
