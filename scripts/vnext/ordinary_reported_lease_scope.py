"""Explicit reported-lease source successor; the old default stays byte-identical.

This adds a proved inclusion relationship to an already verified partial
debt source case. It never turns that case into a complete B06 ratio.
"""
from pathlib import Path

from . import ordinary_special_debt_scope as inherited
from .canonical import content_hash, sha256_file
from .financial_structured import _InlineTableIndex
from .industrial_lease_relation import inspect_inclusion
from .normal_annual_input_v2 import exact_json_value
from .normal_source_authority import ROOT
from .sources import resolve_repository_file


def _reported(scope, *, sources, annual):
    if scope is None:
        return None
    body = {k: v for k, v in scope.items() if k != 'scope_source_id'}
    body['record_type'] = 'ORDINARY_B06_SPECIAL_SCOPE_SOURCE_V2'
    if body['scope_class'] == 'industrial':
        native = {kind: inherited.native(source, annual) for kind, source in sources.items()}
        index = _InlineTableIndex(sources['primary']['raw_bytes'])
        index.feed(sources['primary']['raw_bytes'].decode('utf-8-sig')); index.close()
        body['lease_inclusion'] = inspect_inclusion(primary=sources['primary'],
            parsed=native['primary'][0], reported_components=body['reported_components'],
            lease_reports=body['native_finance_lease_reports'], native_sources=native,
            index=index, sources=sources)
        reason = 'INDUSTRIAL_DEBT_SET_COMPLETENESS_NOT_ESTABLISHED'
        if reason not in body['limitations']:
            body['limitations'] = [*body['limitations'], reason]
    else:
        body['lease_inclusion'] = {'status': 'NOT_APPLICABLE_TO_BANK_SCOPE'}
    body = exact_json_value(body)
    return {**body, 'scope_source_id': content_hash(value=body)}


def inspect_reported_lease_scope(*, primary, xml, annual, financial_institution, rules):
    scope = inherited.inspect_special_scope(primary=primary, xml=xml, annual=annual,
        financial_institution=financial_institution, rules=rules)
    return _reported(scope, sources={'primary': primary, 'xml': xml}, annual=annual)


def _case_sources(case, source_root):
    """Reopen only the exact originals already bound to the inherited case."""
    sources = {}
    for kind in ('primary', 'xml'):
        references = [row['source_reference']
            for component in case['selection']['scope_source']['reported_components'].values()
            for row in component['source_reports'][kind]]
        unique = {r['source_reference_id']: r for r in references}
        inherited.need(len(unique) == 1, 'RELATION_ORIGINAL_NOT_UNIQUE:' + kind)
        ref = next(iter(unique.values()))
        paths = {p['request_repo_relative_path'] for p in case['source_proofs']
            if p['source_url'] == ref['source_url'] and p['accession'] == ref['accession']
            and 'sha256:' + p['content_sha256'] == ref['raw_asset_id']}
        inherited.need(len(paths) == 1, 'RELATION_ORIGINAL_PROOF_NOT_UNIQUE:' + kind)
        path = resolve_repository_file(repo_root=source_root, repo_relative_path=next(iter(paths)))
        sources[kind] = {'raw_bytes': path.read_bytes(), 'source_reference': ref}
    return sources


def prepare_reported_lease_case(*, repo_root: Path, company_id: str):
    case = inherited.prepare_special_debt_case(repo_root=repo_root, company_id=company_id)
    if case is None:
        return None
    original = case['input_binding']['original_source_input']
    annual = original['prepared_annual_input']
    scope = _reported(case['selection']['scope_source'],
        sources=_case_sources(case, repo_root), annual=annual)
    processing = {p: sha256_file(path=ROOT / p) for p in (
        'scripts/vnext/ordinary_special_debt_scope.py',
        'scripts/vnext/ordinary_reported_lease_scope.py',
        'scripts/vnext/industrial_lease_relation.py',
        'scripts/vnext/b06_inclusive_table.py')}
    return {**case,
        'input_binding': {**case['input_binding'], 'scope_source': scope,
            'original_source_input': {**original, 'reported_relations': True,
                'relation_processing_files': processing}},
        'selection': {**case['selection'], 'scope_source': scope, 'reasons': scope['limitations']}}
