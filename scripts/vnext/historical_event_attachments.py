"""Declare only explicitly reviewed incorporated attachments from saved parents.

This prepares successor inputs. It never fetches, calculates, rebinds an old
request, or grants budget; the original counted capture/resume gates remain.
"""
import hashlib
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from .canonical import strict_json_file
from .annual_sources import AnnualUpdateError, saved_source
from .normal_source_authority import ROOT

POLICY_PATH = 'docs/evidence/issue47_history/event-attachment-declarations-v1.json'


def _need(ok, reason):
    if not ok:
        raise ValueError('HISTORICAL_EVENT_ATTACHMENT_'+reason)


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            values = [value for name, value in attrs if name.lower() == 'href']
            _need(len(values) <= 1, 'DUPLICATE_LINK_ATTRIBUTE')
            self.hrefs.extend(values)



def _read_saved(*, repo_root, url, accession=''):
    """Existing saved-source result and latest-failure semantics, no capture."""
    try:
        item = saved_source(repo_root=repo_root, url=url, accession=accession)
    except AnnualUpdateError as error:
        if not str(error).startswith('LATEST_SOURCE_REQUEST_FAILED'):
            raise
        return None, 'LATEST_SOURCE_REQUEST_FAILED'
    return (item, None) if item is not None else (None, 'SAVED_SOURCE_MISSING')


def attachment_dependencies(*, repo_root, company_id, requirements, report_ends):
    policy = strict_json_file(path=ROOT/POLICY_PATH)
    items = [item for item in policy['items'] if item['company_id'] == company_id
             and item['report_end'] in report_ends]
    dependencies = []
    for item in items:
        parents = [row for row in requirements if row['source_url'] == item['parent_url']
                   and row['accession'] == item['accession']
                   and row['dependency_class'] == 'FISCAL_EVENT_FILING']
        _need(len(parents) == 1, 'PARENT_NOT_DECLARED_IN_FRAME')
        parent, reason = _read_saved(repo_root=repo_root, url=item['parent_url'], accession=item['accession'])
        _need(parent is not None, 'PARENT_UNAVAILABLE:'+str(reason))
        from .ordinary_source_authority import verify_ordinary_source_proofs
        verify_ordinary_source_proofs(data_root=repo_root, proofs=[parent['proof']])
        raw = parent['raw']
        _need(hashlib.sha256(raw).hexdigest() == item['parent_sha256'], 'PARENT_BYTES_CHANGED')
        span = raw[item['anchor_start']:item['anchor_end']]
        _need(hashlib.sha256(span).hexdigest() == item['anchor_sha256'], 'ANCHOR_BYTES_CHANGED')
        parser = _Links()
        parser.feed(span.decode('utf-8', errors='strict'))
        _need(parser.hrefs == [item['literal_href']], 'EXACT_LINK_CHANGED')
        target = urljoin(item['parent_url'], parser.hrefs[0])
        endpoint = urlsplit(target)
        _need(target == item['source_url'] and endpoint.scheme == 'https'
              and endpoint.netloc == 'www.sec.gov' and not endpoint.query and not endpoint.fragment,
              'TARGET_OUTSIDE_REVIEWED_SCOPE')
        saved, missing = _read_saved(repo_root=repo_root, url=target, accession=item['accession'])
        if saved is not None:
            verify_ordinary_source_proofs(data_root=repo_root, proofs=[saved['proof']])
        dependencies.append({'source_url': target, 'media_type': 'text/html',
            'accession': item['accession'], 'document_name': endpoint.path.rsplit('/', 1)[-1],
            'dependency_class': 'FISCAL_EVENT_FILING', 'source_roles': [item['source_role']],
            'consumers': ['period:'+item['report_end'], 'E01_SUCCESSOR_INCORPORATED_ATTACHMENT'],
            'parent_source_url': item['parent_url'], 'parent_sha256': item['parent_sha256'],
            'parent_item_id': item['item_id'], 'declared_by': POLICY_PATH,
            'primary_cik': parents[0]['primary_cik'], 'registrant_cik': parents[0]['registrant_cik'],
            'saved_status': 'VERIFIED_SAVED_SOURCE' if saved is not None else 'MISSING_SAVED_SOURCE',
            'saved_reason': missing, 'new_acquisition_required': saved is None,
            'acquisition_kind': 'FIRST_ACQUISITION' if saved is None else None,
            'source_acquisition_credit': False,
            'retry_count': 0, 'maximum_sec_attempts': item['maximum_sec_attempts'],
            'source_contract_scope': 'SUCCESSOR_INPUT_ONLY_NO_OLD_REQUEST_OR_RUN_REBINDING'})
    return dependencies
