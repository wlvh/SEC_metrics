"""Read an existing Enphase task in a fresh process, without computing it."""
import argparse, csv, hashlib, json, socket, subprocess, sys, time
from pathlib import Path
from unittest.mock import patch
from tools.vnext_company import main
from vnext import historical_risk_heading_case, calculator

parser=argparse.ArgumentParser()
parser.add_argument('--state-root', required=True)
parser.add_argument('--output-root', required=True)
args=parser.parse_args()
state=Path(args.state_root).resolve(); output=Path(args.output_root).resolve()
assert state.is_dir() and not output.exists()
def snapshot():
    return {str(p.relative_to(state)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in state.rglob('*') if p.is_file()}
before=snapshot()
call=['results','--company','enphase_energy','--state-root',str(state),'--output-root',str(output)]
started=time.monotonic()
with patch.object(historical_risk_heading_case,'prepare_historical_risk_heading_year_case',side_effect=AssertionError('Read must not prepare a case')), \
     patch.object(calculator,'calculate_metric',side_effect=AssertionError('Read must not compute')), \
     patch.object(calculator,'calculate_text_metric',side_effect=AssertionError('Read must not compute')), \
     patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
    exit_code=main(call)
elapsed=time.monotonic()-started
assert exit_code==0 and before==snapshot()
rows=list(csv.DictReader((output/'metrics_matrix.csv').open()))
reference=json.loads((Path(__file__).parent.parent/'main-c2f-receiving/read.json').read_text())['rows']
assert len(rows)==len(reference)==25
for row, expected in zip(rows,reference):
    for key in ['metric_id','fiscal_year','unit','period_start','period_end','result_id','status']:
        assert row[key]==str(expected[key]), (key,row,expected)
    assert hashlib.sha256(row['value'].encode()).hexdigest()==expected['value_sha256']
summary={'local_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
         'execution':'uncommitted normal main893 merge', 'main':'893f47610a7ae250e4b809e10f2a8f1d75160ace',
         'seconds_cli_only':elapsed,'exit_code':exit_code,'arguments':call,
         'all_state_files_preserved':len(before), 'rows_equal_prior_read':len(rows),
         'heading_counts':[len(r['value'].splitlines()) for r in rows if r['metric_id']=='D01'],
         'factory_calls':0,'calculator_calls':0,'new_calls':[0,0,0]}
(output/'read-verification.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary))
