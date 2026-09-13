import hashlib,json,pathlib,sys
sys.path[:0]=['/Users/lyuhongwang/Developer/SEC_metrics','/Users/lyuhongwang/Developer/SEC_metrics/scripts']
from tests.vnext.test_annual_amendment_scope import AnnualAmendmentScopeTest
out=pathlib.Path('/tmp/sec_metrics_issue28_continuous/amendment-prefix-first');out.mkdir(exist_ok=False)
root=pathlib.Path('/Users/lyuhongwang/Developer/SEC_metrics')
for name in ['scripts/vnext/annual_amendment_scope.py','config/annual_amendment_scope_v1.json']:
 raw=(root/name).read_bytes();(out/pathlib.Path(name).name).write_bytes(raw)
 print(name,hashlib.sha256(raw).hexdigest())
AnnualAmendmentScopeTest.setUpClass();t=AnnualAmendmentScopeTest()
transforms={
 'earlier_extra_purpose':lambda raw:raw.replace(b'to correct the hyperlink',b'to revise reported revenue and to correct the hyperlink',1),
 'different_declared_exhibit':lambda raw:raw.replace(b'for Exhibit 3.2,',b'for Exhibit 10.2,',1),
 'different_declared_original_year':lambda raw:raw.replace(b'for the fiscal year ended December 31, 2025',b'for the fiscal year ended December 31, 2024',1),
}
for name,transform in transforms.items():
 raw=t.arguments()['amendment']['raw'];changed=transform(raw);(out/(name+'.htm')).write_bytes(changed)
 result=t.changed(transform);(out/(name+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(name,{'classification':result['classification'],'unchanged_input_classes':result['unchanged_input_classes'],'raw_sha256':hashlib.sha256(changed).hexdigest()})
