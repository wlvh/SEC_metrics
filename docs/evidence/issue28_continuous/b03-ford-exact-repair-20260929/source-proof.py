"""Save a compact, reproducible reading of Ford's original split."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from vnext.b03_exact_impairment_relation import prove_exact_impairment_relation
from vnext.normal_run_v3 import prepare_case

case = prepare_case(data_root=ROOT, company_id='ford_motor_company',
                    metric_id='B03')
proof = prove_exact_impairment_relation(case=case, data_root=ROOT)
body = {'company_id': 'ford_motor_company', 'fiscal_year': 2025,
    'original_selected_result_id_retained': case['results']['B03']['result_id'],
    'original_selected_result_value_not_current_credit':
        case['results']['B03']['value'],
    'source_relation': proof,
    'derived_native_credit_claimed_by_this_read': False}
(HERE/'source-proof.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'proof_id': proof['proof_id'],
    'gross': proof['selected_total_usd'],
    'impairment_depreciation': proof['exact_impairment_depreciation_usd'],
    'remaining': proof['arithmetically_remaining_da_usd']},
    sort_keys=True))
