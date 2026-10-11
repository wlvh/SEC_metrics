"""Three failed original source paths; no company cache, network or source mutation."""
from pathlib import Path
import json,socket,sys,time
from decimal import Decimal
from unittest.mock import patch
from vnext.historical_statement_cases import prepare_historical_statement_year_case

source=Path(sys.argv[1]).resolve()
expected={2023:('14557','17478'),2024:('13108','14557'),2025:('12402','13108')}
records=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
    for year,(current,prior) in expected.items():
        started=time.monotonic()
        case=prepare_historical_statement_year_case(repo_root=source,
            company_id='lumen_technologies',metric_id='B02',fiscal_year=year)
        elapsed=time.monotonic()-started
        result=case['results']['B02']
        record={'year':year,'seconds':elapsed,'result':{k:result.get(k) for k in
            ('result_id','publication','value','unit','reason_code','period_start','period_end')},
            'scope_summary':{},'calls':[0,0,0]}
        scopes=case.get('input_assessments',{}).get('historical_statement',{}).get('paired_revenue_scopes',{})
        # Scope details may be exposed directly by the ordinary case assessment.
        if not scopes:
            for assessment in case.get('input_assessments',{}).values():
                if isinstance(assessment,dict) and 'paired_revenue_scopes' in assessment:
                    scopes=assessment['paired_revenue_scopes'];break
        for role,s in scopes.items():
            record['scope_summary'][role]={'complete_scope_proven':s['complete_scope_proven'],
                'status':s['status'],'reported_values':[x['total']['value'] for x in s.get('reported_totals',[])]}
        records.append(record)
        Path(__file__).with_name('eps-originals-results.json').write_text(json.dumps(records,indent=2)+'\n')
        assert result['publication']=='PUBLISHED' and result['unit']=='ratio',record
        assert Decimal(result['value'])==(Decimal(current)-Decimal(prior))/Decimal(prior),record
print(json.dumps(records,indent=2))
