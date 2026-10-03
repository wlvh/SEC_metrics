from pathlib import Path
import sys,socket,traceback
from unittest.mock import patch
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path.insert(0,str(R/'scripts'))
from vnext.normal_run_v3 import install_normal_inputs,create_normal_run
T=Path('/private/tmp/sec_metrics_issue28_continuous/ci780d9ba-native-reproduction');assert not T.exists()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch('sec_http.urlopen',side_effect=AssertionError('NO_SEC')):
 try:
  install_normal_inputs(data_root=T/'data',company_id='marriott_international',metric_id='B01')
  create_normal_run(data_root=T/'data',run_dir=T/'run',company_id='marriott_international',metric_id='B01')
 except Exception:
  traceback.print_exc();raise
