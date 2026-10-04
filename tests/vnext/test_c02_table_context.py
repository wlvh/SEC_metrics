"""Keep table membership columns and all source texts through the model view."""
import copy
import hashlib
import unittest

from tests.vnext import common  # Initialize the existing vnext import path.
from tools.prepare_c02_table_context import assert_matches, expanded_view, model_view
from vnext.table_grid import build_table_grid


class C02TableContextTest(unittest.TestCase):
    def fixture(self):
        raw = (b'<html><body><p>Board members</p><table><tr><th rowspan="2">Director</th>'
               b'<th colspan="2">Committees</th></tr><tr><th>Alpha</th><th>Beta</th></tr>'
               b'<tr><td>Alice &amp; Bob</td><td>Member</td><td></td></tr>'
               b'<tr><td>Carol</td><td></td><td>Member</td></tr>'
               b'<tr><th colspan="3"></th></tr></table>'
               b'<table><tr><td>Unrelated compensation table</td><td>10</td></tr></table></body></html>')
        raw_id = 'sha256:' + hashlib.sha256(raw).hexdigest()
        grid = build_table_grid(html_bytes=raw, parent_raw_asset_ids=[raw_id], storage_uri='evidence/test.json')
        document = {'raw_asset_id': raw_id, 'blocks': [
            {'block_index': i, 'text': text} for i, text in enumerate(
                ('Board members', 'Director Committees', 'Alpha Beta', 'Alice & Bob Member',
                 'Carol Member', 'Unrelated compensation table 10'))]}
        return document, grid

    def test_same_member_word_stays_in_different_committee_columns(self):
        document, grid = self.fixture()
        blocks, tables = expanded_view(model_view(document, grid))
        self.assertEqual([b['text'] for b in document['blocks']], blocks)
        cells = tables[0]['cells']
        self.assertEqual(('Member', False), cells[2][1])
        self.assertEqual(('', False), cells[2][2])
        self.assertEqual(('', False), cells[3][1])
        self.assertEqual(('Member', False), cells[3][2])
        self.assertEqual(('Director', True), cells[1][0])
        self.assertEqual([('', True)] * 3, cells[4])
        # The full source is retained, including the irrelevant table.
        self.assertEqual(2, len(tables))
        self.assertEqual(('10', False), tables[1]['cells'][0][1])

    def test_column_swap_preserves_count_but_cannot_pass_source_comparison(self):
        document, grid = self.fixture()
        view = model_view(document, grid)
        member = next(x for x in view['tables'][0]['x'] if x[:2] == [2, 1])
        member[1] = 2
        with self.assertRaisesRegex(ValueError, 'EXPANDED_GRID_CHANGED'):
            assert_matches(view, document, grid)

    def test_drop_table_block_or_member_refuses(self):
        document, grid = self.fixture()
        original = model_view(document, grid)
        variants = []
        dropped_table = copy.deepcopy(original); dropped_table['tables'].pop(); variants.append(dropped_table)
        dropped_block = copy.deepcopy(original); dropped_block['block_count'] -= 1; variants.append(dropped_block)
        dropped_cell = copy.deepcopy(original)
        dropped_cell['tables'][0]['x'] = [x for x in dropped_cell['tables'][0]['x'] if x[:2] != [3, 2]]
        variants.append(dropped_cell)
        for view in variants:
            with self.subTest(view=view):
                with self.assertRaisesRegex(ValueError, 'CHANGED'):
                    assert_matches(view, document, grid)

    def test_block_ids_are_stable_and_changed_spelling_is_rejected(self):
        document, grid = self.fixture()
        view = model_view(document, grid)
        self.assertEqual(document['blocks'][0]['text'], view['strings'][0])
        self.assertGreater(len(view['strings']), view['block_count'])
        view['strings'][0] = 'Different body'
        with self.assertRaisesRegex(ValueError, 'BLOCK_TEXT_OR_ORDER_CHANGED'):
            assert_matches(view, document, grid)

    def test_overlapping_or_escaping_spans_and_boolean_indices_refuse(self):
        document, grid = self.fixture()
        original = model_view(document, grid)
        for kind in ('overlap', 'escape', 'bool'):
            view = copy.deepcopy(original)
            if kind == 'overlap': view['tables'][0]['x'].append(view['tables'][0]['x'][0])
            if kind == 'escape': view['geometry'][view['tables'][0]['g']][0] = 100
            if kind == 'bool': view['block_count'] = True
            with self.subTest(kind=kind):
                with self.assertRaises(ValueError): expanded_view(view)

    def test_cross_source_grid_and_noncontiguous_block_numbers_refuse(self):
        document, grid = self.fixture()
        changed = copy.deepcopy(document); changed['raw_asset_id'] = 'sha256:' + '1' * 64
        with self.assertRaisesRegex(ValueError, 'RAW_PARENT_CHANGED'):
            model_view(changed, grid)
        changed = copy.deepcopy(document); changed['blocks'][1]['block_index'] = 7
        with self.assertRaisesRegex(ValueError, 'BLOCK_ORDER'):
            model_view(changed, grid)


if __name__ == '__main__':
    unittest.main()
