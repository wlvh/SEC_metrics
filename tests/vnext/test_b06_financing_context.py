"""Full development inputs stay separate from an extracted debt answer."""
import json
import hashlib
from pathlib import Path
import tempfile
import unittest

from tests.vnext import common
from tools.prepare_b06_financing_context import load_packet, request_for
from tools.prepare_c02_table_context import model_view
from tests.vnext import test_c02_table_context as c02_context
from vnext.continuous_request_context import render_prompt


class B06FinancingContextTest(unittest.TestCase):
    def directory(self, root):
        document, grid = c02_context.C02TableContextTest().fixture()
        view = model_view(document, grid)
        native = {'primary': [], 'xml': []}
        packet = {'primary_text_and_table_layout': view,
                  'current_potential_financing_native_facts': native}
        artifacts = {'document.json': document, 'table-grid.json': grid,
                     'view.json': view, 'native-current-financing-facts.json': native,
                     'source-only-package.json': packet, 'normal-b06-source-binding.json': {}}
        digests = {}
        for name, value in artifacts.items():
            raw = json.dumps(value).encode()
            (root / name).write_bytes(raw)
            digests[name] = hashlib.sha256(raw).hexdigest()
        metadata = {'artifacts': digests, 'block_count': view['block_count'],
                    'table_count': len(grid['tables']), 'expanded_cells': sum(
                        t['row_count'] * t['column_count'] for t in grid['tables'])}
        (root / 'metadata.json').write_text(json.dumps(metadata))
        return packet, metadata

    def test_changed_bytes_missing_artifact_and_mismatched_packet_reject(self):
        for kind in ['changed_bytes', 'missing_artifact', 'changed_packet', 'counts']:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                packet, metadata = self.directory(root)
                self.assertEqual(packet, load_packet(root)[0])
                if kind == 'changed_bytes':
                    (root / 'view.json').write_text('{}')
                elif kind == 'missing_artifact':
                    del metadata['artifacts']['view.json']
                elif kind == 'changed_packet':
                    packet['primary_text_and_table_layout']['strings'][0] = 'Omitted actual source text'
                    raw = json.dumps(packet).encode()
                    (root / 'source-only-package.json').write_bytes(raw)
                    metadata['artifacts']['source-only-package.json'] = hashlib.sha256(raw).hexdigest()
                else:
                    metadata['block_count'] -= 1
                (root / 'metadata.json').write_text(json.dumps(metadata))
                with self.assertRaisesRegex(ValueError, 'B06_DEVELOPMENT_.*CHANGED'):
                    load_packet(root)

    def test_unrelated_source_and_unnormalized_native_text_are_retained(self):
        packet = {'company_id': 'test', 'primary_text_and_table_layout': {
            'strings': ['  Leading and trailing text  ', 'Unrelated tax disclosure'],
            'block_count': 2, 'geometry': [], 'tables': []},
            'current_potential_financing_native_facts': {
                'primary': [{'ordinal': 1, 'source_text': 'no', 'normalized_source_value': '0'}],
                'xml': [{'ordinal': 1, 'source_text': '0', 'normalized_source_value': '0'}]}}
        request = request_for(packet, {'included': ['recognized_borrowings']})
        self.assertEqual(packet, json.loads(request['messages'][1]['content']))
        self.assertIn('Leading and trailing text', request['messages'][1]['content'])
        self.assertNotIn('reference_answer', request['messages'][1]['content'])

    def test_complete_request_has_the_existing_measurement_envelope(self):
        body = request_for({'all_source': ['text', 'tables', 'native']}, {'included': []})
        rendered = render_prompt(json.dumps(body).encode(), provider='deepseek',
                                 model='deepseek-flash', api='chat_completions')
        self.assertIn(body['messages'][0]['content'], rendered)
        self.assertIn(body['messages'][1]['content'], rendered)
        self.assertEqual(4096, body['max_tokens'])
        self.assertIn('complete=false', body['messages'][0]['content'])


if __name__ == '__main__':
    unittest.main()
