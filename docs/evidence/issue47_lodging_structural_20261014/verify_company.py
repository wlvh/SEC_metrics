"""Selected historical structural outcomes through the one company CLI."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("--source-root", required=True, type=Path)
parser.add_argument("--output-root", required=True, type=Path)
parser.add_argument("--resume-existing-evidence", action="store_true")
args = parser.parse_args()
source = args.source_root.resolve()
output = args.output_root.resolve()
output.mkdir(exist_ok=args.resume_existing_evidence, parents=True)

def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}

watch = ("config/company_registry.csv", "evidence/requests_log.csv",
         "evidence/requests_log_manifest.json")
source_before = {p: hashlib.sha256((source / p).read_bytes()).hexdigest() for p in watch}

def invoke(name, cli, forbid=False):
    previous = output/(name+".json")
    if args.resume_existing_evidence and previous.exists():
        saved = json.loads(previous.read_text())
        assert saved["arguments"] == cli and saved["exit_code"] == 0
        saved["payload"] = json.loads(saved["stdout"])
        saved["processing_calls"] = json.loads(saved["stderr"])
        saved["reused_saved_execution"] = True
        return saved
    code = """import json,sys
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_lodging_results as h,calculator
counts={}
blocked={f.__code__ for f in (h.prepare_historical_lodging_year_case,
    h.prepare_historical_lodging_case,h._resolve_historical_lodging_metric,
    calculator.calculate_metric,calculator.calculate_observation_metric)}
def observe(frame,event,arg):
 if event=="call" and frame.f_code in blocked:
  counts[frame.f_code.co_name]=counts.get(frame.f_code.co_name,0)+1
  if sys.argv[2]=="1":raise AssertionError("Unchanged input must not prepare or calculate")
sys.setprofile(observe)
try:
 with patch("socket.socket.connect",side_effect=AssertionError("No real network")):
  status=main(json.loads(sys.argv[1]))
finally:
 sys.setprofile(None)
print(json.dumps(counts),file=sys.stderr)
raise SystemExit(status)
"""
    start = time.perf_counter()
    run = subprocess.run([sys.executable, "-B", "-c", code, json.dumps(cli),
                          "1" if forbid else "0"], text=True, capture_output=True, timeout=300)
    result = {"arguments": cli, "seconds": time.perf_counter()-start,
              "exit_code": run.returncode, "stdout": run.stdout, "stderr": run.stderr}
    (output/(name+".json")).write_text(json.dumps(result, indent=2)+"\n")
    assert run.returncode == 0, result
    result["payload"] = json.loads(run.stdout)
    result["processing_calls"] = json.loads(run.stderr)
    return result

summaries=[]
for company, year, start, end in (("ford_motor_company",2021,"2021-01-01","2021-12-31"),
                                 ("salesforce",2024,"2023-02-01","2024-01-31")):
    at=output/company
    state=at/"state"
    command=["run","--company",company,"--period","fiscal-years",
             "--fiscal-year-start",str(year),"--fiscal-year-end",str(year),
             "--metric","B10","--metric","B11","--source-root",str(source),
             "--work-dir",str(state),"--output-dir",str(at/"runs")]
    first=invoke(company+"-first",command)
    assert first["processing_calls"]["prepare_historical_lodging_year_case"]==2
    assert first["processing_calls"]["calculate_metric"]==2
    assert all(m["result_reason_code"]=="TRAIT_NOT_APPLICABLE"
               for m in first["payload"]["metrics"]), first
    old=hashes(state)
    results={p:h for p,h in old.items() if "/results/" in p}
    repeat=invoke(company+"-repeat",command,True)
    assert not repeat["processing_calls"]
    assert all(not m["calculation_performed"] and not m["new_candidate_created"]
               for m in repeat["payload"]["metrics"])
    assert all(hashes(state).get(p)==h for p,h in results.items())
    before_read=hashes(state)
    read=invoke(company+"-read",["results","--company",company,
                "--state-root",str(state),"--output-root",str(at/"read")],True)
    assert before_read==hashes(state)
    with (at/"read/metrics_matrix.csv").open() as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==2,rows
    assert {r["metric_id"] for r in rows}=={"B10","B11"}
    assert all(r["period_start"]==start and r["period_end"]==end
               and not r["value"] and r["status"]=="N_A_STRUCTURAL" for r in rows),rows
    for metric in ("B10","B11"):
        check=json.loads((state/f"updates/{metric}/periods/FY{year}/completed-check.json").read_text())
        row = next(r for r in rows if r["metric_id"] == metric)
        record_root = Path(row["record_root"])
        assert state in record_root.parents
        manifest = json.loads((record_root/"manifest.json").read_text())
        assert manifest["result_id"]==row["result_id"]
        assert manifest["target_period"]["fiscal_year"]==year
        assert manifest["source_proofs"]
        assert all(v==0 for v in manifest["new_calls"].values())
        records = [json.loads(line) for line in (record_root/"records.jsonl").read_text().splitlines()]
        result = next(r for r in records if r["record_type"]=="METRIC_RESULT"
                      and r["result_id"]==row["result_id"])
        assert result["applicability"]=="N_A_STRUCTURAL"
        assert result["value"] is None and result["unit"] is None
    summaries.append({"company":company,"fiscal_year":year,
        "first":first,"repeat":repeat,"read":read,"rows":rows,
        "result_files_preserved_on_repeat":len(results),
        "state_files_preserved_on_read":len(before_read)})
    print(company,round(first["seconds"],3),round(repeat["seconds"],3),
          round(read["seconds"],3),flush=True)

assert source_before=={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in watch}
(output/"summary.json").write_text(json.dumps({"cases":summaries,
    "source_metadata_unchanged":source_before,"new_calls":[0,0,0]},indent=2)+"\n")
