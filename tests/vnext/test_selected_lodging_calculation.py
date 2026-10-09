"""Small actual table-to-Calculator cases; no company installation or network."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.vnext import test_selected_lodging_source as support
from vnext import lodging_table_source as source
from vnext.normal_lodging_results import calculate_selected_lodging_metric, _spec
from vnext.calculator import CalculationError
from vnext.traits import repository_company_traits


ROOT = Path(__file__).resolve().parents[2]


class SelectedLodgingCalculationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        support.SelectedLodgingSourceTest.setUpClass()
        cls.args = support.SelectedLodgingSourceTest().arguments()
        cls.args['reference'].update(source_reference_id='sha256:'+'1'*64,
            source_role='target_primary',document_name='annual.htm')
        cls.args['filing'].update(form='10-K',filingDate='2026-02-01')
        cls.component = source.read_selected_lodging_source(**cls.args)
        cls.specs = {m: _spec(ROOT,m) for m in ('B10','B11')}
        cls.traits = repository_company_traits(repo_root=ROOT,company_id='marriott_international')
        cls.prepared = {'company_id':'example','entity':'1','filing':cls.args['filing'],
                        'table_input':{'target_period':cls.args['period']}}

    def calculate(self, metric='B10', **changes):
        args = {'prepared':copy.deepcopy(self.prepared),'component':copy.deepcopy(self.component),
                'reference':copy.deepcopy(self.args['reference']), 'metric_id':metric,
                'spec':self.specs[metric],'traits':self.traits}
        args.update(changes)
        return calculate_selected_lodging_metric(**args)

    def test_both_metrics_reach_calculator_without_selecting_or_reading_again(self):
        with patch('vnext.normal_lodging_results.prepare_saved_annual_input',side_effect=AssertionError('No selection')), \
             patch.object(source,'prepare_saved_lodging_source',side_effect=AssertionError('No reread')):
            for metric,value,unit in [('B10','0.693','ratio'),('B11','128.8','USD')]:
                with self.subTest(metric=metric):
                    r=self.calculate(metric);result=r['result'];obs=r['observation']
                    self.assertEqual((result['value'],result['unit'],result['quality']),(value,unit,'EXACT'))
                    self.assertEqual((result['period_start'],result['period_end']),('2025-01-01','2025-12-31'))
                    fact=self.component['selection']['facts'][metric]
                    self.assertEqual(obs['source_binding']['reported_raw_text'],fact['source_witnesses']['amount']['raw_text'])
                    self.assertEqual(obs['source_binding']['table_locator'],fact['source_witnesses']['amount']['locator'])
                    self.assertEqual(r['selection']['source_witnesses'],fact['source_witnesses'])

    def test_changed_period_or_scope_is_rejected_before_calculation(self):
        for field,value in [('period',{'fiscal_year':2024,'period_start':'2024-01-01','period_end':'2024-12-31'}),
                            ('scope',{'geography':'domestic'})]:
            c=copy.deepcopy(self.component);c['selection']['facts']['B10'][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'SCOPE_OR_PERIOD_CONFLICT'):
                self.calculate(component=c)

    def test_company_accession_reference_and_metric_conflicts_are_rejected(self):
        for field,value in [('company_id','another'),('accession','another'),('source_reference_id','sha256:'+'2'*64)]:
            reference={**self.args['reference'],field:value}
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'SOURCE_CONFLICT'):
                self.calculate(reference=reference)
        with self.assertRaisesRegex(ValueError,'METRIC_CONFLICT'):
            self.calculate(spec=self.specs['B11'])

    def test_wrong_unit_cannot_become_an_exact_result(self):
        c=copy.deepcopy(self.component);c['selection']['facts']['B10']['unit']='USD'
        with self.assertRaisesRegex(CalculationError,'binding differs: unit'):
            self.calculate(component=c)

    def test_selected_noncalendar_interval_is_preserved_through_calculation(self):
        raw=support.HTML.replace(b'2024',b'2023').replace(b'2025',b'2024')
        args=support.SelectedLodgingSourceTest().arguments(raw,year=2024,start='2024-02-04',end='2025-02-01')
        args['reference'].update(self.args['reference'],raw_asset_id=args['blob']['raw_asset_id'])
        args['filing'].update(form='10-K',filingDate='2025-03-01')
        component=source.read_selected_lodging_source(**args)
        prepared={**self.prepared,'filing':args['filing'],'table_input':{'target_period':args['period']}}
        result=self.calculate(prepared=prepared,component=component,reference=args['reference'])['result']
        self.assertEqual((result['period_start'],result['period_end']),('2024-02-04','2025-02-01'))
        self.assertEqual(result['value'],'0.693')


if __name__=='__main__':unittest.main()
