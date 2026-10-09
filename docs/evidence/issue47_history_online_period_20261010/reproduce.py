"""Constructed dispatch control; no ledger, sources, network or business result."""
import contextlib,io,json
from unittest.mock import patch
from tools.vnext_company import main
cases=[('historical-range',['--period','fiscal-years','--fiscal-year-start','2021','--fiscal-year-end','2025']),('latest-with-history-years',['--period','latest-complete-fy','--fiscal-year-start','2021','--fiscal-year-end','2025'])]
observations=[]
for name,period in cases:
 with patch('vnext.company_online.run_online_company',return_value={'status':'FLOW_COMPLETED'}) as online,contextlib.redirect_stdout(io.StringIO()) as output:
  rc=main(['run','--company','ford_motor_company',*period,'--metric','B01','--call-context','/constructed/not-read-context.json','--work-dir','/constructed/state','--output-dir','/constructed/output'])
 observations.append({'case':name,'requested_period_arguments':period,'returncode':rc,'online_called':online.called,'online_argument_names':sorted(online.call_args.kwargs),'period_forwarded':'period' in online.call_args.kwargs,'years_forwarded':any('fiscal_year' in k for k in online.call_args.kwargs),'stdout':output.getvalue()})
print(json.dumps({'constructed_control':True,'business_result_created':False,'ledger_or_network_access':False,'observations':observations},indent=2))
