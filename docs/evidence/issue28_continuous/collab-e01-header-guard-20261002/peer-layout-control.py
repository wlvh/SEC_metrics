"""Three bounded layout controls; no saved filing/result impact inferred."""
import json
from pathlib import Path
from vnext.e01_header_document_guard_28_v1 import headed_item_codes

CASES = [
    ('removed_inline', '<div>SEE<span style="display:none">hidden</span>Item 2.01 Completion of Acquisition</div>', []),
    ('laid_out_hidden_block', '<div>SEE<div style="visibility:hidden">blank</div>Item 2.01 Completion of Acquisition</div>', ['2.01']),
    ('separate_visible_paragraphs', '<p>SEE</p><p>Item 2.01 Completion of Acquisition</p>', ['2.01']),
]
rows = [{'case': name, 'raw': html,
         'actual_codes': sorted(headed_item_codes(raw_bytes=html.encode())),
         'expected_from_explicit_block_layout': expected}
        for name, html, expected in CASES]
record = {'tested_source_head': '4835cff7d8e009db0f2341decf93e630a5d381eb',
          'peer_reply': 'https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-5957449714',
          'peer_available_patch': '9caada4ed62d02321d32fbb8249407b992de7154',
          'scope': 'FUNCTION_LEVEL_HTML_CONTROL_NOT_BROWSER_RENDER_OR_FILING_CONTENT_REVIEW',
          'cases': rows, 'confirmed_source_guard_counterexample': True,
          'saved_source_or_result_impact_verified': False,
          'new_business_calls': [0, 0, 0]}
Path(__file__).with_suffix('.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
