"""Compare the original union against the narrow duplicate-blob correction."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch
from tests.vnext.test_selected_event_source_v1 import SelectedEventSourceTest
base = '3d6030b1bc5e1e7b22833a0101fbeb8f88341498'
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp)/'original.py'
    path.write_bytes(subprocess.check_output(['git','show',base+':scripts/vnext/normal_zero_ai_results.py']))
    spec = importlib.util.spec_from_file_location('scripts.vnext._original_union',path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    control = SelectedEventSourceTest(); control.setUp()
    try:
        control.add_issuer('2041610','0002041610-25-000011')
        control.add_issuer('813828','0000813828-25-000012')
        def original(**kwargs):
            # The original signature has no validator argument; use its own
            # untouched default, rather than patching its source/body parser.
            assert kwargs.pop('history_validator') is None
            return module._registered_event_sources(**kwargs)
        try:
            with patch('scripts.vnext.selected_event_source_v1._registered_event_sources',original):
                control.read(company='paramount_skydance_paramount_global',cik='2041610',registered_union=True)
        except ValueError as error:
            assert str(error)=='NORMAL_REGISTERED_EVENT_RECORD_CONFLICT'
            print('ORIGINAL_MAIN:',str(error))
        else: raise AssertionError('Original should reject duplicate-location raw blob')
        output = control.read(company='paramount_skydance_paramount_global',cik='2041610',registered_union=True)
        print('FIXED:',len(output['claims']),'claims;',len(output['source_proofs']),'exact proofs; no Result/Run')
    finally: control.doCleanups()
