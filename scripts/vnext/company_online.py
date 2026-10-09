"""Finite SEC discovery -> ordinary company calculation, with existing counts.

No runtime installation, source trust registry, old calculation or AI transport.
The call context identifies an existing ledger and already applicable purpose;
it never creates a real allowance. Tests replace only sec_http.urlopen.
"""
from pathlib import Path
from contextlib import redirect_stdout
import sys
import fcntl
from urllib.parse import urlsplit

from sec_http import SecHttpClient, validate_request_log_manifest, parse_request_log_rows, write_immutable_bytes
from sec_urls import submissions_url, submissions_file_url, companyfacts_url, accession_document_url, accession_directory_url
from .annual_sources import saved_source
from .canonical import content_hash, strict_json_file, strict_json_loads, sha256_file
from .company_handoff import _atomic_json
from .company_local import absolute
from .normal_source_authority import ROOT
from .normal_annual_input import _registry_rows, select_filing
from .normal_governance_input import _filings, _history_index, history_body_alignment
from .normal_source_requirements import _instance_names

ONLINE_METRICS = frozenset({'B01', 'B02'})


def _need(condition, reason):
    if not condition:
        raise ValueError('COMPANY_ONLINE_' + reason)


def _ledger(context, company, metrics):
    from .continuous_call_ledger import CallLedger, _FACTORY
    root = Path(context['ledger_root']).resolve()
    _need(root.is_dir() and (root/'binding.json').is_file(), 'EXISTING_LEDGER_REQUIRED')
    binding = strict_json_file(path=root/'binding.json')
    _need(context['company_id'] == company and set(metrics) <= set(context['metric_ids']), 'PURPOSE_SCOPE_CHANGED')
    _need(context['purpose'] in binding['purposes'], 'PURPOSE_NOT_IN_EXISTING_ALLOWANCE')
    _need(context['execution_mode'] == binding['execution_mode'], 'MODE_CHANGED')
    _need(context['maximum_counts'] == binding['limits'], 'EXISTING_LIMITS_CHANGED')
    return CallLedger(factory=_FACTORY, root=root, binding=binding, live=binding['execution_mode']=='LIVE')


