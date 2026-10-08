"""Append the extension injections to fault-injections.json, which the wiring receipt hashes."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
wiring = REPO / "docs/evidence/issue47_history/acquisition-wiring"
record = json.loads((wiring / "fault-injections.json").read_text(encoding="utf-8"))
results = json.loads((Path(__file__).with_name("extension-injections.json")).read_text(
    encoding="utf-8"))["results"]
ids = {result["id"] for result in results}
record["injections"] = [item for item in record["injections"] if item["id"] not in ids]
for result in results:
    record["injections"].append({
        "id": result["id"], "edit": result["edit"],
        "caught_by": [result["expected_case"]] if result["outcome"] == "CAUGHT" else [],
        "outcome": result["outcome"], "suite_result": result["suite_result"],
        "why_it_matters": result["why_it_matters"],
        "run": "2026-09-30, an isolated sparse clone, acquisition-extension/extension_injections.py; "
               "failed cases " + ", ".join(result["failed_cases"])})
(wiring / "fault-injections.json").write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n",
                                              encoding="utf-8")
print(len(record["injections"]), "injections recorded")
