"""B13 inputs reuse the complete annual text/native source assembler.

The small candidate packet remains useful navigation. It cannot stand in for
the complete supplied source, especially amended, hidden or continued facts.
This adapter changes the question, not the inherited source set or its credit.
"""
from pathlib import Path
import re
from xml.sax.saxutils import quoteattr

from .canonical import content_hash, sha256_file, strict_json_file
from .capacity_utilization_source import POLICY_PATH, policy, need
from .normal_source_authority import ROOT
from .r6_semantic_source import prepare_d04_semantic_source
from .r6_semantic_review import _source_items
from .governance_signals import _FactAttributes


def native_capacity_roles(units):
    """Separate disclosed monetary facilities from physical quantity roles.

    A native name is only a candidate. The finite credit-facility relation also
    requires its real unit declaration to resolve to an undivided ISO currency.
    Other candidates stay unresolved; no missing production amount is inferred.
    """
    rows = []
    for unit in units:
        if unit['kind'] != 'NATIVE_FACTS':
            continue
        payload = unit['payload']
        for row in payload['facts']:
            fact = row['fact']
            if re.search(r'capacity|utilization|actualproduction|productionvolume',
                         fact['qualified_name'], re.I) is None:
                continue
            declared = None
            if fact['unit_ref']:
                definition = payload['units'][fact['unit_ref']]
                namespaces = payload['namespace_environments'][definition['namespace_environment_id']]
                attributes = ' '.join(('xmlns:' + k if k else 'xmlns') + '=' + quoteattr(v)
                                      for k, v in namespaces.items())
                parser = _FactAttributes()
                parser.feed('<root ' + attributes + '>' + definition['raw_xml'] + '</root>')
                parser.close()
                need(parser.unit is None and parser.measure is None,
                     'B13_NATIVE_UNIT_INCOMPLETE')
                declared = parser.units.get(fact['unit_ref'])
            namespace, concept = row['expanded_concept']
            monetary = (re.fullmatch(r'https?://fasb\.org/us-gaap/\d{4}', namespace) is not None
                        and concept == 'LineOfCreditFacilityMaximumBorrowingCapacity'
                        and declared is not None and not declared['divided']
                        and len(declared['measures']) == 1
                        and declared['measures'][0][0] == 'http://www.xbrl.org/2003/iso4217'
                        and re.fullmatch(r'[A-Z]{3}', declared['measures'][0][1]) is not None)
            body = {'unit_id': unit['unit_id'], 'source_index': fact['ordinal'],
                    'expanded_concept': row['expanded_concept'], 'original_fact': fact,
                    'declared_unit': declared,
                    'role': 'MONETARY_CREDIT_FACILITY_CAPACITY' if monetary else 'ROLE_UNRESOLVED',
                    'production_or_physical_capacity_quantity': False if monetary else None,
                    'numeric_pair_absence_asserted': False}
            rows.append({**body, 'role_assessment_id': content_hash(value=body)})
    return rows


