"""Formal company dispatch uses the selected metric's actual processing inputs."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.vnext_company import main
from vnext import historical_statement_cases as cases


class StatementMetricDispatchTest(unittest.TestCase):
    def test_formal_history_cli_selects_specific_dependencies_without_running_factories(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'sources';source.mkdir()
            with patch('vnext.company_current_records.run_saved_company',return_value={
                    'status':'FLOW_COMPLETED','verification_scope':'CONSTRUCTED_DISPATCH_ONLY'}) as writer, \
                 patch.object(cases,'prepare_historical_statement_year_case',
                    side_effect=AssertionError('Dispatch must not precompute a case')), \
                 redirect_stdout(io.StringIO()):
                code=main(['run','--company','paramount_skydance_paramount_global','--source-root',str(source),
                    '--work-dir',str(root/'state'),'--output-dir',str(root/'out'),'--period','fiscal-years',
                    '--fiscal-year-start','2024','--fiscal-year-end','2024',
                    '--metric','B04','--metric','B05','--metric','B07'])
            self.assertEqual(code,0)
            args=writer.call_args.kwargs
            for metric in ('B04','B05','B07'):
                self.assertEqual(args['processing_files_by_metric'][metric],
                    cases.processing_files_for_statement_metric(metric))
                self.assertIn('scripts/vnext/statement_metric_amendment.py',
                              args['processing_files_by_metric'][metric])
            self.assertIn('scripts/vnext/financial_duration.py',
                          args['processing_files_by_metric']['B05'])
            self.assertEqual(args['fiscal_years'],[2024])

    def test_new_property_version_reprocesses_only_consuming_metrics(self):
        from tests.vnext import test_ordinary_current_update as fixture
        update=fixture.update;state=fixture.CurrentUpdateTest();state.setUp()
        self.addCleanup(state.doCleanups);created=[]
        def create(**kwargs):
            metric=kwargs['metric_id'];path=kwargs['output_root'];path.mkdir(parents=True)
            created.append(metric)
            value={'manifest':{'company_id':'marriott_international','metric_id':metric,
                'source_proofs':[state.proof]},'result':{'company_id':'marriott_international',
                'metric_id':metric,'publication':'PUBLISHED','period_end':'2025-12-31',
                'result_id':metric+'-constructed-'+str(len(created))}}
            state.records[str(path)]=value;return value
        def run(metric):
            return update.run_once(state_root=state.root/metric,source_root=fixture.ROOT,
                company_id='marriott_international',metric_id=metric,
                processing_files=cases.processing_files_for_statement_metric(metric))
        with patch.object(update,'create_saved_result',side_effect=create):
            first={m:run(m) for m in ('B04','B05','B07','B01')}
            original_hash=update.sha256_file
            def changed(*,path):
                return 'changed-property-code' if Path(path).name=='statement_metric_amendment.py' else original_hash(path=path)
            with patch.object(update,'sha256_file',side_effect=changed):
                second={m:run(m) for m in ('B04','B05','B07','B01')}
                self.assertTrue(second['B04']['calculation_performed'])
                self.assertTrue(second['B07']['calculation_performed'])
                self.assertTrue(second['B05']['calculation_performed'])
                self.assertEqual(second['B01']['status'],'NO_SOURCE_CONTENT_CHANGE')
                self.assertEqual(second['B01']['result_id'],first['B01']['result_id'])
                with patch.object(update,'create_saved_result',side_effect=AssertionError('No repeated calculation')):
                    repeated={m:run(m) for m in ('B04','B05','B07','B01')}
                self.assertTrue(all(not v['calculation_performed'] for v in repeated.values()))
        self.assertEqual(created,['B04','B05','B07','B01','B04','B05','B07'])


if __name__=='__main__':unittest.main()
