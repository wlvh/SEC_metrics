#!/usr/bin/env python3
"""Export, install and compute company sources without SEC or new AI calls."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    export = sub.add_parser('export', help='Controlled preparation: source-only company export')
    export.add_argument('--source-root', required=True, type=Path)
    export.add_argument('--output-root', required=True, type=Path)
    export.add_argument('--trust-root', required=True, type=Path)
    export.add_argument('--company', required=True)
    export.add_argument('--metric', action='append')
    export.add_argument('--history-years', type=int, choices=[5])
    processing = sub.add_parser('export-processing', help='Authenticate complete saved D04 separately from SEC sources')
    processing.add_argument('--installed-root', required=True, type=Path)
    processing.add_argument('--output-root', required=True, type=Path)
    processing.add_argument('--runtime-output-root', required=True, type=Path)
    processing.add_argument('--trust-root', required=True, type=Path)
    processing.add_argument('--company', required=True)
    runtime = sub.add_parser('install-runtime', help='Install a separately bound fixed computing runtime')
    runtime.add_argument('--output-root', required=True, type=Path)
    runtime.add_argument('--kind', choices=['baseline', 'ordinary', 'native', 'historical'], default='baseline')
    install = sub.add_parser('install', help='Validate and import at the stable company source path')
    install.add_argument('--package-root', required=True, type=Path)
    install.add_argument('--state-root', required=True, type=Path)
    install.add_argument('--trust-root', required=True, type=Path)
    install.add_argument('--company', required=True)
    compute = sub.add_parser('compute', help='Use the installed company source and native update APIs')
    compute.add_argument('--state-root', required=True, type=Path)
    compute.add_argument('--trust-root', required=True, type=Path)
    compute.add_argument('--company', required=True)
    compute.add_argument('--metric', required=True, action='append')
    compute.add_argument('--processing-package', type=Path)
    compute.add_argument('--processing-runtime', type=Path)
    compute.add_argument('--processing-trust-root', type=Path)
    period = compute.add_mutually_exclusive_group()
    period.add_argument('--report-end')
    period.add_argument('--fiscal-year', type=int)
    results = sub.add_parser('export-results', help='Export native rows, evidence and replay inputs')
    results.add_argument('--state-root', required=True, type=Path)
    results.add_argument('--output-root', required=True, type=Path)
    results.add_argument('--trust-root', required=True, type=Path)
    results.add_argument('--company', required=True)
    results.add_argument('--runtime-root', action='append', type=Path, default=[],
                         help='Fixed creator tree; repeat for mixed Run closures')
    results.add_argument('--defects-file', type=Path,
                         help='Existing known_result_defects register, read only')
    results.add_argument('--processing-trust-root', type=Path)
    view = sub.add_parser('results', help='Read all native company metric/period references')
    view.add_argument('--state-root', required=True, type=Path)
    view.add_argument('--trust-root', required=True, type=Path)
    view.add_argument('--company', required=True)
    view.add_argument('--defects-file', type=Path)
    view.add_argument('--runtime-root', action='append', type=Path, default=[])
    args = parser.parse_args(argv)
    start = time.monotonic()
    if args.command == 'export':
        from vnext.company_handoff import export_company
        declaration = None
        if args.history_years:
            from vnext.historical_source_acquisition import declared_frame
            declaration = lambda source, company: declared_frame(
                repo_root=source, company_id=company, years=args.history_years)
        result = export_company(source_root=args.source_root, output_root=args.output_root,
                                trust_root=args.trust_root, company_id=args.company,
                                metric_ids=args.metric, declared_frame=declaration)
    elif args.command == 'export-processing':
        from vnext.company_processing import export_processing
        result = export_processing(installed_root=args.installed_root, output_root=args.output_root,
            runtime_output_root=args.runtime_output_root, trust_root=args.trust_root, company_id=args.company)
    elif args.command == 'install-runtime':
        from vnext.company_runtime_install import install_runtime
        result = install_runtime(output_root=args.output_root, kind=args.kind)
    else:
        from vnext.company_source_authority import TRUST_VARIABLE
        os.environ[TRUST_VARIABLE] = str(args.trust_root)
        if getattr(args, 'processing_trust_root', None):
            from vnext.company_processing import TRUST_VARIABLE as processing_trust_variable
            os.environ[processing_trust_variable] = str(args.processing_trust_root)
        if args.command == 'install':
            from vnext.company_handoff import install_company
            result = install_company(package_root=args.package_root, state_root=args.state_root,
                                     company_id=args.company)
        elif args.command == 'compute':
            from vnext.company_compute import compute_company
            result = compute_company(state_root=args.state_root, company_id=args.company,
                                     metric_ids=args.metric, report_end=args.report_end,
                                     fiscal_year=args.fiscal_year, processing_package=args.processing_package,
                                     processing_runtime=args.processing_runtime)
        elif args.command == 'results':
            from vnext.company_result_view import read_company_results
            result = read_company_results(state_root=args.state_root, company_id=args.company,
                                         defects_file=args.defects_file, runtime_roots=args.runtime_root)
        else:
            from vnext.company_result_export import export_results
            result = export_results(state_root=args.state_root, output_root=args.output_root,
                                    company_id=args.company, runtime_roots=args.runtime_root,
                                    defects_file=args.defects_file)
    print(json.dumps({'elapsed_seconds': time.monotonic()-start, **result},
                     ensure_ascii=False, indent=2))
    if args.command == 'compute':
        return 0 if all(m['status'] in {'CANDIDATE_READY', 'NO_SOURCE_CONTENT_CHANGE'}
                        for m in result['metrics']) else 2
    return 2 if result.get('status') == 'EXPORTED_PARTIAL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