def capacity_source_from_complete_annual(*, source, rules):
    """Project source navigation without deleting any document or source unit.

    This pure helper carries no source admission; the public factory below
    rebuilds the supplied packet through the existing authenticated assembler.
    """
    need(source['semantic_source_id'] == content_hash(value={
        k: v for k, v in source.items() if k != 'semantic_source_id'}),
        'B13_COMPLETE_SOURCE_BINDING_CHANGED')
    need(source['source_serialization_complete'], 'B13_SOURCE_SERIALIZATION_INCOMPLETE')
    need([u['unit_id'] for u in source['units']] == source['required_unit_ids']
         and len(set(source['required_unit_ids'])) == len(source['units']),
         'B13_COMPLETE_SOURCE_UNIT_SET_CHANGED')
    by_document = {}
    for unit in source['units']:
        by_document.setdefault(unit['document_id'], []).append(unit)
    need(set(by_document) == {d['document_id'] for d in source['documents']},
         'B13_COMPLETE_SOURCE_DOCUMENT_SET_CHANGED')
    related = re.compile(rules['related_production_capacity_pattern'], re.I)
    production = re.compile(rules['possible_actual_production_pattern'], re.I)
    # Navigation only: a miss never removes the item from the interpretation
    # input or establishes that a production quantity is not disclosed.
    navigation = []
    for document in source['documents']:
        units = by_document[document['document_id']]
        need([u['unit_id'] for u in units] == document['source_unit_ids'],
             'B13_DOCUMENT_UNIT_SET_CHANGED')
        visible_count = 0
        native_count = 0
        supplement_count = 0
        for unit in units:
            kind, items = _source_items(unit)
            if kind == 'VISIBLE_BLOCK':
                visible_count += len(items)
            elif kind == 'NATIVE_FACT':
                native_count += len(items)
            else:
                supplement_count += sum(1 + len(item['nested_objects']) for item in items.values())
            for index, item in items.items():
                text = item.get('text', item.get('raw_xml', ''))
                signals = []
                if related.search(text):
                    signals.append('CAPACITY_LANGUAGE')
                if production.search(text):
                    signals.append('POSSIBLE_PRODUCTION_LANGUAGE')
                if kind == 'NATIVE_FACT' and re.search(
                        r'capacity|utilization|actualproduction|productionvolume',
                        item['qualified_name'], re.I):
                    signals.append('NATIVE_CONCEPT_NAME_ONLY')
                if signals:
                    navigation.append({'unit_id': unit['unit_id'], 'kind': kind,
                                       'source_index': index, 'signals': signals})
        need(visible_count == document['visible_block_count'],
             'B13_VISIBLE_SOURCE_COVERAGE_CHANGED')
        need(native_count == document['native_coverage']['fact_count']
             and supplement_count == document['native_coverage']['supplement_count'],
             'B13_NATIVE_SOURCE_COVERAGE_CHANGED')
    body = {k: v for k, v in source.items() if k != 'semantic_source_id'}
    body.update(record_type='B13_COMPLETE_SEMANTIC_SOURCE', metric_id='B13',
                inherited_complete_source_id=source['semantic_source_id'],
                capacity_navigation=navigation,
                native_capacity_role_assessments=native_capacity_roles(source['units']),
                required_assessment_dimensions=['assertion', 'subject', 'period',
                    'product_or_facility_scope', 'quantity_role', 'unit', 'detail_level'],
                source_check_scope='SAVED_ANNUAL_PRIMARY_AND_ALL_CURRENT_ANNUAL_AMENDMENTS_VISIBLE_AND_NATIVE',
                numeric_pair_completeness_verified=False, absence_established=False,
                native_result_created=False, interpretation_created=False)
    return {**body, 'semantic_source_id': content_hash(value=body)}


def prepare_capacity_semantic_source(*, repo_root: Path, company_id: str, request_context_format=None, ordinary_registered=False):
    """Rebuild all source units before any B13 quantity or absence decision."""
    rules, approved = policy()
    need(company_id in approved['applicable_company_ids'],
         'B13_OUTSIDE_APPROVED_APPLICABILITY')
    need(strict_json_file(path=(ROOT if ordinary_registered else repo_root) / POLICY_PATH) == rules,
         'B13_INSTALLED_RULES_CHANGED')
    source = prepare_d04_semantic_source(repo_root=repo_root, company_id=company_id, ordinary_registered=ordinary_registered)
    result = capacity_source_from_complete_annual(source=source, rules=rules)
    body = {k: v for k, v in result.items() if k != 'semantic_source_id'}
    body.update(capacity_rule_sha256=sha256_file(path=ROOT / POLICY_PATH),
                capacity_module_sha256=sha256_file(path=Path(__file__)))
    if request_context_format is not None:
        from .continuous_request_context import FORMAT_VERSION
        need(request_context_format == FORMAT_VERSION, 'B13_CONTEXT_FORMAT_UNSUPPORTED')
        body['request_context_format'] = FORMAT_VERSION
    result = {**body, 'semantic_source_id': content_hash(value=body)}
    if request_context_format is not None:
        from .capacity_quantity_scope import attach_quantity_scope
        from .sources import resolve_repository_file
        raw = {d['raw_blob']['raw_asset_id']: resolve_repository_file(repo_root=repo_root,
            repo_relative_path=d['raw_blob']['storage_uri']).read_bytes() for d in result['documents']}
        result = attach_quantity_scope(source=result, raw_bytes_by_id=raw)
    return result
