"""Current annual D01 through the existing source selector and ordinary writer.

The thin selected-source construction follows #47's historical consumer at
6d000bdc. This adapter uses current annual selection, not its historical engine.
Heading selection, Evidence, Review and Calculator are shared public functions.
"""
import copy
from datetime import datetime, timezone
from pathlib import Path

SPEC_PATH = 'catalog/r6/D01_risk_factor_headings.md'
CAPACITY_SPEC_PATH = 'catalog/ordinary_risk_headings/D01_128.md'
PROCESSING_FILES = (
    'scripts/vnext/current_risk_heading_case.py',
    'scripts/vnext/normal_annual_input_v2.py',
    'scripts/vnext/fiscal_year_labels.py',
    'scripts/vnext/text_results_v2.py',
    'scripts/vnext/normal_governance_input.py',
    'scripts/vnext/d01_emphasis_results.py',
    'scripts/vnext/d01_emphasis_source.py',
    'scripts/vnext/text_results.py',
    'scripts/vnext/text_rendering_limits.py',
    'scripts/vnext/text_coverage.py',
    'scripts/vnext/risk_signals.py',
    'scripts/vnext/text_review.py',
    'scripts/vnext/review.py',
    'config/normal_fiscal_year_labels_v1.json',
    'catalog/r6/text_results_v2_policy.json',
    SPEC_PATH, CAPACITY_SPEC_PATH,
)


class CurrentRiskHeadingError(ValueError):
    def __init__(self, reason, category='SOURCE_INTEGRITY_ERROR'):
        super().__init__(reason)
        self.category = category


def _need(condition, reason, category='SOURCE_INTEGRITY_ERROR'):
    if not condition:
        raise CurrentRiskHeadingError(reason, category)


def _candidate(api, args, root):
    """Reuse the public capacity contract only after actual old-limit failure."""
    from .specs import compile_spec_file
    old = args['compiled_spec']
    try:
        return api.create_deterministic_text_candidate(**args), SPEC_PATH
    except ValueError as error:
        if str(error) != 'DETERMINISTIC_TEXT_HEADINGS_EXCEED_BOUND':
            raise
    successor = compile_spec_file(path=root/CAPACITY_SPEC_PATH, dependency_specs={})
    before, after = copy.deepcopy(old['compiled']), copy.deepcopy(successor['compiled'])
    a, b = before['text_policy'], after['text_policy']
    _need(a['renderer'] == 'ORDERED_NEWLINE_V1' and a['max_items'] == 64
          and b['renderer'] == 'ORDERED_NEWLINE_128_V2' and b['max_items'] == 128,
          'CURRENT_RISK_HEADINGS_CAPACITY_SUCCESSOR_CHANGED')
    b.update(renderer=a['renderer'], max_items=a['max_items'])
    _need(before == after, 'CURRENT_RISK_HEADINGS_CAPACITY_SEMANTICS_CHANGED')
    args['compiled_spec'] = successor
    candidate = api.create_deterministic_text_candidate(**args)
    _need(len(candidate['selected']) > a['max_items'], 'CURRENT_RISK_HEADINGS_CAPACITY_NOT_REQUIRED')
    return candidate, CAPACITY_SPEC_PATH


