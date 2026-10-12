"""Constructed wrong-column control; no financial result or remote request."""
import json
from tests.vnext.test_single_segment_revenue import original, SingleSegmentRevenueTest
from tests.vnext.test_selected_reported_revenue_v2 import changed

source, annual = original()
raw = source['raw_bytes'].replace(b'<td>2025</td>', b'<td colspan="2">2025</td>')
raw = raw.replace(b'<td>Year Ended December 31,</td><td></td>',
                  b'<td>Year Ended December 31,</td><td colspan="2"></td>')
raw = raw.replace(b'>58496</ix:nonFraction></td>',
                  b'>58496</ix:nonFraction></td><td></td>')
for label in (b'Cost of sales', b'Net income'):
    raw = raw.replace(b'<td>'+label+b'</td><td>', b'<td>'+label+b'</td><td></td><td>')
try:
    result = SingleSegmentRevenueTest().scope(changed(source, raw), annual)
    print(json.dumps({'complete_scope_proven': result['complete_scope_proven']}))
except ValueError as error:
    print(json.dumps({'refused': str(error)}))
