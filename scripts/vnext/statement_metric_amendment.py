"""Explicit original-statement input properties for B04/B07, not metric results.

The existing Part III identity/note/cover/correction checks are reused. The
target's approved component roles stay explicit; no old income property or
annual scope is relabelled as proof for all financial metrics.
"""
import re

from .canonical import content_hash, sha256_bytes, sha256_file, strict_json_file
from .normal_source_authority import ROOT
from .ordinary_income_input import inspect_income_amendment, need, POLICY_PATH
from .instant_balance_amendment_v2 import _text_units
from .table_grid import build_table_grid

CATALOG_PATH='catalog/deterministic_metrics.json'
_COMPONENT_SUBJECTS={
    'net_income':r'\b(?:(?:net|consolidated) (?:income|loss|earnings|profit)|profit (?:or|and) loss)\b',
    'operating_income':r'\boperating (?:income|loss|profit)\b',
    'interest_expense':r'\b(?:interest (?:expense|cost)|borrowing costs?)\b',
    'pretax_income':r'\b(?:(?:pre-tax|pretax) (?:income|loss|profit)|(?:income|loss|profit) before (?:income )?tax(?:es)?)\b',
    'aggregate_nonoperating':r'\b(?:non-?operating (?:income|expense|loss)|other non-?operating (?:income|expense))\b',
}
_INPUT_CLASSES={'B04':'ORIGINAL_REPORTED_NET_INCOME_VALUES',
                'B07':'ORIGINAL_INTEREST_COVERAGE_COMPONENT_VALUES'}
_INCOME_TAX_SUBJECT=r'\b(?:income taxes?|tax expense|tax benefit)\b'
# Complete row labels differ from references to adjusted compensation targets.
# Parenthetical income/loss is retained as meaning, not stripped globally.
_ROW_LABELS={
    'net_income':r'(?:net (?:income|loss|earnings|profit)(?:\s*\((?:loss|income)\))?|profit (?:or|and) loss)',
    'operating_income':r'operating (?:income|loss|profit)(?:\s*\((?:loss|income)\))?',
    'interest_expense':r'(?:interest (?:expense|cost)(?:,?\s*(?:net|non-operating))?|borrowing costs?)',
    'pretax_income':r'(?:(?:pre-tax|pretax) (?:income|loss|profit)|(?:income|loss|profit) before (?:income )?tax(?:es)?)',
    'aggregate_nonoperating':r'(?:other )?non-?operating (?:income|expense|loss)(?:\s*\((?:expense|income)\))?(?:,?\s*net)?',
}
# Amounts in a component-bearing paragraph require an additional relation
# proof. They cannot silently become unchanged merely because no financial
# statement or financial native fact was added. This is a refusal boundary,
# not extraction of a number or an English semantic classification.
_AMOUNT=re.compile(r'(?:[$€£]\s*[-(]?\s*\d|\bUSD\s*[-(]?\s*\d|\d[\d,.]*\s*(?:million|billion|thousand)\b)',re.I)


def inspect_statement_metric_amendment(scope,raw,*,metric_id):
    """Return a bound, metric-specific property or a concrete unresolved cause.

    Original quantity selection, unit/period/subject, continuity, scope,
    coverage and Calculator checks remain the consumer's responsibilities.
    Default income and instant-balance callers do not consume this API.
    """
    need(metric_id in _INPUT_CLASSES,'STATEMENT_METRIC_NOT_SUPPORTED')
    doc=scope['amendment']['document']
    need(doc['raw_asset_id']=='sha256:'+sha256_bytes(content=raw)
         and doc['byte_length']==len(raw),'STATEMENT_AMENDMENT_RAW_BINDING_CHANGED')
    definition=strict_json_file(path=ROOT/CATALOG_PATH)['metrics'][metric_id]
    components=[c for branch in definition['branches'] for c in branch['components']]
    roles=sorted({c['role'] for c in components})
    expected=({'net_income'} if metric_id=='B04' else
              {'operating_income','interest_expense','pretax_income','aggregate_nonoperating'})
    need(set(roles)==expected and all(c['unit']=='USD' and c['period_role']=='current_annual'
        and c['accession_role']=='current' and c['dimension_policy']=='NONE' for c in components),
        'STATEMENT_COMPONENT_DEFINITION_CHANGED')
    subjects='(?:'+'|'.join(_COMPONENT_SUBJECTS[role] for role in roles)+')'
    rules=strict_json_file(path=ROOT/POLICY_PATH)
    typed_rules={**rules,'input_class':_INPUT_CLASSES[metric_id],
        'income_subject_pattern':'(?:'+rules['income_subject_pattern']+'|'+subjects+'|'+_INCOME_TAX_SUBJECT+')'}
    checked=inspect_income_amendment(scope,raw,typed_rules)
    reported=[]
    # An already proved identical-original link correction has no additional
    # statement content. Part III needs this further whole-document check.
    if not checked.get('inherited_statement_proof'):
        for unit in _text_units(doc['blocks'],raw,scope.get('note_layout','blocks-v1')):
            matched=[role for role in roles if re.search(_COMPONENT_SUBJECTS[role],unit['text'],re.I)]
            if matched and _AMOUNT.search(unit['text']):
                reported.append({'component_roles':matched,'source_unit':unit})
        grid=build_table_grid(html_bytes=raw,parent_raw_asset_ids=[doc['raw_asset_id']],
                             storage_uri='derived/statement-amendment-tables.json')
        for table in grid['tables']:
            for row in table['rows']:
                cells=[c for c in row['cells'] if c['is_origin']]
                matched=[role for role in roles if any(re.fullmatch(
                    _ROW_LABELS[role]+r'(?:\s*\([0-9]+\)|\s*\*)?',
                    ' '.join(c['text'].split()),re.I) for c in cells)]
                numeric=[c for c in cells if re.fullmatch(
                    r'(?:USD\s*|[$€£]\s*)?[-(]?\s*\d[\d,.]*\s*\)?',c['text'].strip(),re.I)
                    or c['text'].strip() in {'-','–','—'}]
                if matched and numeric:
                    reported.append({'component_roles':matched,'table_id':table['table_id'],
                        'row':row,'source_reference':doc['source_reference']})
    need(not reported,'STATEMENT_COMPONENT_DISCLOSURE_RELATION_UNRESOLVED',details=reported)
    body={'record_type':'ORIGINAL_STATEMENT_METRIC_INPUT_PROPERTY','schema_version':1,
        'metric_id':metric_id,'input_class':_INPUT_CLASSES[metric_id],
        'original_scope_id':scope['scope_id'],'covered_component_roles':roles,
        'metric_definition_sha256':sha256_file(path=ROOT/CATALOG_PATH),
        'amendment_raw_sha256':sha256_bytes(content=raw),
        'original_source_reference':scope['original']['document']['source_reference'],
        'amendment_source_reference':doc['source_reference'],'source_property':checked,
        'additional_component_disclosures':reported,
        'original_scope_reclassified':False,'annual_continuity_proven':False,
        'debt_completeness_proven':False,'metric_result_created':False,
        'source_acquisition_credit':False,'production_authorized':False}
    return {**body,'property_id':content_hash(value=body)}
