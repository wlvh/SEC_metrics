"""Independent regression for semantic redraw identity of indexed responses.

These are signature probes over synthetic factory requests. Modified proposals
are not source admission or authorization to execute a changed contract.
"""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from tests.vnext.test_native_request_variants import synthetic_source
from vnext.canonical import content_hash
from vnext.continuous_semantic_calls import request_digest
from vnext.native_unit_index import reconstruct_requests, upgrade_request


def reseal(request):
    request['request_id'] = content_hash(value={k:v for k,v in request.items() if k != 'request_id'})
    return request


class IndexedSemanticIdentityTest(unittest.TestCase):
    def setUp(self):
        source, _ = synthetic_source()
        self.base = reconstruct_requests(source)[0]
        self.policy = SimpleNamespace(model='deepseek-flash')

    def test_mechanical_source_identity_cannot_authorize_indexed_redraw(self):
        changed = deepcopy(self.base)
        changed['source_id'] = content_hash(value='Changed code/provenance identity only')
        reseal(changed)
        self.assertNotEqual(self.base['request_id'], changed['request_id'])
        self.assertEqual(request_digest(self.base, self.policy), request_digest(changed, self.policy))
        left, right = upgrade_request(self.base), upgrade_request(changed)
        self.assertNotEqual(left['indexed_unit_contract']['base_request_id'],
                            right['indexed_unit_contract']['base_request_id'])
        # The full request remains different and bound by HTTP/plan/receipt;
        # the separate semantic no-redraw identity must still be identical.
        self.assertNotEqual(left['request_id'], right['request_id'])
        self.assertEqual(request_digest(left, self.policy), request_digest(right, self.policy))

    def test_actual_source_prompt_and_output_contract_changes_remain_distinct(self):
        changed_payload = deepcopy(self.base)
        payload = changed_payload['units'][0]['payload']
        text_column = payload['row_layout']['columns'].index('text')
        next(iter(payload['blocks'].values()))[text_column] += ' A different source statement.'
        changed_prompt = deepcopy(self.base)
        changed_prompt['system_prompt'] += '\nA different interpretation task is required.'
        changed_output = deepcopy(self.base)
        changed_output['response_protocol']['json_schema']['properties']['units']['items']['properties'][
            'findings']['items']['properties']['reason']['maxLength'] -= 1
        for label, changed in [('source_payload', changed_payload), ('prompt', changed_prompt), ('output_contract', changed_output)]:
            reseal(changed)
            for transform in (lambda request: request, upgrade_request):
                with self.subTest(change=label, indexed=transform is upgrade_request):
                    self.assertNotEqual(request_digest(transform(self.base), self.policy),
                                        request_digest(transform(changed), self.policy))

    def test_base_and_indexed_output_contracts_have_distinct_execution_semantics(self):
        self.assertNotEqual(request_digest(self.base, self.policy),
                            request_digest(upgrade_request(self.base), self.policy))


if __name__ == '__main__':
    unittest.main()
