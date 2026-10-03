import importlib.util,sys,unittest
from pathlib import Path
import vnext
stage=Path('/tmp/sec_metrics_issue28_continuous/optional-prior-html')
for name in ['normal_source_requirements','ordinary_refresh_cycle']:
 spec=importlib.util.spec_from_file_location('vnext.'+name,stage/'scripts/vnext'/f'{name}.py');m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;setattr(vnext,name,m);spec.loader.exec_module(m)
suite=unittest.defaultTestLoader.loadTestsFromName('tests.vnext.test_prior_html_dependency')
result=unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful()else 1)
