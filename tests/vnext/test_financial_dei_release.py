"""Explicit bank-source release hooks; no source selection or model calls."""
import unittest
from pathlib import Path
from unittest.mock import patch
from tests.vnext.test_dei_release_selection import annual, PERIOD, SUCCESSOR
from vnext.canonical import sha256_bytes
from vnext.composite_scope import index_source_structure
from vnext.financial_relationships import _issuer_identity, FinancialRelationshipError
from vnext.financial_candidates import inspect_lcr_disclosed_fact, FinancialCandidateError
from vnext.financial_balance_scope import _prepare
from vnext.normal_annual_input import NormalAnnualInputError

ROOT=Path(__file__).resolve().parents[2]


class FinancialDeiReleaseTest(unittest.TestCase):
    def issuer_source(self,namespace):
        return annual(namespace).replace(b'</html>',b'<ix:nonNumeric name="dei:EntityRegistrantName" contextRef="annual">Example Bank Inc.</ix:nonNumeric></html>')

    def test_issuer_successor_and_default_keep_exact_identity_checks(self):
        raw=self.issuer_source('http://xbrl.sec.gov/dei/2021q4')
        args={'source_bytes':raw,'expected_cik':'19617','target_period':PERIOD,
              'structure':index_source_structure(source_bytes=raw)}
        with self.assertRaisesRegex(FinancialRelationshipError,'ENTITY_REGISTRANT_NAME_NOT_UNIQUE'):
            _issuer_identity(**args)
        identity=_issuer_identity(**args,dei_release=SUCCESSOR)
        self.assertEqual(identity['native_name_facts'][0]['entity_cik'],'19617')
        with self.assertRaisesRegex(FinancialRelationshipError,'ENTITY_NAME_CONTEXT_CONFLICT'):
            _issuer_identity(**{**args,'expected_cik':'1'},dei_release=SUCCESSOR)

    def test_year_only_default_is_identical_to_explicit_on_ordinary_source(self):
        raw=self.issuer_source('http://xbrl.sec.gov/dei/2021')
        args={'source_bytes':raw,'expected_cik':'19617','target_period':PERIOD,
              'structure':index_source_structure(source_bytes=raw)}
        self.assertEqual(_issuer_identity(**args),_issuer_identity(**args,dei_release=SUCCESSOR))

    def test_var_prepare_uses_controlled_release_and_original_period(self):
        raw=annual();args={'repo_root':ROOT,'source_bytes':raw,'expected_source_sha256':sha256_bytes(content=raw),
            'expected_cik':'19617','target_period':PERIOD,'metric_id':'A12'}
        with self.assertRaisesRegex(NormalAnnualInputError,'DEI_MISSING_OR_AMBIGUOUS'):_prepare(**args)
        task,builders,structure=_prepare(**args,dei_release=SUCCESSOR)
        self.assertEqual(task['metric_ids'],['A12'])
        with self.assertRaisesRegex(NormalAnnualInputError,'DEI_SUBJECT_CONFLICT'):
            _prepare(**{**args,'expected_cik':'1'},dei_release=SUCCESSOR)

    def test_lcr_checks_source_hash_before_any_release_or_facts(self):
        raw=annual()
        with self.assertRaisesRegex(FinancialCandidateError,'SOURCE_BYTES_DIFFER'):
            inspect_lcr_disclosed_fact(repo_root=ROOT,source_bytes=raw,expected_source_sha256='0'*64,
                expected_cik='19617',target_period=PERIOD,dei_release=SUCCESSOR)

    def test_arbitrary_release_never_enters_shared_issuer_rules(self):
        raw=self.issuer_source('http://xbrl.sec.gov/dei/2021q4')
        with self.assertRaisesRegex(NormalAnnualInputError,'DEI_RELEASE_SELECTION_INVALID'):
            _issuer_identity(source_bytes=raw,expected_cik='19617',target_period=PERIOD,
                structure={},dei_release='.*')


if __name__=='__main__':unittest.main()
