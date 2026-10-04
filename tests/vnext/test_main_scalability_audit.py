"""Exact-source syntax exclusions at the real main publication boundary."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tests.vnext.common import REPO_ROOT
from vnext.ordinary_scalability_audit import successor_scalability_snapshot
from vnext.publication import _execute_scalability_audit, PublicationError


class MainScalabilityAuditTest(unittest.TestCase):
    def fixture(self, *, scoped=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for part in ('scripts','tools','config'):
            shutil.copytree(REPO_ROOT/part, root/part,
                            ignore=shutil.ignore_patterns('__pycache__'))
        if scoped:
            # Same scoped registry convention as the publication fixtures.
            import csv
            path=root/'config/company_registry.csv'
            with path.open(newline='') as f:
                reader=csv.DictReader(f);fields=reader.fieldnames
                rows=[r for r in reader if r['company_id']=='marriott_international']
            with path.open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
        return root

    def test_actual_publication_gate_accepts_reviewed_syntax_only(self):
        self.assertEqual([], _execute_scalability_audit(repo_root=self.fixture()))

    def test_scoped_registry_still_proves_all_declared_syntax_sites(self):
        self.assertEqual([], _execute_scalability_audit(repo_root=self.fixture(scoped=True)))

    def test_real_identity_and_financial_period_are_not_excluded(self):
        root=self.fixture()
        (root/'scripts/injected_company_branch.py').write_text(
            'def decide(company, period):\n'
            '    return company == "Ford Motor " + "Company" or period == "2025-12-31"\n')
        rows=successor_scalability_snapshot(root,policy_path='config/main_scalability_exemptions_v1.json')
        self.assertTrue(any(r['type']=='company_name' for r in rows))
        self.assertTrue(any(r['type']=='fixed_fiscal_date' for r in rows))
        with self.assertRaisesRegex(PublicationError,'Scalability audit execution failed'):
            _execute_scalability_audit(repo_root=root)

    def test_approved_source_mutation_is_rejected(self):
        root=self.fixture();source=root/'scripts/vnext/capacity_reference_contract.py'
        source.write_bytes(source.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'APPROVED_SOURCE_CHANGED'):
            successor_scalability_snapshot(root,policy_path='config/main_scalability_exemptions_v1.json')

    def test_removing_an_exemption_preserves_the_violation(self):
        root=self.fixture();path=root/'config/main_scalability_exemptions_v1.json'
        policy=json.loads(path.read_text());policy['entries'].pop(0);path.write_text(json.dumps(policy))
        rows=successor_scalability_snapshot(root,policy_path='config/main_scalability_exemptions_v1.json')
        self.assertTrue(any(r['type']=='ticker' and r['literal']=='F' for r in rows))

    def test_non_syntax_site_cannot_be_whitelisted_by_matching_hash(self):
        root=self.fixture();source=root/'scripts/injected_company_branch.py'
        source.write_text('def decide(ticker):\n    return ticker == "F"\n')
        policy_path=root/'config/main_scalability_exemptions_v1.json';policy=json.loads(policy_path.read_text())
        policy['entries'].append({'file':'scripts/injected_company_branch.py','line':2,
            'literal':'F','type':'ticker','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'source_size':source.stat().st_size,'context_kind':'NATIVE_FACT_REFERENCE_PREFIX'})
        policy_path.write_text(json.dumps(policy))
        with self.assertRaisesRegex(ValueError,'NOT_PRESENT_OR_NOT_PROVEN'):
            successor_scalability_snapshot(root,policy_path='config/main_scalability_exemptions_v1.json')

    def test_partial_or_alias_successor_installation_fails_closed(self):
        root=self.fixture();(root/'tools/check_main_scalability.py').unlink()
        with self.assertRaisesRegex(PublicationError,'successor installation is incomplete'):
            _execute_scalability_audit(repo_root=root)
        root=self.fixture();policy=root/'config/main_scalability_exemptions_v1.json';policy.unlink()
        policy.symlink_to(REPO_ROOT/'config/main_scalability_exemptions_v1.json')
        with self.assertRaisesRegex(PublicationError,'successor installation is incomplete'):
            _execute_scalability_audit(repo_root=root)


if __name__ == '__main__':
    unittest.main()
