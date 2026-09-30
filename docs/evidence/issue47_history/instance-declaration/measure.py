import sys, json, csv
from pathlib import Path
sys.path.insert(0, "scripts")
from vnext.historical_source_acquisition import declared_frame
from vnext.normal_history_plan import checkpoint_replayed_once
ROOT = Path(sys.argv[1])
out = {}
with checkpoint_replayed_once():
    for company in [r["company_id"] for r in csv.DictReader(open(ROOT / "config/company_registry.csv"))]:
        f = declared_frame(repo_root=ROOT, company_id=company)
        rows = [r for r in f["requirements"] if r["dependency_class"] == "ACCESSION_XBRL_INSTANCE"]
        out[company] = {"declared": len(rows), "due": sum(r["new_acquisition_required"] for r in rows),
                        "due_urls": sorted(r["source_url"] for r in rows if r["new_acquisition_required"]),
                        "consumers": sorted({c for r in rows if r["new_acquisition_required"] for c in r["consumers"]}),
                        "limitations": f["instance_declaration_limitations"]}
        print(company, out[company]["declared"], out[company]["due"], len(out[company]["limitations"]), flush=True)
json.dump(out, open(sys.argv[2], "w"), indent=1)
