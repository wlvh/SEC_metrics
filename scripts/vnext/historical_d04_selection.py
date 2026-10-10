"""Select an existing saved D04 source by the issuer's actual annual input.

No source, request, answer, ledger or result is created here. Public replay owns
original execution/response checks and semantic aggregation. This module only
connects historical annual selection to exact members of an existing package.
"""
from pathlib import Path
import tarfile

from .canonical import strict_json_loads
from .historical_annual_input import prepare_historical_annual_input
from .normal_period_selection import resolve_period_selection
from .normal_source_authority import ROOT
from .native_unit_index import validate_request_partition


class HistoricalD04SelectionError(ValueError):
    def __init__(self, reason, category='SOURCE_INTEGRITY_ERROR'):
        super().__init__(reason)
        self.category = category


def _need(condition, reason, category='SOURCE_INTEGRITY_ERROR'):
    if not condition:
        raise HistoricalD04SelectionError(reason, category)


def _coordinate(annual):
    try:
        return (annual['company_id'], str(int(annual['entity'])),
                annual['filing']['accessionNumber'],
                *(annual['table_input']['target_period'][key] for key in
                  ('fiscal_year', 'period_start', 'period_end')))
    except (KeyError, TypeError, ValueError) as error:
        raise HistoricalD04SelectionError('HISTORICAL_D04_SOURCE_COORDINATE_INVALID') from error


def select_saved_d04_source(*, prepared_annual, sources):
    """One exact original source; another year's success cannot replace it."""
    wanted = _coordinate(prepared_annual)
    matches = [source for source in sources
        if source.get('metric_id') == 'D04'
        and source.get('record_type') == 'D04_NATIVE_COMPLETE_SEMANTIC_SOURCE'
        and source.get('company_id') == wanted[0]
        and _coordinate(source['prepared_annual_input']) == wanted]
    _need(len(matches) == 1,
          'HISTORICAL_D04_SAVED_SOURCE_MISSING_OR_AMBIGUOUS:'+str(len(matches)),
          'SOURCE_UNAVAILABLE' if not matches else 'SOURCE_INTEGRITY_ERROR')
    return matches[0]


def prepare_historical_d04_selection(*, source_root, company_id, fiscal_year,
                                     saved_call_package):
    """Prepare selected annual and point to an unmodified original call group."""
    selected = resolve_period_selection(repo_root=Path(source_root),
        company_id=company_id, fiscal_year=fiscal_year, rules_root=ROOT)
    annual = prepare_historical_annual_input(repo_root=Path(source_root),
        company_id=company_id, period_selection=selected, rules_root=ROOT)
    package = Path(saved_call_package)
    _need(package.is_file(), 'HISTORICAL_D04_SAVED_PACKAGE_MISSING', 'SOURCE_UNAVAILABLE')
    with tarfile.open(package, 'r:gz') as archive:
        # Read named regular members only. Never extract or execute the archive.
        entries = [member for member in archive.getmembers() if member.isfile()]
        members = {member.name: member for member in entries}
        _need(len(members) == len(entries), 'HISTORICAL_D04_DUPLICATE_PACKAGE_MEMBER')
        _need('root/binding.json' in members, 'HISTORICAL_D04_ORIGINAL_BINDING_MISSING')
        def read(name):
            _need(name in members, 'HISTORICAL_D04_PACKAGE_MEMBER_MISSING:'+name)
            return strict_json_loads(text=archive.extractfile(members[name]).read().decode('utf-8'))
        source_members = sorted(name for name in members
            if len(name.split('/')) == 4 and name.startswith('root/calls/')
            and name.endswith('/source.json') and name.split('/')[2].isdigit())
        sources, paths = {}, {}
        for name in source_members:
            source = read(name)
            identity = source.get('semantic_source_id')
            if source.get('metric_id') != 'D04':
                continue
            _need(type(identity) is str, 'HISTORICAL_D04_SOURCE_ID_MISSING')
            _need(identity not in sources or sources[identity] == source,
                  'HISTORICAL_D04_SAME_SOURCE_ID_CHANGED')
            sources[identity] = source
            paths.setdefault(identity, []).append(name)
        source = select_saved_d04_source(prepared_annual=annual,
                                          sources=list(sources.values()))
        source_id = source['semantic_source_id']
        calls = []
        for source_name in paths[source_id]:
            directory = source_name.rsplit('/', 1)[0]
            request_name = directory+'/semantic-request.json'
            request = read(request_name)
            _need(request.get('company_id') == company_id
                  and request.get('metric_id') == 'D04'
                  and request.get('target_cik') == annual['entity']
                  and request.get('target_period') == annual['table_input']['target_period'],
                  'HISTORICAL_D04_REQUEST_COORDINATE_CHANGED')
            calls.append({'ordinal': int(directory.split('/')[-1]),
                          'source_member': source_name,
                          'request_member': request_name,
                          'request': request})
        order = {identity: index for index, identity in enumerate(source['required_unit_ids'])}
        calls.sort(key=lambda call: order[call['request']['units'][0]['unit_id']])
        validate_request_partition(source, [call['request'] for call in calls])
    return {'record_type': 'HISTORICAL_D04_SAVED_SELECTION',
        'prepared_annual_input': annual, 'period_selection': selected,
        'original_source': source, 'original_source_id': source_id,
        'saved_call_package': str(package.resolve()),
        'original_call_members': [{key:value for key,value in call.items() if key != 'request'}
                                  for call in calls],
        'metric_executed': False, 'reply_or_ledger_modified': False,
        'new_calls': {'provider':0, 'paid':0, 'sec':0}}
