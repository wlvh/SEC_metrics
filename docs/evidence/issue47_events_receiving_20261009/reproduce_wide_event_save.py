"""Reproduce the already observed wide-event save, from saved sources only."""
import argparse
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext.historical_event_cases import prepare_historical_event_year_case
from vnext.ordinary_saved_result import save_calculated_case
from vnext.deterministic_router import shared_xbrl_parses

parser = argparse.ArgumentParser()
parser.add_argument('--source-root', type=Path, required=True)
parser.add_argument('--output-root', type=Path, required=True)
args = parser.parse_args()
if args.output_root.exists():
    raise SystemExit('Choose a new output directory')
args.output_root.mkdir(parents=True)
with patch.object(socket.socket, 'connect', side_effect=AssertionError('No business network')), shared_xbrl_parses():
    case = prepare_historical_event_year_case(repo_root=args.source_root.resolve(),
        company_id='paramount_skydance_paramount_global', metric_id='C01', fiscal_year=2025)
    (args.output_root / 'case.json').write_text(json.dumps(case, ensure_ascii=False, indent=2) + '\n')
    try:
        saved = save_calculated_case(source_root=args.source_root.resolve(),
            output_root=args.output_root / 'result', company_id=case['prepared_annual_input']['company_id'],
            metric_id='C01', case=case)
    except ValueError as error:
        (args.output_root / 'failure.json').write_text(json.dumps({'error_type':type(error).__name__,
            'reason':str(error), 'source_root':str(args.source_root.resolve())}, indent=2) + '\n')
        raise
    print(saved['result']['result_id'])
