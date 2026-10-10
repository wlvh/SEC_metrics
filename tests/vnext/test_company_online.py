"""Small count/failure checks; real HTTP-boundary CLI evidence is separate."""
import io,json
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
from tests.vnext.common import REPO_ROOT
from vnext import company_online as online
from vnext.continuous_call_ledger import recorded_ledger
from vnext.canonical import content_hash


class Response(io.BytesIO):
    status=200
    headers={'Content-Type':'application/json'}


class CompanyOnlineTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.ledger=recorded_ledger(root=self.root/'ledger',limits=(0,0,10))
        with self.ledger.locked():self.ledger.snapshot()
        self.context={'company_id':'marriott_international','metric_ids':['B01','B02'],
            'recorded_http_root':str(self.root/'http-fixtures'),'ledger_root':str(self.ledger.root),'maximum_counts':[0,0,10],
            'execution_mode':'RECORDED_TEST_ONLY','purpose':'remaining_development_feasibility',
            'requirement_id':'ordinary-company-capture-v1','requirement_closure_hash':content_hash(value={'recorded':True})}
        self.url='https://data.sec.gov/submissions/CIK0001048286.json'
        self.capture=online.Capture(self.root/'source',self.ledger,self.context,5)

    def test_one_native_http_attempt_uses_existing_count_and_no_retry(self):
        with patch('vnext.recorded_sec_http.RecordedSecHttpClient.reply',return_value=(200,b'{"cik":1048286}',{},'')) as transport:
            self.capture.get(self.url)
            self.capture.get(self.url)
        self.assertEqual(transport.call_count,1)
        self.assertEqual(self.capture.client.config['max_retries'],0)
        with self.ledger.locked():self.assertEqual(self.ledger.snapshot()['counts'],[0,0,1])
        self.assertEqual(len(self.capture.captures),1)
        self.assertTrue((self.root/'source/evidence/requests_log_manifest.json').is_file())

    def test_unknown_remote_blocks_next_claim_and_is_not_zero(self):
        with patch('vnext.recorded_sec_http.RecordedSecHttpClient.reply',side_effect=OSError('unknown remote')) as transport:
            with self.assertRaises(ValueError):self.capture.get(self.url)
        self.assertEqual(transport.call_count,1)
        with self.ledger.locked():
            state=self.ledger.snapshot();self.assertEqual(state['counts'],[0,0,1]);self.assertIn('SEC',state['stopped_channels'])
        self.assertEqual(self.capture.stop,'UNKNOWN_REMOTE_OUTCOME')
        with self.assertRaises(ValueError):self.capture.get(self.url)

    def test_persistence_interrupt_leaves_counted_pending_no_second_transport(self):
        with patch('vnext.recorded_sec_http.RecordedSecHttpClient.reply',return_value=(200,b'{}',{},'')) as transport, \
             patch('vnext.company_online._atomic_json',side_effect=RuntimeError('interrupted plan')):
            with self.assertRaises(RuntimeError):self.capture.get(self.url)
        self.assertEqual(transport.call_count,0)
        with self.ledger.locked():self.assertIn('SEC',self.ledger.snapshot()['stopped_channels'])

    def test_scope_or_limits_cannot_be_changed_by_call_context(self):
        for updated in [{'company_id':'ford_motor'}, {'maximum_counts':[0,0,11]}, {'execution_mode':'LIVE'}]:
            with self.assertRaises(ValueError):online._ledger({**self.context,**updated},'marriott_international',['B01'])

    def test_existing_real_ledger_never_created(self):
        with self.assertRaises(ValueError):online._ledger({**self.context,'ledger_root':str(self.root/'missing')},'marriott_international',['B01'])
        self.assertFalse((self.root/'missing').exists())

    def test_unsupported_metric_rejected_before_sources_or_claim(self):
        with self.assertRaisesRegex(ValueError,'METRIC_NOT_CONNECTED'):
            online.run_online_company(company_id='marriott_international',work_dir=self.root/'task',output_dir=self.root/'out',call_context=self.root/'missing-context',metric_ids=['D03'])
        with self.ledger.locked():self.assertEqual(self.ledger.snapshot()['counts'],[0,0,0])

    def test_claim_is_reported_pending_before_plan_persistence(self):
        context=self.root/'context.json';context.write_text(json.dumps(self.context))
        original=online._atomic_json
        def interrupted(path,value):
            if path.name=='sec-plan.json':raise RuntimeError('plan persistence interrupted')
            return original(path,value)
        for calculate in (False,True):
            # Each mode uses a separate isolated recorded ledger, no real quota.
            if calculate:
                ledger=recorded_ledger(root=self.root/'ledger-run',limits=(0,0,10))
                with ledger.locked():ledger.snapshot()
                context.write_text(json.dumps({**self.context,'ledger_root':str(ledger.root)}))
            output=self.root/'output';output.mkdir(exist_ok=True)
            with patch.object(online,'_atomic_json',side_effect=interrupted), \
                 patch('vnext.company_current_records.run_saved_company',return_value={'output_root':str(output),'status':'FLOW_COMPLETED'}) as calculator, \
                 patch('sec_http.urlopen',side_effect=AssertionError('no HTTP before plan')):
                result=online.run_online_company(company_id='marriott_international',work_dir=self.root/('run' if calculate else 'acquire'),output_dir=output,call_context=context,calculate=calculate)
            self.assertEqual(result['unknown_capture_ordinal'],1)
            self.assertEqual(result['simulated_sec_claims'],1)
            self.assertEqual(result['calls'],{'provider':0,'paid':0,'sec':0})
            self.assertEqual(calculator.call_count,int(calculate))

    def test_prior_metadata_missing_does_not_prevent_current_sources(self):
        from vnext.normal_annual_input import _registry_rows
        for company_id in ('marriott_international','paramount_skydance_paramount_global'):
            company=next(r for r in _registry_rows(repo_root=REPO_ROOT) if r['company_id']==company_id)
            cik=company['primary_cik'];accession=cik.zfill(10)+'-26-000007';document='issuer-20251231.htm'
            payload={'cik':int(cik),'filings':{'recent':{
                'form':['10-K'],'reportDate':['2025-12-31'],'filingDate':['2026-02-10'],
                'accessionNumber':[accession],'primaryDocument':[document]},'files':[]}}
            requested=[]
            class CaptureSpy:
                def get(self,url,**kwargs):
                    requested.append(url)
                    if '/submissions/' in url:raw=json.dumps(payload).encode()
                    elif url.endswith('index.json'):raw=json.dumps({'directory':{'name':'/Archives/edgar/data/'+cik+'/'+accession.replace('-',''),'item':[{'name':document}]}}).encode()
                    else:raw=b'dummy body; discovery only, not semantic acceptance'
                    return {'raw':raw}
            result=online.acquire_financial(CaptureSpy(),company,['B01','B02'])
            self.assertEqual(len(requested),4)
            self.assertTrue(any('/companyfacts/' in u for u in requested))
            self.assertTrue(any(u.endswith(document) for u in requested))
            if company['entity_continuity_status']=='continuous':
                self.assertEqual(result['metric_limitations'][0]['metric_id'],'B02')
                self.assertEqual(result['status'],'SOURCES_PARTIAL_FOR_SELECTED_METRICS')
            else:
                self.assertEqual(result['metric_limitations'],[])
                self.assertEqual(result['status'],'SOURCES_READY_FOR_SELECTED_METRICS')


    def test_new_task_source_directory_does_not_reset_immutable_capture(self):
        with patch('vnext.recorded_sec_http.RecordedSecHttpClient.reply',return_value=(200,b'{}',{},'')) as transport:
            self.capture.get(self.url)
            other=online.Capture(self.root/'different-task-source',self.ledger,self.context,5)
            with self.assertRaisesRegex(ValueError,'ALREADY_CAPTURED_SOURCE_REUSE_REQUIRED'):
                other.get(self.url)
        self.assertEqual(transport.call_count,1)
        with self.ledger.locked():self.assertEqual(self.ledger.snapshot()['counts'],[0,0,1])
        self.assertIsNone(other.pending)


    def test_recorded_context_without_replies_cannot_use_network(self):
        context={k:v for k,v in self.context.items() if k!='recorded_http_root'}
        with patch('sec_http.urlopen',side_effect=AssertionError('recorded must not reach live')) as network:
            with self.assertRaisesRegex(ValueError,'RECORDED_HTTP_INPUT_REQUIRED'):
                online.Capture(self.root/'missing-replies',self.ledger,context,5)
        network.assert_not_called()
        with self.ledger.locked():self.assertEqual(self.ledger.snapshot()['counts'],[0,0,0])


