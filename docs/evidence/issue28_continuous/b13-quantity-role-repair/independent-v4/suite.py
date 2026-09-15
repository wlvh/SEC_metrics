import sys,unittest,socket
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True
import vnext
vnext.__path__.insert(0,'/tmp/sec_metrics_issue28_continuous/b13-role-proof-independent-review/v4/overlay/scripts/vnext')
suite=unittest.defaultTestLoader.loadTestsFromNames(['tests.vnext.test_capacity_quantity_roles','tests.vnext.test_capacity_text_results','tests.vnext.test_capacity_utilization_source.CapacityComparisonTest'])
with patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS forbidden')):
 result=unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
