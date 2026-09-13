"""A real current B06 Run must retain amendment bytes and input decisions."""
import copy
import csv
import io
import json
import os
from pathlib import Path
import shutil
import socket
import unittest
from unittest.mock import patch

from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import normal_run_v3 as normal,run_store
from vnext.canonical import content_hash,sha256_file
from vnext.calculator import calculate_metric
from vnext.ordinary_projection import render_ordinary_run


@unittest.skipUnless(os.environ.get('B06_CURRENT_INPUT_MATERIAL_ROOT'),'Requires a fresh external material directory')
class CurrentDebtInputMaterialTest(unittest.TestCase):
    def test_actual_amendment_is_preserved_and_cannot_be_removed_or_self_approved(self):
        root=Path(os.environ['B06_CURRENT_INPUT_MATERIAL_ROOT']).resolve()
        self.assertFalse(root.exists());root.mkdir(parents=True)
        data,run=root/'data',root/'run';company='paramount_skydance_paramount_global'
        prepare=normal.prepare_case
        def checked_prepare(**kwargs):
            with original_sources_only():return prepare(**kwargs)
        # Guard source preparation, while allowing the installer to persist
        # immutable authority files in its new isolated output directory.
        with patch.object(normal,'prepare_case',side_effect=checked_prepare), \
             patch.object(socket.socket,'connect',side_effect=AssertionError('No network')), \
             patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')):
            normal.install_normal_inputs(data_root=data,company_id=company,metric_id='B06')
            created=normal.create_normal_run(data_root=data,run_dir=run,company_id=company,metric_id='B06')
            manifest,records,decisions=run_store._mechanically_replay_open_run(run_dir=run,repo_root=data,require_complete_results=True)
            rendered=render_ordinary_run(data_root=data,run_dir=run)
        self.assertEqual('OPEN',manifest['status']);self.assertEqual([],decisions)
        self.assertEqual(('EXACT','PUBLISHED','1.168049260241169930727785855'),
                         tuple(created['result'][k] for k in ['quality','publication','value']))
        case=normal.replay_case(data_root=data,manifest=manifest);packet=case['input_binding']['current_debt_input']
        self.assertEqual('INPUT_PROPERTY_PROVEN',packet['decision'])
        self.assertFalse(packet['debt_completeness_proven'])
        source=case['input_binding']['source_proof']
        self.assertTrue(source['complete_b06_proven'])
        self.assertEqual(('13658000000','3000000'),(source['carrying_amount'],source['roles']['finance_lease']['value']))
        public=next(csv.DictReader(io.StringIO(rendered['files']['metrics_matrix.csv'].decode())))
        self.assertEqual((created['result']['value'],'ratio'),(public['value'],public['unit']))
        amendment=packet['prepared_input']['amendments'][0]['accessionNumber']
        self.assertTrue(any(s['accession']==amendment for s in manifest['source_references']))
        proof=next(p for p in packet['source_proofs'] if p['accession']==amendment)
        for name,raw in rendered['files'].items():
            (root/name).write_bytes(raw)
        for name,value in [('lease-counted-twice','13661000000'),('predecessor-total-used','14501000000')]:
            facts=copy.deepcopy(case['selection']['audit']['measurement_reconciliation']['calculation_facts'])
            chosen=next(f for f in facts if f['concept']=='us-gaap:DebtAndCapitalLeaseObligations')
            chosen['value']=value;chosen['fact_id']='fact:'+content_hash(value={k:v for k,v in chosen.items() if k!='fact_id'})
            target={k:v for k,v in case['traces']['B06']['calculation_target'].items() if k!='metric_id'}
            false_result,false_trace,observations=calculate_metric(compiled_spec=case['compiled_specs']['B06'],
                target=target,company_traits=manifest['company_traits'],structured_facts=facts,verified_observations=[])
            self.assertEqual('EXACT',false_result['quality']);self.assertNotEqual(created['result']['value'],false_result['value'])
            attack=root/name;shutil.copytree(run,attack)
            changed=[*case['source_records'],*observations,false_trace,false_result]
            (attack/'records.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in changed))
            with self.assertRaisesRegex(ValueError,'COMPLETE_COMPUTATION_GRAPH_CHANGED'):
                run_store._mechanically_replay_open_run(run_dir=attack,repo_root=data,require_complete_results=True)
        old_spec=root/'historical-spec';shutil.copytree(run,old_spec)
        old_manifest=copy.deepcopy(manifest);old_path='catalog/r5/B06_new_source_v2.md'
        old_manifest['spec_file_hashes']={old_path:sha256_file(path=data/old_path)}
        (old_spec/'manifest.json').write_text(json.dumps(old_manifest,ensure_ascii=False,indent=2)+'\n')
        with self.assertRaisesRegex(ValueError,'SOURCE_SPEC_OR_PERIOD_CHANGED'):
            run_store._mechanically_replay_open_run(run_dir=old_spec,repo_root=data,require_complete_results=True)
        changed_data,changed_run=root/'missing-amendment/data',root/'missing-amendment/run'
        shutil.copytree(data,changed_data);shutil.copytree(run,changed_run)
        (changed_data/proof['request_repo_relative_path']).unlink()
        with self.assertRaisesRegex(run_store.RunStoreError,'Run RawBlob bytes changed'):
            run_store._mechanically_replay_open_run(run_dir=changed_run,repo_root=changed_data,require_complete_results=True)
        forged_data,forged_run=root/'self-approved-input/data',root/'self-approved-input/run'
        shutil.copytree(data,forged_data);shutil.copytree(run,forged_run)
        changed=copy.deepcopy(manifest);key=changed['run_id'][len(normal.PREFIX):]
        path=forged_data/normal.BINDING_DIRECTORY/(key+'.json');binding=json.loads(path.read_text())
        binding['input_binding']['current_debt_input']['checks']=[]
        binding['input_binding']['current_debt_input']['prepared_input']['amendments']=[]
        new_key=content_hash(value=binding)[7:]
        (forged_data/normal.BINDING_DIRECTORY/(new_key+'.json')).write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n')
        changed['run_id']=normal.PREFIX+new_key
        (forged_run/'manifest.json').write_text(json.dumps(changed,ensure_ascii=False,indent=2)+'\n')
        with self.assertRaisesRegex(ValueError,'INPUT_BINDING_CHANGED'):
            run_store._mechanically_replay_open_run(run_dir=forged_run,repo_root=forged_data,require_complete_results=True)
        (root/'summary.json').write_text(json.dumps({'status':'PASS','actual_run_status':'OPEN','result':created['result'],
            'amendment_retained':amendment,'attacks':5,
            'calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False},indent=2)+'\n')


if __name__=='__main__':unittest.main()
