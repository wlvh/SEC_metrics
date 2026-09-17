import vnext
vnext.__path__.insert(0,'/tmp/sec_metrics_issue28_continuous/native-update-patch/after/scripts/vnext')
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from contextlib import ExitStack
from vnext import continuous_semantic_calls as c
from vnext.continuous_call_ledger import CallLedger,_FACTORY
with TemporaryDirectory()as tmp,ExitStack()as stack:
 root=Path(tmp).resolve();fixed=root/'fixed';requirement={'policy':{'budget_root':str(fixed)}}
 for target in ('load_requirement_snapshot','validate_semantic_rule_bindings','load_delegation','configured_transport_policy'):
  stack.enter_context(patch.object(c,target,return_value=requirement if target=='load_requirement_snapshot'else None))
 stack.enter_context(patch('vnext.requirement_profile.validate_execution_authority'))
 stack.enter_context(patch.object(c.control,'prepare_successor_invocation_authority'))
 factory=stack.enter_context(patch('vnext.r6_semantic_source.prepare_d04_semantic_source',side_effect=AssertionError('SOURCE_FACTORY_NOT_REACHED')))
 live=CallLedger(factory=_FACTORY,root=fixed,binding={},live=True)
 wrong_live=CallLedger(factory=_FACTORY,root=root/'wrong',binding={},live=True)
 recorded=CallLedger(factory=_FACTORY,root=root/'recorded',binding={},live=False)
 tests=[('wrong-live-source',root/'arbitrary',live),('wrong-live-ledger',fixed/'source-inputs',wrong_live),('recorded-fixed-source',fixed/'source-inputs',recorded),('forged-ledger',fixed/'source-inputs',{'live':True})]
 for name,source,ledger in tests:
  try:c.prepare_requests(company_id='sample',metric_id='D04',native=True,source_root=source,source_ledger=ledger)
  except ValueError as e:print(name,str(e),flush=True)
  else:raise AssertionError(name+' accepted')
 factory.assert_not_called()
print('PASS 4 root/factory attacks; execution authority setup doubled, actual source-root gates exercised')
