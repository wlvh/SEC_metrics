"""V6 uses the unchanged complete-source recorded Run lifecycle, not live credit."""
from unittest.mock import patch
import os
from tests.vnext import test_capacity_run_material as original
from vnext import capacity_run


class CapacityProgramRunMaterialTest(original.CapacityRunMaterialTest):
    def test_native_run_recorded_mode_exact_source_and_resigned_input_rejection(self):
        prepare=original.prepare_requests
        respond=original.recorded_response
        install=capacity_run.install_inputs
        def program_prepare(**kwargs):
            return prepare(**kwargs,program_quantity_roles=True)
        def program_response(request):
            result=respond(request)
            proof=request['program_quantity_contract']
            owned={(r['unit_id'],r['source_kind'],r['source_index'])
                   for r in proof['verified_quantity_roles']+proof['verified_nonphysical_references']}
            for unit in result['units']:
                unit['findings']=[f for f in unit['findings'] if not any(
                    (unit['unit_id'],e['kind'],e['source_index']) in owned for e in f['evidence'])]
            return result
        def program_install(**kwargs):
            return install(**kwargs,program_quantity_roles=True)
        with patch.dict(os.environ,{'B13_REFERENCE_CONTEXT':'1'}),\
             patch.object(original,'prepare_requests',side_effect=program_prepare),\
             patch.object(original,'recorded_response',side_effect=program_response),\
             patch.object(capacity_run,'install_inputs',side_effect=program_install):
            super().test_native_run_recorded_mode_exact_source_and_resigned_input_rejection()
