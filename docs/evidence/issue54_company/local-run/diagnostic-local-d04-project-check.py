import json,pathlib,sys
sys.path[:0]=['/workspace/work/sec-company-compute','/workspace/work/sec-company-compute/scripts']
from vnext.company_processing_read import project_capture_identity
from vnext.capacity_update_input import source_equivalence
old=json.load(open('/workspace/work/company-d04-live-processing/processing-source.json'))
new=json.load(open(next(pathlib.Path('/workspace/work/local-recorded-d04/state').rglob('current-semantic-source.json'))))
projected,proof=project_capture_identity(new,old)
print('projected',bool(proof))
try:
 result=source_equivalence(current=projected,original=old)
 print(json.dumps(result))
except Exception as err:print(type(err).__name__,str(err));raise
