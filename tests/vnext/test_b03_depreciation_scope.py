"""A narrow B03 source fact must not enter current update or release credit."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import socket
import tempfile
from unittest import TestCase
from unittest.mock import patch

from tests.vnext.test_normal_zero_ai_results import original_sources_only
from tools import vnext_normal_update
from vnext import ordinary_release_preparation as release
from vnext.b03_depreciation_scope import (
    _nearest_da_label, assess_direct_depreciation_scope)
from vnext.canonical import sha256_bytes
from vnext.normal_run_v3 import (create_normal_run, install_normal_inputs,
                                 prepare_case)
from vnext.normal_source_authority import ROOT
from vnext.ordinary_projection import render_ordinary_run


class B03DepreciationScopeTest(TestCase):
    def test_nearby_narrow_row_does_not_taint_a_later_generic_label(self):
        self.assertFalse(_nearest_da_label(
            'Depreciation and amortization of fixed assets 1.2 '
            'Total depreciation and amortization ')['narrow'])
        self.assertTrue(_nearest_da_label(
            'Total depreciation and amortization of fixed assets ')['narrow'])


class B03DepreciationScopeMaterialTest(TestCase):
    def test_current_update_cli_selects_guard_without_request_or_success(self):
        self.enterContext(original_sources_only())
        with tempfile.TemporaryDirectory(prefix='b03-current-cli-') as tmp:
            output = StringIO()
            with redirect_stdout(output):
                code = vnext_normal_update.main(['--process',
                    '--state-root', tmp, '--company', 'salesforce',
                    '--metric', 'B03'])
            report = json.loads(output.getvalue())
            self.assertEqual(2, code)
            self.assertEqual('UPDATES_INCOMPLETE',
                report['companies'][0]['status'])
            self.assertEqual('EXECUTION_FAILED',
                report['companies'][0]['metrics'][0]['status'])
            self.assertEqual({'provider':0,'paid':0,'sec':0},
                report['calls'])
            state = (Path(tmp)/'salesforce/metrics/B03/current.json')
            self.assertIsNone(json.loads(state.read_text())[
                'successful_attempt'])

    def test_saved_salesforce_subset_and_competing_scope_block_current_credit(self):
        self.enterContext(original_sources_only())
        case = prepare_case(data_root=ROOT, company_id='salesforce',
                            metric_id='B03')
        self.assertEqual('PUBLISHED', case['results']['B03']['publication'])
        assessment = assess_direct_depreciation_scope(case=case,
            data_root=ROOT)
        self.assertEqual('NARROW_SELECTED_AND_COMPETING_SCOPE',
                         assessment['status'])
        self.assertTrue(assessment['blocked'])
        self.assertEqual('1200000000', assessment['selected_fact']['value'])
        self.assertIn('fixed assets', assessment['selected_label'])
        self.assertIn(('3631000000', 'us-gaap:DepreciationAndAmortization'),
            [(row['value'], row['concept'])
             for row in assessment['competing_facts']])
        with patch.object(release.normal, 'replay_case', return_value=case):
            with self.assertRaisesRegex(ValueError,
                    'ORDINARY_RELEASE_B03_DEPRECIATION_SCOPE_UNRESOLVED'):
                release._result_selection_basis(data_root=ROOT, manifest={},
                    result=case['results']['B03'], rendered={})

    def test_unflagged_direct_and_composed_inputs_keep_their_prior_path(self):
        self.enterContext(original_sources_only())
        southwest = prepare_case(data_root=ROOT,
            company_id='southwest_airlines', metric_id='B03')
        assessment = assess_direct_depreciation_scope(case=southwest,
            data_root=ROOT)
        self.assertEqual('NO_EXPLICIT_NARROW_SCOPE_FOUND',
                         assessment['status'])
        self.assertFalse(assessment['blocked'])
        self.assertFalse(assessment['complete_depreciation_scope_proven'])
        with patch.object(release.normal, 'replay_case',
                          return_value=southwest):
            self.assertEqual('NATIVE_PUBLISHED_RESULT',
                release._result_selection_basis(data_root=ROOT,
                    manifest={}, result=southwest['results']['B03'],
                    rendered={}))
        marriott = prepare_case(data_root=ROOT,
            company_id='marriott_international', metric_id='B03')
        self.assertEqual('NO_DIRECT_DEPRECIATION_SELECTION',
            assess_direct_depreciation_scope(case=marriott,
                data_root=ROOT)['status'])

    def test_altered_original_source_proof_is_rejected(self):
        self.enterContext(original_sources_only())
        case = prepare_case(data_root=ROOT, company_id='salesforce',
                            metric_id='B03')
        accession = next(row['source_binding']['accession']
            for row in case['observations'] if row['semantic_role'] ==
            'depreciation_and_amortization')
        proofs = [{**proof, 'content_sha256': '0' * 64}
            if proof.get('accession') == accession and
            proof.get('document_name', '').endswith('.htm') else proof
            for proof in case['source_proofs']]
        with self.assertRaisesRegex(ValueError,
                'B03_SCOPE_PRIMARY_BYTES_CHANGED'):
            assess_direct_depreciation_scope(case={**case,
                'source_proofs': proofs}, data_root=ROOT)


    def test_real_saved_salesforce_run_cannot_enter_unified_release(self):
        self.enterContext(patch.object(socket.socket, 'connect',
            side_effect=AssertionError('NETWORK_FORBIDDEN')))
        self.enterContext(patch.object(socket, 'getaddrinfo',
            side_effect=AssertionError('DNS_FORBIDDEN')))
        self.enterContext(patch('sec_http.urlopen',
            side_effect=AssertionError('HTTP_FORBIDDEN')))
        with tempfile.TemporaryDirectory(prefix='b03-scope-current-') as tmp:
            data = Path(tmp)/'data'
            run = Path(tmp)/'run'
            install_normal_inputs(data_root=data, company_id='salesforce',
                metric_id='B03')
            created = create_normal_run(data_root=data, run_dir=run,
                company_id='salesforce', metric_id='B03')
            self.assertEqual('PUBLISHED', created['result']['publication'])
            rendered = render_ordinary_run(data_root=data, run_dir=run,
                _return_replay_context=True)
            result = next(row for row in rendered['replay_context']['records']
                if row['record_type'] == 'METRIC_RESULT'
                and row['metric_id'] == 'B03')
            self.assertEqual(created['result'], result)
            with self.assertRaisesRegex(ValueError,
                    'ORDINARY_RELEASE_B03_DEPRECIATION_SCOPE_UNRESOLVED'):
                release._result_selection_basis(data_root=data,
                    manifest=created['manifest'], result=result,
                    rendered=rendered)


class B03ImpairmentSourceMaterialTest(TestCase):
    def test_ford_total_includes_footnoted_impairment_depreciation(self):
        self.enterContext(original_sources_only())
        case = prepare_case(data_root=ROOT,
                            company_id='ford_motor_company', metric_id='B03')
        self.assertEqual('PUBLISHED', case['results']['B03']['publication'])
        checked = assess_direct_depreciation_scope(case=case, data_root=ROOT)
        self.assertEqual('SELECTED_DEPRECIATION_INCLUDES_IMPAIRMENT',
                         checked['status'])
        self.assertTrue(checked['blocked'])
        proof = checked['impairment_inclusion_proof']
        self.assertEqual('15974', proof['visible_component_sum'])
        self.assertEqual('15,974', proof['selected_visible_total'])
        self.assertEqual('8,235',
                         proof['included_component']['visible_value'])
        self.assertEqual('g', proof['included_component']['marker'])
        self.assertIn('depreciation related to the Model e asset impairment',
                      proof['footnote']['text'])
        with patch.object(release.normal, 'replay_case', return_value=case):
            with self.assertRaisesRegex(ValueError,
                    'ORDINARY_RELEASE_B03_DEPRECIATION_SCOPE_UNRESOLVED'):
                release._result_selection_basis(data_root=ROOT, manifest={},
                    result=case['results']['B03'], rendered={})

    def test_exclusion_footnote_cannot_trigger_inclusion_guard(self):
        self.enterContext(original_sources_only())
        case = prepare_case(data_root=ROOT,
                            company_id='ford_motor_company', metric_id='B03')
        proof = next(row for row in case['source_proofs']
            if row.get('accession') == '0000037996-26-000015'
            and row.get('document_name') == 'f-20251231.htm')
        raw = (ROOT/proof['request_repo_relative_path']).read_bytes()
        text = raw.decode('utf-8')
        anchor = text.index('Model e asset impairment (see Note')
        include = text.rfind('Includes', 0, anchor)
        self.assertLess(anchor-include, 300)
        changed = (text[:include] + 'Excludes' +
                   text[include+len('Includes'):]).encode('utf-8')
        with tempfile.TemporaryDirectory(prefix='b03-footnote-negative-') as tmp:
            root = Path(tmp).resolve()
            target = root/proof['request_repo_relative_path']
            target.parent.mkdir(parents=True)
            target.write_bytes(changed)
            altered = deepcopy(case)
            altered['source_proofs'] = [
                {**row, 'content_sha256': sha256_bytes(content=changed)}
                if row == proof else row for row in case['source_proofs']]
            # This synthetic text change checks only the local source-role
            # relation. It has no SEC request-log or business credit.
            checked = assess_direct_depreciation_scope(case=altered,
                                                        data_root=root)
            self.assertFalse(checked['blocked'])
            self.assertEqual('NO_EXPLICIT_NARROW_SCOPE_FOUND',
                             checked['status'])
