"""One company, one pinned source version, existing ordinary update/Run APIs."""
import json
from pathlib import Path
import socket
import time
from unittest.mock import patch

from .canonical import strict_json_file
from .company_handoff import locked_company, recover_import, _atomic_json
from .company_source_authority import require_company, need


def compute_company(*, state_root, company_id, metric_ids, report_end=None, fiscal_year=None,
                    processing_package=None, processing_runtime=None):
    """Keep the import lock until all selected Runs and references are durable."""
    with locked_company(state_root) as root:
        current = recover_import(root)
        need(current is not None, 'COMPANY_COMPUTE_SOURCE_NOT_INSTALLED')
        source = root/'source'
        admission = require_company(source_root=source, company_id=company_id)
        need(metric_ids and len(metric_ids) == len(set(metric_ids))
             and set(metric_ids) <= set(admission['metric_ids']),
             'COMPANY_COMPUTE_METRIC_OUTSIDE_PACKAGE_SCOPE')
        start = time.monotonic()
        ordinary = [m for m in metric_ids if m not in {'B13', 'D04', 'C04'}]
        processing_errors = {}
        if 'B13' in metric_ids:
            try:
                from .capacity_utilization_source import policy
                _, approved = policy()
                if company_id not in approved['applicable_company_ids']:
                    ordinary.append('B13')
            except Exception as error:
                processing_errors['B13'] = {'metric_id': 'B13', 'status': 'UPDATE_BLOCKED',
                    'reason': str(error), 'error_type': type(error).__name__,
                    'business_metric_completed': False}
        from .normal_source_authority import ROOT
        historical = (ROOT/'requirements/issue_54_v3').is_dir()
        native = (ROOT/'requirements/issue_54_v2').is_dir()
        need((processing_package is None) == (processing_runtime is None),
             'COMPANY_PROCESSING_PACKAGE_AND_ORIGINAL_RUNTIME_REQUIRED')
        need(processing_package is None or 'D04' in metric_ids,
             'COMPANY_PROCESSING_INPUT_REQUIRES_D04')
        need(not historical or processing_package is None,
             'COMPANY_PROCESSING_HISTORY_ADAPTER_NOT_IMPLEMENTED')
        need(not native or set(metric_ids) <= {'B13', 'D04'},
             'COMPANY_NATIVE_RUNTIME_METRIC_SCOPE_REQUIRED')
        if not native and (ROOT/'requirements/issue_54_v1').is_dir() and 'B13' in ordinary:
            ordinary.remove('B13')
            processing_errors['B13'] = {'metric_id': 'B13', 'status': 'NATIVE_RUNTIME_REQUIRED',
                'reason': 'Use the fixed native runtime for acquired-company B13; its parent is issue_28_v14.',
                'business_metric_completed': False}
        need(historical or report_end is None and fiscal_year is None,
             'COMPANY_COMPUTE_PERIOD_REQUIRES_HISTORY_RUNTIME')
        # This child process is computing only. Recorded capture occurs in
        # the preparation process. Provider and SEC dispatch are impossible.
        with patch.object(socket.socket, 'connect', side_effect=ValueError('COMPANY_COMPUTE_NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo', side_effect=ValueError('COMPANY_COMPUTE_DNS_FORBIDDEN')):
            if historical:
                from .company_historical_compute import compute_historical
                from .normal_history_plan import checkpoint_replayed_once
                # Reuse #47's existing state-keyed, single-thread replay scope.
                # Every selected proof is still checked; a changed source root
                # or installed data directory gets a fresh full replay.
                with checkpoint_replayed_once():
                    result = compute_historical(root=root, source=source, company_id=company_id,
                        metric_ids=metric_ids, report_end=report_end, fiscal_year=fiscal_year)
            else:
                from .ordinary_d02_category_update_v2 import run_company
                result = (run_company(state_root=root/('updates/native-v1' if native else 'updates'), source_root=source,
                                 company_id=company_id, metric_ids=ordinary)
                      if ordinary else {'company_id': company_id, 'metrics': []})
            results = {row['metric_id']: row for row in result['metrics']}
            for metric in ([] if historical else metric_ids):
                if metric in {'B13', 'D04'} and metric not in ordinary:
                    if metric == 'D04' and processing_package is not None:
                        try:
                            need(processing_runtime is not None, 'COMPANY_PROCESSING_ORIGINAL_RUNTIME_REQUIRED')
                            from .company_processing import compute_saved_processing
                            results[metric] = compute_saved_processing(root=root, source=source, admission=admission,
                                company_id=company_id, packet_root=processing_package, program_root=processing_runtime)
                        except Exception as error:
                            results[metric] = {'metric_id': metric, 'status': 'PROCESSING_INPUT_REJECTED',
                                'reason': str(error), 'business_metric_completed': False}
                        continue
                    results[metric] = processing_errors.get(metric) or {'metric_id': metric, 'status': 'AI_PROCESSING_INPUT_REQUIRED',
                        'reason': 'SEC sources are installed. Supply independently trusted complete D04 processing input with its original fixed runtime. B13 and acquired-source assessment adaptation remain unsupported; new AI calls require a subsequent issue.',
                        'business_metric_completed': False}
                elif metric == 'C04':
                    from .c04_update_cycle import run_company as run_c04
                    results[metric] = {'metric_id': metric, **run_c04(
                        state_root=root/'updates/metrics/C04-registration-v3',
                        source_root=source, company_id=company_id)['metrics'][0]}
        # The package is unchanged throughout compute, and the original Run
        # installers preserve their own source and rule copies for old replay.
        require_company(source_root=source, company_id=company_id)
        report = {'record_type': 'COMPANY_COMPUTATION_REFERENCES_V1',
            'company_id': company_id, 'source_checkpoint_id': admission['checkpoint_id'],
            'source_root': str(source), 'metric_ids': metric_ids,
            'period_request': {'report_end': report_end, 'fiscal_year': fiscal_year},
            'metrics': [results[m] for m in metric_ids],
            'compute_seconds': format(time.monotonic()-start, '.6f'),
            'source_installation': (strict_json_file(path=root/'latest_import.json')
                                    if (root/'latest_import.json').is_file() else None),
            'new_business_calls': {'provider': 0, 'paid': 0, 'sec': 0},
            'production_authorized': False}
        from .company_result_view import save_execution, build_company_view
        report['runtime_root'] = str(ROOT)
        report = save_execution(root=root, report=report)
        _atomic_json(root/'company-results.json', build_company_view(
            root=root, company_id=company_id, current=current))
        return report
