"""Two resource responsibilities cannot silently drop or duplicate source."""
import copy
import unittest

from tests.vnext import test_c02_table_context as context
from tools.prepare_c02_table_context import model_view
from tools.prepare_c02_responsibility_packets import assert_union, packets


class C02ResponsibilityPacketsTest(unittest.TestCase):
    def source(self):
        return model_view(*context.C02TableContextTest().fixture())

    def test_whole_tables_and_all_text_keep_global_identities(self):
        view = self.source()
        parts = packets(view)
        assert_union(view, parts)
        self.assertEqual(view['strings'], parts[0]['strings'])
        self.assertEqual(view['strings'], parts[1]['strings'])
        self.assertEqual('table_000002', parts[1]['owned_tables'][0]['i'])
        self.assertEqual(view['tables'], [t for p in parts for t in p['owned_tables']])

    def test_missing_duplicate_mutated_table_or_dictionary_rejects(self):
        view = self.source()
        for kind in ['missing', 'duplicate', 'cell', 'text', 'identity']:
            parts = copy.deepcopy(packets(view))
            if kind == 'missing': parts[1]['owned_tables'].pop()
            elif kind == 'duplicate': parts[1]['owned_tables'] = parts[0]['owned_tables']
            elif kind == 'cell': parts[1]['owned_tables'][0]['x'].pop()
            elif kind == 'text': parts[1]['strings'][0] = 'Changed source'
            else: parts[1]['full_source_view_sha256'] = '0' * 64
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED|UNION_CHANGED'):
                assert_union(view, parts)

    def test_block_gap_overlap_and_boolean_bounds_reject(self):
        view = self.source()
        for start in [0, 2, 4, True]:
            parts = copy.deepcopy(packets(view))
            parts[1]['owned_text_block_range'][0] = start
            with self.subTest(start=start), self.assertRaisesRegex(ValueError, 'BLOCK_UNION_CHANGED'):
                assert_union(view, parts)

    def test_owned_extra_strings_keep_original_indices_and_full_union(self):
        view = self.source()
        parts = packets(view, 'owned')
        assert_union(view, parts)
        self.assertEqual(view['strings'][:view['block_count']], parts[1]['strings'])
        extras = {i: text for p in parts for i, text in p['cell_strings']}
        self.assertEqual(dict(enumerate(view['strings'][view['block_count']:], view['block_count'])), extras)
        changed = copy.deepcopy(parts)
        owner = next(p for p in changed if p['cell_strings'])
        owner['cell_strings'][0][1] = 'Changed cell text'
        with self.assertRaisesRegex(ValueError, 'CELL_DICTIONARY_CHANGED'):
            assert_union(view, changed)


if __name__ == '__main__':
    unittest.main()