def prepare_current_risk_heading_case(*, repo_root, company_id, metric_id):
    from .canonical import content_hash
    from .normal_annual_input_v2 import prepare_saved_annual_input
    from .normal_governance_input import _Sources
    from .normal_source_authority import ROOT
    from .ordinary_source_authority import verify_ordinary_source_proofs
    from .specs import compile_spec_file
    from .traits import repository_company_traits
    from . import d01_emphasis_results as api
    from .text_review import build_text_review_unit
    from .review import (_create_review_decision, _system_approved_claims,
                         SYSTEM_REVIEWER_ID, SYSTEM_REVIEW_REASON)
    _need(metric_id == 'D01', 'CURRENT_RISK_HEADINGS_METRIC_NOT_SUPPORTED', 'IMPLEMENTATION_GAP')
    source = Path(repo_root)
    annual = prepare_saved_annual_input(repo_root=source, company_id=company_id, ordinary_registered=True)
    _need(not annual['amendments'] and annual['subject_policy']['mode'] == 'CONTINUOUS_PRIMARY',
          'CURRENT_RISK_HEADINGS_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED', 'IMPLEMENTATION_GAP')
    period = annual['table_input']['target_period']
    original = annual.get('original_input', annual)['table_input']['target_period']
    _need(all(original[k] == period[k] for k in ('period_start', 'period_end')),
          'CURRENT_RISK_HEADINGS_ORIGINAL_PERIOD_CHANGED')
    spec = compile_spec_file(path=ROOT/SPEC_PATH, dependency_specs={})
    _need(spec['compiled']['quality_rule'].get('deterministic_text_method') == 'RISK_FACTOR_HEADINGS_V1'
          and not spec['compiled']['dependencies'], 'CURRENT_RISK_HEADINGS_SPEC_CHANGED')
    reader = _Sources(source, company_id, annual['entity'])
    primary = reader.primary(annual['filing'])
    scope = spec['compiled']['required_claims']
    target = {'company_id':company_id, 'entity':annual['entity'],
        'accession':annual['filing']['accessionNumber'], 'period_start':period['period_start'],
        'period_end':period['period_end'], 'scope':scope, 'scope_key':content_hash(value=scope)}
    args = {'compiled_spec':spec, 'target':target, 'source_references':[primary['source_reference']],
        'raw_blobs':{primary['raw_blob']['raw_asset_id']:primary['raw_blob']},
        'raw_bytes_by_id':{primary['raw_blob']['raw_asset_id']:primary['raw_bytes']},
        'd01_emphasis_policy':api.RUNNING_HEADER_POLICY}
    candidate, path = _candidate(api, args, ROOT)
    spec = args['compiled_spec']
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
        candidate=candidate, evidence_check=evidence, review_unit=unit, review_decisions=[decision], **args)
    proofs = list({content_hash(value=p):p for p in [*annual['source_proofs'],
        *[s['proof'] for s in reader.proofs.values()]]}.values())
    return {'kind':'STRUCTURED', 'primary_metric_id':metric_id,
        'input_binding':{'record_type':'CURRENT_RISK_HEADING_INPUT', 'prepared_input':annual,
            'source_proofs':proofs, 'd01_emphasis_policy':api.RUNNING_HEADER_POLICY, 'new_provider_execution':False},
        'compiled_specs':{metric_id:spec}, 'spec_paths':{metric_id:path}, 'target_period':period,
        'prepared_annual_input':annual, 'references':args['source_references'], 'source_proofs':proofs,
        'admission':verify_ordinary_source_proofs(data_root=source, proofs=proofs),
        'expected_records':[*reader.records.values(), candidate, evidence, unit, decision, *observations, trace, result],
        'results':{metric_id:result}, 'traces':{metric_id:trace},
        'selection':{'method':'RISK_FACTOR_HEADINGS_V1', 'source_reference_ids':candidate['source_reference_ids'],
            'heading_count':len(candidate['selected']), 'risk_occurrence_asserted':False, 'capacity_spec_path':path},
        'rules_root':str(ROOT)}


def run_current_saved_company(*, company_id, source_root, work_dir, output_dir, metric_ids=None):
    from .company_current_records import run_saved_company
    from .canonical import strict_json_file
    from .normal_source_authority import ROOT
    selected = sorted(strict_json_file(path=ROOT/'config/source_strategy_registry.json')['metrics']) if metric_ids is None else list(metric_ids)
    return run_saved_company(company_id=company_id, source_root=source_root, work_dir=work_dir,
        output_dir=output_dir, metric_ids=selected,
        **({'current_case_factories':{'D01':prepare_current_risk_heading_case},
            'processing_files_by_metric':{'D01':PROCESSING_FILES}} if 'D01' in selected else {}))
