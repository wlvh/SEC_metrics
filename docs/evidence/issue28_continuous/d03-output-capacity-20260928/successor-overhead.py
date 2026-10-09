"""Measure the one JPMorgan source-anchor successor's extra response field."""
import json
import socket
from pathlib import Path
from unittest.mock import patch

from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.continuous_request_context import _load_tokenizer
from vnext.d03_native_preparation import prepare_native_input

from census import compact, scenarios


HERE = Path(__file__).resolve().parent
previous = json.loads((HERE / 'census.json').read_text())
row = next(x for x in previous['companies'] if x['company_id'] == 'jpmorgan_chase')
with original_sources_only(), \
     patch.object(socket.socket, 'connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')), \
     patch.object(socket, 'getaddrinfo',
                  side_effect=AssertionError('DNS_FORBIDDEN')), \
     patch('sec_http.urlopen',
           side_effect=AssertionError('SEC_HTTP_FORBIDDEN')):
    prepared = prepare_native_input(company_id='jpmorgan_chase')
assert prepared['source_id'] == row['source_id']
groups = [x for x in prepared['groups'] if x['source_anchor_successor']]
assert len(groups) == 1
group = groups[0]
request = group['effective_request']
prior = row['groups'][group['group_index']]
assert request['request_id'] == prior['request_id']
anchors = request['source_fact_candidates']
assert len(anchors) == 1
tokenizer, fallback = _load_tokenizer()
assert tokenizer is not None and fallback is None
tokens = {}
for name, value in scenarios(request).items():
    result = dict(value)
    result['candidate_reviews'] = ([] if name != 'one_minimal_finding_per_required'
        else [{'candidate_id': a['candidate_id'], 'unit_id': a['unit_id'],
               'finding_indices': [0]} for a in anchors])
    tokens[name] = len(tokenizer.encode(compact(result),
                    add_special_tokens=False).ids)
summary = {'record_type': 'D03_SINGLE_SUCCESSOR_RESPONSE_FIELD_OVERHEAD',
    'company_id': 'jpmorgan_chase', 'source_id': prepared['source_id'],
    'group_index': group['group_index'], 'request_id': request['request_id'],
    'source_fact_candidate_count': len(anchors),
    'prior_scenario_tokens_without_extra_field': prior['scenario_tokens'],
    'scenario_tokens_with_candidate_reviews_field': tokens,
    'output_token_limit': 4096,
    'bare_and_context_scenarios_are_schema_floor_not_accepted_answers': True,
    'one_finding_scenario_is_synthetic_not_semantically_approved': True,
    'actual_model_output_observed': False, 'real_calls': [0, 0, 0]}
(HERE / 'successor-overhead.json').write_text(json.dumps(summary,
    ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'group_index': group['group_index'],
    'candidate_count': len(anchors), 'prior_tokens': prior['scenario_tokens'],
    'corrected_tokens': tokens}, sort_keys=True), flush=True)
