"""Source grouping keeps exact historical boundaries and resource failures."""
from unittest.mock import patch
import json
import tarfile
import unittest

from vnext import r6_semantic_source as source


def original_groups(rows, render, document, kind):
    groups, current = [], []
    for row in rows:
        trial = current + [row]
        if current and len(source._bytes(render(trial))) > source.POLICY['max_unit_payload_bytes']:
            groups.append(current)
            current = [row]
        else:
            current = trial
        source._need(len(source._bytes(render(current))) <= (
            source.POLICY['max_single_object_payload_bytes'] if len(current) == 1 else source.POLICY['max_unit_payload_bytes']),
            'SEMANTIC_SINGLE_SOURCE_OBJECT_EXCEEDS_INPUT_BOUND')
    if current:
        groups.append(current)
    return [source._seal_unit(document, kind, render(group), i) for i, group in enumerate(groups)]


class SemanticSourceGroupingTest(unittest.TestCase):
    def test_exact_old_boundaries_for_text_shared_maps_and_large_single_objects(self):
        rules = {**source.POLICY, 'max_unit_payload_bytes': 400, 'max_single_object_payload_bytes': 1300}
        with patch.object(source, 'POLICY', rules):
            for rows in ([], ['abc'], ['é' * (i % 13 + 1) for i in range(100)], ['x' * 500, 'a', 'b'],
                         ['a', 'b', 'x' * 500], ['x' * 180] * 9):
                for render in (lambda values: {'blocks': values},
                               lambda values: {'facts': values, 'contexts': {str(len(v)): v for v in values}}):
                    with self.subTest(rows=len(rows)):
                        self.assertEqual(source._group(rows, render, 'document', 'TEST'),
                                         original_groups(rows, render, 'document', 'TEST'))
            with self.assertRaisesRegex(ValueError, 'EXCEEDS_INPUT_BOUND'):
                source._group(['ok', 'x' * 1301], lambda values: {'blocks': values}, 'document', 'TEST')

    def test_many_small_rows_do_not_revalidate_every_growing_prefix(self):
        rows = ['same'] * 1000
        calls = []
        def render(values):
            calls.append(len(values))
            return {'blocks': values}
        result = source._group(rows, render, 'document', 'TEST')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['payload']['blocks'], rows)
        self.assertLess(len(calls), 30)


class SemanticSourceGroupingMaterialTest(unittest.TestCase):
    def test_actual_two_company_units_are_identical_to_preoptimization_material(self):
        from tests.vnext.test_normal_zero_ai_results import original_sources_only
        from vnext.capacity_semantic_source import prepare_capacity_semantic_source
        from vnext.normal_source_authority import ROOT
        with tarfile.open(ROOT / 'docs/evidence/issue28_continuous/resume-2026-09-14/b13-complete-source.tar.gz') as archive:
            for member in archive.getmembers():
                old = json.load(archive.extractfile(member))
                with original_sources_only():
                    current = prepare_capacity_semantic_source(repo_root=ROOT, company_id=old['company_id'])
                self.assertEqual(current['units'], old['units'])
                self.assertEqual(current['required_unit_ids'], old['required_unit_ids'])
                self.assertEqual(current['documents'], old['documents'])


if __name__ == '__main__':
    unittest.main()
