"""Selected annual D01 source excerpts for the existing ordinary company path.

This adapter selects a historical annual identity and consumes the shared D01
source/Evidence/Review/Calculator. It owns no heading classifier or persistence.
"""
from datetime import datetime, timezone
from pathlib import Path

from .canonical import content_hash
from .historical_annual_input import prepare_historical_annual_input
from .historical_dei import release_aware
from .normal_period_selection import resolve_period_selection
from .normal_governance_input import _Sources
from .normal_source_authority import ROOT
from .ordinary_source_authority import verify_ordinary_source_proofs
from .review import _create_review_decision, _system_approved_claims, SYSTEM_REVIEWER_ID, SYSTEM_REVIEW_REASON
from .specs import compile_spec_file
from .text_review import build_text_review_unit
from .traits import repository_company_traits
from . import d01_emphasis_results

METRICS = frozenset({'D01'})
SPEC_PATH = 'catalog/r6/D01_risk_factor_headings.md'
PROCESSING_FILES = (
    'scripts/vnext/historical_risk_heading_case.py',
    'scripts/vnext/historical_annual_input.py',
    'scripts/vnext/historical_dei.py',
    'scripts/vnext/historical_fiscal_labels.py',
    'scripts/vnext/historical_filing_inventory.py',
    'scripts/vnext/normal_period_selection.py',
    'scripts/vnext/normal_history_catalog.py',
    'scripts/vnext/normal_annual_input.py',
    'scripts/vnext/normal_annual_input_v2.py',
    'scripts/vnext/fiscal_year_labels.py',
    'scripts/vnext/normal_governance_input.py',
    'scripts/vnext/d01_emphasis_results.py',
    'scripts/vnext/d01_emphasis_source.py',
    'scripts/vnext/text_results.py',
    'scripts/vnext/text_coverage.py',
    'scripts/vnext/risk_signals.py',
    'scripts/vnext/text_review.py',
    'scripts/vnext/review.py',
    'config/normal_period_selection_v1.json',
    'config/normal_fiscal_year_labels_v1.json',
    SPEC_PATH,
)


class RiskHeadingCaseError(ValueError):
    def __init__(self, reason, category='SOURCE_INTEGRITY_ERROR'):
        super().__init__(reason)
        self.category = category


def _need(condition, reason, category='SOURCE_INTEGRITY_ERROR'):
    if not condition:
        raise RiskHeadingCaseError(reason, category)


def prepare_historical_risk_heading_year_case(*, repo_root, company_id, metric_id, fiscal_year):
    """A selected source-heading result, not a free-form risk interpretation."""
    _need(metric_id in METRICS, 'HISTORICAL_RISK_HEADINGS_METRIC_NOT_SUPPORTED', 'IMPLEMENTATION_GAP')
    source = Path(repo_root)
    selection = resolve_period_selection(repo_root=source, company_id=company_id,
        fiscal_year=fiscal_year, rules_root=ROOT)
    annual = prepare_historical_annual_input(repo_root=source, company_id=company_id,
        period_selection=selection, rules_root=ROOT)
    _need(not annual['amendments'] and annual['subject_policy']['mode'] == 'CONTINUOUS_PRIMARY',
          'HISTORICAL_RISK_HEADINGS_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED', 'IMPLEMENTATION_GAP')
    period = annual['table_input']['target_period']
    original = annual.get('original_input', annual)['table_input']['target_period']
    _need(all(original[k] == period[k] for k in ('period_start', 'period_end')),
          'HISTORICAL_RISK_HEADINGS_ORIGINAL_PERIOD_CHANGED')
    spec = compile_spec_file(path=ROOT/SPEC_PATH, dependency_specs={})
    _need(spec['compiled']['quality_rule'].get('deterministic_text_method') == 'RISK_FACTOR_HEADINGS_V1'
          and not spec['compiled']['dependencies'], 'HISTORICAL_RISK_HEADINGS_SPEC_CHANGED')
    reader = _Sources(source, company_id, annual['entity'])
    primary = reader.primary(annual['filing'])
    target = {'company_id': company_id, 'entity': annual['entity'],
        'accession': annual['filing']['accessionNumber'],
        'period_start': period['period_start'], 'period_end': period['period_end'],
        'scope': spec['compiled']['required_claims'],
        'scope_key': content_hash(value=spec['compiled']['required_claims'])}
    args = {'compiled_spec': spec, 'target': target,
        'source_references': [primary['source_reference']],
        'raw_blobs': {primary['raw_blob']['raw_asset_id']: primary['raw_blob']},
        'raw_bytes_by_id': {primary['raw_blob']['raw_asset_id']: primary['raw_bytes']},
        'd01_emphasis_policy': d01_emphasis_results.RUNNING_HEADER_POLICY}
    # The retained namespace view keeps shared D01 algorithms while admitting
    # actual historical SEC/FASB release names. It is not a second selector.
    api = release_aware(d01_emphasis_results)
    candidate = api.create_deterministic_text_candidate(**args)
    evidence = api.build_text_evidence(candidate=candidate, **args)
    unit, _ = build_text_review_unit(compiled_spec=spec, candidate=candidate,
        evidence_check=evidence, source_bindings=args['source_references'])
    decision = _create_review_decision(review_unit=unit, decision='APPROVE',
        approved_claims=_system_approved_claims(review_unit=unit),
        required_claims=spec['compiled']['required_claims'], reviewer_type='SYSTEM',
        reviewer_id=SYSTEM_REVIEWER_ID, decided_at_utc=datetime.now(timezone.utc).isoformat(),
        reason=SYSTEM_REVIEW_REASON, supersedes_decision_id=None)
    result, trace, observations = api.replay_text_result(
        company_traits=repository_company_traits(repo_root=ROOT, company_id=company_id),
        candidate=candidate, evidence_check=evidence, review_unit=unit,
        review_decisions=[decision], **args)
    proofs = list({content_hash(value=p): p for p in [*annual['source_proofs'],
        *[s['proof'] for s in reader.proofs.values()]]}.values())
    binding = {'record_type': 'HISTORICAL_RISK_HEADING_INPUT', 'metric_id': metric_id,
        'prepared_input': annual, 'period_selection': selection,
        'source_proofs': proofs, 'd01_emphasis_policy': d01_emphasis_results.RUNNING_HEADER_POLICY,
        'new_provider_execution': False}
    return {'kind': 'STRUCTURED', 'primary_metric_id': metric_id,
        'input_binding': binding, 'compiled_specs': {metric_id: spec},
        'spec_paths': {metric_id: SPEC_PATH}, 'target_period': period,
        'prepared_annual_input': annual, 'references': args['source_references'],
        'source_proofs': proofs, 'admission': verify_ordinary_source_proofs(data_root=source, proofs=proofs),
        'expected_records': [*reader.records.values(), candidate, evidence, unit, decision,
                             *observations, trace, result],
        'results': {metric_id: result}, 'traces': {metric_id: trace},
        'selection': {'method': 'RISK_FACTOR_HEADINGS_V1',
            'source_reference_ids': candidate['source_reference_ids'],
            'heading_count': len(candidate['selected']), 'risk_occurrence_asserted': False},
        'rules_root': str(ROOT)}