class CompanyCliPeriodRoutingTest(unittest.TestCase):
    """Public argument routing controls; stubs are not computed results."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.base=['run','--company','ford_motor','--metric','B01',
                   '--work-dir',str(self.root/'state'),'--output-dir',str(self.root/'output')]

    def test_online_historical_range_rejected_before_context_or_writer(self):
        from tools.vnext_company import main
        with patch.object(online,'run_online_company',return_value={'status':'FLOW_COMPLETED'}) as run, \
             patch.object(online,'_ledger',side_effect=AssertionError('No ledger')) as ledger, \
             patch('sys.stderr',io.StringIO()),patch('sys.stdout',io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main(self.base+['--period','fiscal-years','--fiscal-year-start','2021',
                     '--fiscal-year-end','2025','--call-context',str(self.root/'not-readable.json')])
        self.assertEqual(caught.exception.code,2);run.assert_not_called();ledger.assert_not_called()
        self.assertEqual(list(self.root.iterdir()),[])

    def test_latest_does_not_silently_ignore_supplied_years(self):
        from tools.vnext_company import main
        for years in (['--fiscal-year-start','2021'],['--fiscal-year-end','2025'],
                      ['--fiscal-year-start','2021','--fiscal-year-end','2025']):
            with self.subTest(years=years), \
                 patch.object(online,'run_online_company',return_value={'status':'FLOW_COMPLETED'}) as run, \
                 patch('sys.stderr',io.StringIO()),patch('sys.stdout',io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    main(self.base+['--call-context',str(self.root/'missing-context')]+years)
                self.assertEqual(caught.exception.code,2);run.assert_not_called()
        self.assertEqual(list(self.root.iterdir()),[])

    def test_latest_saved_source_also_rejects_ignored_year_arguments(self):
        from tools.vnext_company import main
        with patch('vnext.company_local.run_local',return_value={'status':'FLOW_COMPLETED'}) as run, \
             patch('sys.stderr',io.StringIO()),patch('sys.stdout',io.StringIO()):
            with self.assertRaises(SystemExit):
                main(self.base+['--source-root',str(self.root/'source'),'--fiscal-year-start','2021'])
        run.assert_not_called()

    def test_supported_current_online_dispatch_unchanged(self):
        from tools.vnext_company import main
        with patch.object(online,'run_online_company',return_value={'status':'FLOW_COMPLETED'}) as run, \
             patch('sys.stdout',io.StringIO()):
            self.assertEqual(main(self.base+['--call-context',str(self.root/'context')]),0)
        self.assertEqual(run.call_args.kwargs['company_id'],'ford_motor')
        self.assertEqual(run.call_args.kwargs['metric_ids'],['B01'])
        self.assertEqual(run.call_args.kwargs['call_context'],self.root/'context')
        self.assertNotIn('fiscal_year_start',run.call_args.kwargs)

    def test_saved_history_range_forwarded_to_existing_public_consumer(self):
        from tools.vnext_company import main
        with patch('vnext.company_local.run_local',return_value={'status':'FLOW_COMPLETED'}) as run, \
             patch('sys.stdout',io.StringIO()):
            self.assertEqual(main(self.base+['--period','fiscal-years','--fiscal-year-start','2021',
                '--fiscal-year-end','2025','--source-root',str(self.root/'source')]),0)
        self.assertEqual(run.call_args.kwargs['period'],'fiscal-years')
        self.assertEqual(run.call_args.kwargs['fiscal_year_start'],2021)
        self.assertEqual(run.call_args.kwargs['fiscal_year_end'],2025)
