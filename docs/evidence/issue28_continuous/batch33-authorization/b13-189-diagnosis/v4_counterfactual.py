"""Offline shape checks using a copied prefix of failed189; no old credit."""
import json
from copy import deepcopy
from pathlib import Path

from vnext.capacity_reference_contract import restore_base_request, upgrade_request
from vnext.capacity_semantic_review import validate_response


evidence = Path(__file__).resolve().parent
path = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls/0189')
old = json.loads((path/'semantic-request.json').read_text())
source = json.loads((path/'source.json').read_text())
response = json.loads((path/'wire/raw-response.bin').read_text())
content = response['choices'][0]['message']['content']
decoder = json.JSONDecoder()
units, _ = decoder.raw_decode(content[content.index('"units":') + len('"units":'):])
position = content.index('"findings":[') + len('"findings":[')
prefix = []
while position < len(content):
    while position < len(content) and content[position] in ' \t\r\n,':
        position += 1
    try:
        row, end = decoder.raw_decode(content, position)
    except json.JSONDecodeError:
        break
    if not isinstance(row, list):
        break
    prefix.append(row)
    position = end
base = restore_base_request(old)
request = upgrade_request(base, compact=True, role_labels=True, relevance_scope=True)
mandatory = {'B443', 'B454', 'B834', 'B1022'}
required_rows = [row for row in prefix if any(ref in mandatory for ref in row[3])]
assert len(required_rows) == 4 and len(units) == 5


def evaluate(rows, statuses=None):
    body = {'units': units if statuses is None else statuses, 'findings': rows}
    return validate_response(request=request,
                             raw_response=json.dumps(body,ensure_ascii=False,
                                                     separators=(',',':')).encode(),
                             source=source)


checked = evaluate(required_rows)
assert not checked['unresolved'] and len(checked['findings']) >= 5
assert any(f['subject'] == 'UNRESOLVED' and
           any(e['source_index'] == 1022 for e in f['resolved_evidence'])
           for f in checked['findings'])
corrected = deepcopy(required_rows)
for row in corrected:
    if 'B1022' in row[3]:
        assert row[1] == 2
        row[1] = 0  # Synthetic valid-answer shape, never old189 credit.
positive = evaluate(corrected)
assert not positive['unresolved'] and not any(
    f['subject'] == 'UNRESOLVED' for f in positive['findings'])
rejections = {}
for name, rows, statuses in (
    ('nonrequired_monetary', required_rows + [next(row for row in prefix
        if row[0] == 'monetary_credit_capacity')], None),
    ('required_missing', required_rows[1:], None),
    ('unit_missing', required_rows, units[:-1]),
):
    try:
        evaluate(rows, statuses)
    except (ValueError, KeyError, TypeError) as error:
        rejections[name] = str(error)
    else:
        raise AssertionError('EXPECTED_REJECTION:' + name)
assert 'B13_V4_NONREQUIRED_BACKGROUND_FINDING' in rejections['nonrequired_monetary']
summary = {'record_type':'ISSUE28_B13_189_V4_COUNTERFACTUAL_OFFLINE_SHAPE_CHECK',
           'status':'PASS_SYNTHETIC_VALID_SUBJECT_SHAPE_AND_THREE_NEGATIVES',
           'source':'ORIGINAL189_TRUNCATED_PREFIX_WITH_SYNTHETIC_COMPLETION',
           'new_v4_request_digest_not_authorized_by_this_check':True,
           'original_189_upgraded':False,
           'positive_complete_response_required_rows':len(required_rows),
           'original_prefix_B1022_subject_unresolved':True,
           'synthetic_positive_B1022_subject_changed_to_target':True,
           'positive_unresolved_count':len(positive['unresolved']),
           'negative_rejections':rejections,
           'new_calls':[0,0,0],
           'real_model_accuracy_proven':False}
(evidence/'v4-counterfactual-summary.json').write_text(
    json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False))