class Capture:
    def __init__(self, source, ledger, context, maximum):
        self.source, self.ledger, self.context = source, ledger, context
        self.maximum, self.captures, self.stop = maximum, [], None
        self.attempted = set()
        self.pending = None
        self.source.mkdir(parents=True, exist_ok=True)
        registry = self.source/'config/company_registry.csv'
        if registry.exists():
            _need(registry.read_bytes() == (ROOT/'config/company_registry.csv').read_bytes(), 'REGISTRY_CHANGED')
        else:
            write_immutable_bytes(path=registry, content=(ROOT/'config/company_registry.csv').read_bytes())
        self.client = SecHttpClient(workdir=source, config_path=ROOT/'config/sec_config.json',
                                    log_path=source/'evidence/requests_log.csv')
        # One claim corresponds to exactly one HTTP attempt. Do not alter the
        # global client default or rely on its retrying configuration.
        self.client.config = {**self.client.config, 'max_retries':0, 'rate_limit_per_sec':1}
        validate_request_log_manifest(log_path=self.source/'evidence/requests_log.csv')
        for row in parse_request_log_rows(text=(self.source/'evidence/requests_log.csv').read_text()):
            if row['status_code'] in {'403','429'}:
                self.stop='HTTP_'+row['status_code']

    def get(self, url, *, refresh=False, accession=''):
        _need(not self.stop, 'CHANNEL_STOPPED:'+str(self.stop))
        if url in self.attempted:
            return saved_source(repo_root=self.source,url=url,accession=accession)
        log=self.source/'evidence/requests_log.csv'
        rows=parse_request_log_rows(text=log.read_text())
        matching=[r for r in rows if r['source_url']==url]
        if matching and not refresh and (matching[-1]['status_code']!='200' or matching[-1]['error']):
            raise ValueError('LATEST_SOURCE_REQUEST_FAILED:'+url)
        if matching and not refresh:
            return saved_source(repo_root=self.source,url=url,accession=accession)
        _need(len(self.captures)<self.maximum, 'INVOCATION_LIMIT_REACHED')
        self.attempted.add(url)
        request={'method':'GET','url':url,'company_id':self.context['company_id'],
                 'refresh_metadata':refresh,'source_log_before_sha256':sha256_file(path=log)}
        requirement={k:self.context[k] for k in ('requirement_id','requirement_closure_hash')}
        with self.ledger.locked():
            slot,intent=self.ledger.claim(channel='SEC',request_digest=content_hash(value=request),
                requirement=requirement,plan_id=content_hash(value=request),purpose=self.context['purpose'])
            _atomic_json(slot/'sec-plan.json', request)
            self.pending = intent['ordinal']
            before=len(rows)
            path=self.source/'evidence/raw'/content_hash(value={'url':url})[7:]/urlsplit(url).path.rsplit('/',1)[-1]
            # An exception after claim intentionally leaves an incomplete slot;
            # the existing ledger blocks further capture instead of retrying.
            from .sec_rate import rate_scope
            with rate_scope(), redirect_stdout(sys.stderr):
                result=self.client.fetch(url=url,purpose=('LIVE' if self.ledger.live else 'RECORDED_TEST_ONLY')+'_ORDINARY_COMPANY',local_path=path)
            validate_request_log_manifest(log_path=log)
            rows=parse_request_log_rows(text=log.read_text())
            _need(len(rows)==before+1,'HTTP_ATTEMPT_COUNT_CHANGED')
            row=rows[-1]
            stop='UNKNOWN_REMOTE_OUTCOME' if row['status_code']=='0' else 'HTTP_402' if row['status_code']=='402' else ''
            body={'record_type':'ORDINARY_COMPANY_SEC_RECEIPT','intent_id':intent['intent_id'],
                'execution_mode':self.context['execution_mode'],'actual_sec_egress_count':int(self.ledger.live),
                'automatic_retry_count':0,'status':'SUCCEEDED' if row['status_code']=='200' and not row['error'] else 'FAILED_TERMINAL',
                'stop_reason':stop,'source_root':str(self.source),'ledger_row_index':before,'ledger_row':row}
            receipt={**body,'receipt_id':content_hash(value=body)}
            _atomic_json(slot/'sec-receipt.json',receipt)
            self.ledger.finish_sec(path=slot,intent=intent,receipt=receipt)
            self.captures.append(receipt)
            self.pending = None
            self.stop=stop or ('HTTP_'+row['status_code'] if row['status_code'] in {'403','429'} else None)
        return saved_source(repo_root=self.source,url=url,accession=accession)


def acquire_financial(capture, company, metrics):
    """Reuse metadata validation, current filing selection and instance names.

    B02 needs the adjacent annual source as well. Relevant amendments and all
    native instance files are retained, not guessed from a single label.
    """
    cik=int(company['primary_cik'])
    raw=capture.get(submissions_url(cik=cik),refresh=True)['raw']
    payload=strict_json_loads(text=raw.decode('utf-8'))
    rows=_filings(payload,inventory_name='current_submissions')
    for shard in _history_index(payload,str(cik)):
        latest=max((r['reportDate'] for r in rows if r['form']=='10-K'),default='')
        prior=max((r['reportDate'] for r in rows if r['form']=='10-K' and r['reportDate']<latest),default='')
        cutoff=prior if 'B02' in metrics else latest
        if cutoff and shard['filingTo']<cutoff:continue
        source=capture.get(submissions_file_url(file_name=shard['name']),refresh=True)
        body=strict_json_loads(text=source['raw'].decode('utf-8'))
        values=_filings(body,inventory_name=shard['name'])
        _need(history_body_alignment(shard=shard,rows=values) is None,'HISTORY_ALIGNMENT_FAILED')
        rows.extend(values)
    _need(len({r['accessionNumber'] for r in rows})==len(rows),'METADATA_OVERLAP')
    # Existing select_filing remains the authority for the recent current
    # filing; unsupported current history shapes are named limits, not silence.
    selected=select_filing(company=company,submissions=payload)
    filing=selected['filing']
    filings=[filing,*selected['amendments']]
    if 'B02' in metrics:
        prior=max((r['reportDate'] for r in rows if r['form']=='10-K' and r['reportDate']<filing['reportDate']),default='')
        previous=[r for r in rows if r['form']=='10-K' and r['reportDate']==prior]
        _need(len(previous)==1,'PRIOR_ANNUAL_MISSING_OR_AMBIGUOUS')
        filings.extend(previous)
        filings.extend(r for r in rows if r['form']=='10-K/A' and r['reportDate']==prior)
    capture.get(companyfacts_url(cik=cik),refresh=True)
    for current in filings:
        accession=current['accessionNumber']
        capture.get(accession_document_url(cik=cik,accession=accession,document_name=current['primaryDocument']),accession=accession)
        index=capture.get(accession_directory_url(cik=cik,accession=accession),accession=accession)
        for name in _instance_names(strict_json_loads(text=index['raw'].decode('utf-8')),company,current):
            capture.get(accession_document_url(cik=cik,accession=accession,document_name=name),accession=accession)
    return {'status':'SOURCES_READY_FOR_SELECTED_METRICS','filing':filing,
            'metric_ids':list(metrics),'all_39_sources_proven':False}


