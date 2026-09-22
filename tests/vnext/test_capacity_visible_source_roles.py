"""Narrative-role admission never takes a model's explanation as source proof."""
import unittest
from vnext.capacity_quantity_roles import validate_visible_source_label_roles

class VisibleSourceRoleTest(unittest.TestCase):
    def check(self, text, kind, reason='Correct label according to the model.'):
        return validate_visible_source_label_roles(findings=[{'unit_id':'unit','kind':kind,
            'subject':'TARGET_REGISTRANT','timing':'CURRENT_REPORT','reason':reason,
            'resolved_evidence':[{'kind':'VISIBLE_BLOCK','source_index':1,'text':text}]}])
    def test_unrelated_sources_do_not_acquire_capacity_from_label_or_reason(self):
        cases=[('Shares remain available for issuance under the employee stock purchase plan.','PRODUCT_STORAGE_OR_INSTALLED_CAPACITY'),
               ('The company settled its outstanding convertible notes in cash.','PLANNED_CAPACITY'),
               ('Audit Committee information is incorporated by reference from the proxy statement.','PLANNED_CAPACITY'),
               ('Inventory costs are allocated based on normal utilization of our manufacturing facility.','PRODUCT_STORAGE_OR_INSTALLED_CAPACITY'),
               ('Purchase obligations for component inventory follow our production forecast.','CAPACITY_QUALITATIVE')]
        for text,kind in cases:
            with self.subTest(text=text):self.assertTrue(self.check(text,kind,'We plan manufacturing capacity of5million units.'))
    def test_supported_narrative_roles_and_mixed_block(self):
        for text,kind in [('Our manufacturing capacity is constrained.','CAPACITY_QUALITATIVE'),
                          ('Normal utilization of our manufacturing facility determines cost allocation.','CAPACITY_QUALITATIVE'),
                          ('We plan to expand our manufacturing capacity.','PLANNED_CAPACITY'),
                          ('The battery has a storage capacity of5 kWh.','PRODUCT_STORAGE_OR_INSTALLED_CAPACITY'),
                          ('Shares are available for issuance. The battery has capacity of 5 kWh.','PRODUCT_STORAGE_OR_INSTALLED_CAPACITY')]:
            with self.subTest(text=text):self.assertFalse(self.check(text,kind))
    def test_negated_hypothetical_or_disconnected_plan_is_not_proven(self):
        for text in ['We do not plan to expand manufacturing capacity.',
                     'If demand improves, we could expand production capacity.',
                     'We plan to repay notes. Manufacturing capacity is unchanged.',
                     'We plan to repay notes while our production capacity is unchanged.',
                     'We plan to reduce costs in manufacturing capacity management.']:
            with self.subTest(text=text):self.assertTrue(self.check(text,'PLANNED_CAPACITY'))
