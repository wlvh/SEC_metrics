"""Compare the complete installed historical cascade with a recorded baseline.

Usage: python3 script.py <restored source-inputs> <baseline probe.json> <out.json>
The code root is the current working directory. This makes no Run and admits
no content reading; it compares the stage, selection audit and four result
fields, not every native record's identity. Live calls fail in the guard.
"""
import hashlib
import gzip
import json
import sys
from pathlib import Path

repo = Path.cwd()
sys.path[:0] = [str(repo / 'scripts'), str(repo)]
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import historical_debt_results as debt
from vnext.historical_run_replay import run_checks_replay_once
from vnext.historical_derivation_memo import derived_once_per_state
from vnext.historical_xbrl_parse import xbrl_parsed_once
from vnext.normal_history_plan import checkpoint_replayed_once
from vnext.normal_period_selection import resolve_period_selection

root, baseline_path, output = map(Path, sys.argv[1:4])
baseline = json.loads(gzip.decompress(baseline_path.read_bytes()) if baseline_path.suffix == '.gz'
                      else baseline_path.read_bytes())
rows = {}
with original_sources_only(), run_checks_replay_once(), derived_once_per_state(), xbrl_parsed_once(), checkpoint_replayed_once():
    for position in baseline['positions']:
        company, end = position.rsplit(':', 1)
        selection = resolve_period_selection(repo_root=root, company_id=company, report_end=end)
        try:
            comp = debt.resolve_historical_debt_metric(repo_root=root, company_id=company,
                                                       metric_id='B06', period_selection=selection)
            row = {'stage': comp.get('cascade_stage'), 'reason': comp.get('selection'),
                   'result': {k: comp['result'].get(k) for k in ['value', 'quality', 'publication', 'reason_code']}}
        except Exception as error:
            row = {'error': type(error).__name__ + ':' + str(error)}
        # A persisted baseline uses JSON arrays where the resolver may return
        # tuples. Compare the persisted representation on both sides.
        row = json.loads(json.dumps(row))
        rows[position] = {'baseline': baseline['rows'][position]['base'], 'successor': row}
        print(position, 'MOVED' if rows[position]['baseline'] != row else 'SAME', flush=True)
        output.with_suffix('.partial.json').write_text(json.dumps(rows, indent=1) + '\n')
moved = [k for k,v in rows.items() if v['baseline'] != v['successor']]
record = {'record_type':'ISSUE_47_B06_NOTE_FORMS_FRAME_EFFECT', 'positions':len(rows),
          'moved':moved, 'errors':[k for k,v in rows.items() if 'error' in v['successor']],
          'baseline_sha256':'sha256:' + hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
          'code_sha256':{'scripts/vnext/' + name:'sha256:' + hashlib.sha256((repo/'scripts/vnext'/name).read_bytes()).hexdigest()
              for name in ['historical_debt_results.py', 'historical_note_carrying.py']},
          'rows':rows, 'calls':{'provider':0,'paid':0,'sec':0}, 'native_result_credit':False}
output.write_text(json.dumps(record, indent=1) + '\n')
print(json.dumps({k:record[k] for k in ['positions','moved','errors','calls']}))
