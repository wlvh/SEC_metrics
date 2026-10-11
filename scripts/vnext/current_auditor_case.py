"""Latest saved C04 consumes the existing complete four-form source core."""
from .c04_registration_successor import (prepare_c04_registration_case,EVENT_FORMS,
                                         SELECTED_PROCESSING_FILES)
from .normal_annual_input_v2 import prepare_saved_annual_input
from .normal_source_authority import ROOT

PROCESSING_FILES=tuple(dict.fromkeys((*SELECTED_PROCESSING_FILES,
    'scripts/vnext/current_auditor_case.py','scripts/vnext/c04_verified_document_alias.py',
    'scripts/vnext/normal_governance_input.py','scripts/vnext/normal_history_catalog.py',
    'scripts/vnext/normal_annual_input.py','scripts/vnext/normal_annual_input_v2.py',
    'scripts/vnext/fiscal_year_labels.py','scripts/vnext/ordinary_registry_scope.py','scripts/sec_http.py','scripts/sec_urls.py')))


def prepare_current_auditor_case(*,source_root,company_id):
    from .normal_governance_input import prepare_saved_governance_input
    from pathlib import Path
    source=Path(source_root)
    annual=prepare_saved_annual_input(repo_root=source,company_id=company_id,ordinary_registered=True)
    base=prepare_saved_governance_input(repo_root=source,company_id=company_id,rules_root=ROOT)
    case=prepare_c04_registration_case(repo_root=source,company_id=company_id,event_forms=EVENT_FORMS,
        selected_base=base,labelled_annual=annual)
    period=annual['table_input']['target_period'];result=case['results']['C04']
    if any(result[key]!=period[key] for key in ('period_start','period_end')) or case['target_period']['fiscal_year']!=period['fiscal_year']:
        raise ValueError('CURRENT_C04_SOURCE_PERIOD_CHANGED')
    complete=case['selection']
    selection={k:complete[k] for k in ('selection_id','resolver','selected_current_accession',
        'names_differ','reason_code','same_cik_prior_status','event_forms','matched_item_4_01_claim_ids') if k in complete}
    selection['event_source_set_ids']=[x['manifest']['source_set_manifest_id'] for x in complete.get('event_source_sets',[])]
    return {**case,'prepared_annual_input':annual,'rules_root':str(ROOT),
        'input_assessments':{'current_auditor':complete},'selection':selection}