def run_online_company(*, company_id, work_dir, output_dir, call_context, metric_ids=None,max_sec_requests=20, calculate=True):
    from .company_current_records import run_saved_company
    metrics=list(metric_ids or sorted(ONLINE_METRICS))
    _need(metrics and len(metrics)==len(set(metrics)) and set(metrics)<=ONLINE_METRICS,'METRIC_NOT_CONNECTED')
    _need(type(max_sec_requests)is int and 0<=max_sec_requests<=120,'INVOCATION_LIMIT_INVALID')
    work,outputs=absolute(work_dir),absolute(output_dir)
    for root in (ROOT.resolve(),outputs):
        _need(work!=root and root not in work.parents and work not in root.parents,'WORK_ROOT_OVERLAP')
    context=strict_json_file(path=Path(call_context))
    ledger=_ledger(context,company_id,metrics)
    work.mkdir(parents=True,exist_ok=True)
    _need(not(work/'local-company.json').exists(),'OLD_TASK_REQUIRES_ORIGINAL_ENTRY')
    with (work/'online.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        config=work/'online-company.json'
        identity={'company_id':company_id,'source_root':str(work/'sources'),
                  'ledger_root':str(ledger.root),'binding_id':ledger.binding['binding_id']}
        if config.exists():_need(strict_json_file(path=config)==identity,'TASK_IDENTITY_CHANGED')
        else:_atomic_json(config,identity)
        capture=Capture(work/'sources',ledger,context,max_sec_requests)
        try: discovery=acquire_financial(capture,next(r for r in _registry_rows(repo_root=ROOT) if r['company_id']==company_id),metrics)
        except Exception as error:
            discovery={'status':'SOURCE_DISCOVERY_FAILED','error_type':type(error).__name__,'reason':str(error)}
        if not calculate:
            result={'record_type':'ORDINARY_COMPANY_ACQUISITION_V1','company_id':company_id,
                'source_root':str(capture.source),'discovery':discovery,
                'status':'SOURCES_READY' if discovery['status']=='SOURCES_READY_FOR_SELECTED_METRICS' else 'SOURCES_PARTIAL',
                'calls':{'provider':0,'paid':0,'sec':(None if capture.pending is not None else len(capture.captures)) if ledger.live else 0},
                'simulated_sec_claims':len(capture.captures)+int(capture.pending is not None) if not ledger.live else 0,
                'execution_mode':context['execution_mode'],'metric_executed':False,
                'unknown_capture_ordinal':capture.pending,'production_authorized':False}
            _atomic_json(work/'latest-acquisition.json',result)
            return result
        # Current source failures remain in the request log: the real update
        # controller refuses them, while preserving old results as history.
        calculated=run_saved_company(company_id=company_id,source_root=capture.source,
            work_dir=work/'company-state',output_dir=outputs,metric_ids=metrics)
        calls={'provider':0,'paid':0,'sec':(None if capture.pending is not None else len(capture.captures)) if ledger.live else 0}
        result={**calculated,'source_mode':'ONLINE_DISCOVERY_WITH_ORDINARY_RECORDS','discovery':discovery,'calls':calls,'simulated_sec_claims':len(capture.captures)+int(capture.pending is not None) if not ledger.live else 0,
                'execution_mode':context['execution_mode'],'unknown_capture_ordinal':capture.pending,'source_capture_receipts':capture.captures}
        if discovery['status']=='SOURCE_DISCOVERY_FAILED':result['status']='FLOW_COMPLETED_WITH_LIMITATIONS'
        _atomic_json(Path(result['output_root'])/'run_summary.json',result)
        return result
