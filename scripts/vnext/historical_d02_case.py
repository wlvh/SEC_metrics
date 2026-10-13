"""Public D02 saved-answer factory; the existing business core owns excerpts."""
from pathlib import Path

from .canonical import strict_json_file
from .d02_reviewed_source import (prepare_historical_legal_sources,
    finish_historical_legal_case,ReviewedLegalSourceError,PROCESSING_FILES as SOURCE_FILES)
from .saved_legal_review import read_saved_legal_review,PROCESSING_FILES as READER_FILES

METRICS=('D02',)
PROCESSING_FILES=tuple(dict.fromkeys((*SOURCE_FILES,*READER_FILES,
    'scripts/vnext/historical_d02_case.py')))


def _answer_roots(root):
    """Index retained complete requests, never reconstruct a pool from answers."""
    root=Path(root)
    if not root.is_dir():
        raise ReviewedLegalSourceError('D02_SAVED_REVIEW_ROOT_MISSING','MODEL_RESPONSE_REQUIRED')
    if (root/'semantic-request.json').is_file():
        candidates=[root]
    else:
        directory=root/'calls' if (root/'calls').is_dir() else root
        candidates=sorted(p for p in directory.iterdir()
                          if p.is_dir() and (p/'semantic-request.json').is_file())
    indexed={}
    for path in candidates:
        request=strict_json_file(path=path/'semantic-request.json')
        if request.get('record_type')!='D02_ITEM_8_LEGAL_REVIEW_REQUEST':
            continue
        identity=request['request_id']
        if identity in indexed:
            raise ReviewedLegalSourceError('D02_SAVED_REVIEW_REQUEST_DUPLICATED')
        indexed[identity]=path
    return indexed


def historical_d02_factory(*, saved_review_root):
    """Use a separately supplied read-only answer root, not a SEC source pack."""
    answers=Path(saved_review_root).expanduser().resolve()
    def prepare(*,repo_root,company_id,metric_id,fiscal_year):
        if metric_id!='D02':
            raise ReviewedLegalSourceError('D02_SAVED_REVIEW_METRIC_REQUIRED')
        source=Path(repo_root).resolve()
        if answers==source or answers in source.parents or source in answers.parents:
            raise ReviewedLegalSourceError('D02_SAVED_ANSWERS_MUST_BE_SEPARATE_FROM_SEC_SOURCES')
        bundle=prepare_historical_legal_sources(repo_root=repo_root,
            company_id=company_id,fiscal_year=fiscal_year)
        indexed=_answer_roots(answers)
        missing=[r['request_id'] for r in bundle['requests'] if r['request_id'] not in indexed]
        if missing:
            raise ReviewedLegalSourceError('D02_COMPLETE_SAVED_REVIEW_SET_MISSING:'+','.join(missing),
                'MODEL_RESPONSE_REQUIRED')
        reviews=[]
        for request in bundle['requests']:
            review=read_saved_legal_review(call_root=indexed[request['request_id']],request=request)
            if review['original_execution_mode']!='LIVE':
                raise ReviewedLegalSourceError('D02_RECORDED_RESPONSE_HAS_NO_BUSINESS_EXECUTION_CREDIT',
                    'MODEL_RESPONSE_REQUIRED')
            if not review['usage_known']:
                raise ReviewedLegalSourceError('D02_SAVED_RESPONSE_TOKEN_USAGE_UNKNOWN',
                    'MODEL_RESPONSE_UNKNOWN')
            reviews.append(review)
        return finish_historical_legal_case(bundle=bundle,reviews=reviews)
    return prepare


def invalid_saved_review_factory(*, error):
    """Raise a package preparation error inside the D02 update boundary.

    Its distinct producer identity prevents an earlier empty-answer success
    from being reused when package validation now fails. The normal shared
    controller records the original error; no result or paid call is made.
    """
    def invalid_package(*,repo_root,company_id,metric_id,fiscal_year):
        raise error
    return invalid_package


def saved_review_input_paths(*, saved_review_root, company_id):
    """Bind the small dedicated answer set as ordinary processing inputs.

    Multi-company or multi-period ledgers are not a calculation package.
    Their selected original members may be exported read-only separately;
    this does not copy a ledger, create quota or alter an old call.
    """
    indexed=_answer_roots(Path(saved_review_root).expanduser().resolve())
    selected=[];periods=set()
    for path in indexed.values():
        request=strict_json_file(path=path/'semantic-request.json')
        if request['company_id']!=company_id:
            raise ReviewedLegalSourceError('D02_SAVED_REVIEW_PACKAGE_OTHER_COMPANY')
        periods.add(request['period_end'])
        terminal=strict_json_file(path=path/'terminal.json')
        providers=[p for p in terminal['evidence'] if p.startswith('invocation_control/requests/') and p.endswith('.bin')]
        if len(providers)!=1:
            raise ReviewedLegalSourceError('D02_SAVED_REVIEW_PROVIDER_REQUEST_AMBIGUOUS')
        selected.extend(path/p for p in ('semantic-request.json','source.json','terminal.json',
            'wire/journal.json','wire/raw-response.bin','wire/assistant-output.bin',providers[0]))
    if len(periods)>1:
        raise ReviewedLegalSourceError('D02_SAVED_REVIEW_PACKAGE_MULTIPLE_PERIODS')
    # An empty but existing package can still produce a precise missing-set
    # observation. Include its selection parameter through the factory path.
    return tuple(selected)
