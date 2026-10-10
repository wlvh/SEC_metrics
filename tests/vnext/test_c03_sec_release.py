"""Explicit SEC release selection retains C03's original business checks."""
import copy
import unittest

from tests.vnext.test_governance_signals import arguments, source
from vnext.governance_signals import GovernanceSignalError, replay_c03, resolve_c03


POLICY = 'YEAR_QUARTER_OR_DATE'


def released_source(rows, release='2022q4', **kwargs):
    return source(rows, ecd_uri='https://xbrl.sec.gov/ecd/'+release, **kwargs).replace(
        b'http://xbrl.sec.gov/dei/2025', ('https://xbrl.sec.gov/dei/'+release).encode())


class C03SecReleaseTest(unittest.TestCase):
    def resolve(self, raw):
        return resolve_c03(**arguments(raw), sec_namespace_release=POLICY)

    def test_old_default_remains_closed_and_explicit_proxy_can_complete(self):
        raw = released_source([{'amount':'1,234,567','person':'ex:PersonAMember'}])
        with self.assertRaisesRegex(GovernanceSignalError, 'C03_DEF14A_SOURCE_REQUIRED'):
            resolve_c03(**arguments(raw))
        resolved = self.resolve(raw)
        self.assertEqual(('PASS','1234567','USD'),
                         (resolved['result']['reason_code'],resolved['result']['value'],resolved['result']['unit']))
        self.assertEqual(POLICY, resolved['selection']['sec_namespace_release'])
        self.assertEqual(resolved, replay_c03(resolution=resolved, **arguments(raw),
                                            sec_namespace_release=POLICY))

    def test_explicit_year_quarter_and_date_releases_are_finite(self):
        for release in ('2025','2022q4','2022-10-31'):
            with self.subTest(release=release):
                self.assertEqual('100', self.resolve(released_source([{'amount':'100'}],release))['result']['value'])
        for release in ('22','2022q5','2023x','2022q4/other'):
            with self.subTest(release=release):
                with self.assertRaisesRegex(GovernanceSignalError, 'C03_DEF14A_SOURCE_REQUIRED'):
                    self.resolve(released_source([{'amount':'100'}],release))

    def test_foreign_ecd_namespace_and_axis_remain_rejected(self):
        raw = released_source([{'amount':'100'}]).replace(
            b'https://xbrl.sec.gov/ecd/2022q4', b'https://example.test/ecd/2022q4')
        with self.assertRaisesRegex(GovernanceSignalError, 'C03_ECD_TAXONOMY_REQUIRED'):
            self.resolve(raw)
        resolved = self.resolve(released_source([{'amount':'100','person':'ex:PersonAMember',
                                                   'dimension':'ex:GeographyAxis'}]))
        self.assertEqual('C03_TARGET_FACT_INVALID',resolved['selection']['reason_code'])

    def test_person_name_relation_uses_the_same_explicit_release(self):
        rows = [{'amount':'Person A','concept':'ecd:PeoName','person':'ex:PersonAMember'},
                {'amount':'100','person':'ex:PersonAMember'}]
        resolved = self.resolve(released_source(rows))
        self.assertEqual('100',resolved['result']['value'])
        self.assertEqual('Person A',resolved['selection']['reported_person_facts'][0]['name'])

    def test_multiple_people_period_entity_and_units_are_not_relaxed(self):
        cases = [([{'amount':'100','person':'ex:PersonAMember'},
                   {'amount':'200','person':'ex:PersonBMember'}],{},'C03_MULTIPLE_REPORTED_AMOUNTS'),
                 ([{'amount':'100','period_start':'2025-10-01'}],{},'C03_TARGET_PERIOD_NOT_FOUND'),
                 ([{'amount':'100','entity':'54321'}],{},'C03_TARGET_FACT_INVALID'),
                 ([{'amount':'100'}],{'measure':'money:EUR'},'C03_TARGET_FACT_INVALID')]
        for rows,kwargs,reason in cases:
            with self.subTest(reason=reason):
                resolved = self.resolve(released_source(rows,**kwargs))
                self.assertEqual(reason,resolved['selection']['reason_code'])
                self.assertIsNone(resolved['result']['value'])

    def test_policy_and_source_changes_do_not_replay_old_resolution(self):
        raw = released_source([{'amount':'100'}]);args=arguments(raw)
        resolved=self.resolve(raw)
        with self.assertRaisesRegex(GovernanceSignalError,'C03_DEF14A_SOURCE_REQUIRED'):
            replay_c03(resolution=resolved,**args)
        changed=copy.deepcopy(resolved);changed['selection']['sec_namespace_release']='YEAR_ONLY'
        with self.assertRaisesRegex(GovernanceSignalError,'C03_SOURCE_REPLAY_MISMATCH'):
            replay_c03(resolution=changed,**args,sec_namespace_release=POLICY)
        for invalid in ('ANY',None,[],'YEAR_OR_DATE_RELEASE'):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError,'SEC_NAMESPACE_POLICY_UNSUPPORTED'):
                    resolve_c03(**args,sec_namespace_release=invalid)

    def test_default_resolution_does_not_gain_a_policy_field(self):
        result=resolve_c03(**arguments(source([{'amount':'100'}])))
        self.assertNotIn('sec_namespace_release',result['selection'])

    def test_generic_member_does_not_become_a_second_specific_person(self):
        rows=[{'amount':'100'},{'amount':'100','person':'ecd:PeoMember'},
              {'amount':'100','person':'ex:PersonAMember'}]
        for release in ('2025','2022q4','2022-10-31'):
            with self.subTest(release=release):
                resolved=self.resolve(released_source(rows,release))
                self.assertEqual('100',resolved['result']['value'])
                self.assertEqual(1,len(resolved['selection']['specific_person_members']))
                two_people=self.resolve(released_source(rows+[
                    {'amount':'100','person':'ex:PersonBMember'}],release))
                self.assertEqual('C03_MULTIPLE_REPORTED_PEOPLE',two_people['selection']['reason_code'])
                foreign=self.resolve(released_source(rows+[
                    {'amount':'100','person':'ex:PeoMember'}],release))
                self.assertEqual('C03_MULTIPLE_REPORTED_PEOPLE',foreign['selection']['reason_code'])


if __name__ == '__main__':
    unittest.main()
