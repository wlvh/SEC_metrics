"""Opt-in ordinary integrated OPEN Runs and actual on-disk adversarial graphs."""
import copy
import json
import os
from pathlib import Path
import shutil
import socket
import time
import traceback
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from tests.vnext.test_normal_run_material import _fresh_output, _protected
from vnext import normal_run_v3 as normal, run_store
from vnext.batch_workflow import _structured_concepts
from vnext.calculator import calculate_metric
from vnext.canonical import content_hash, sha256_file
from vnext.sources import companyfacts_structured_facts


def save(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")


def read_records(run):
    return [json.loads(line) for line in (run/'records.jsonl').read_text().splitlines()]


def write_records(run, records):
    (run/'records.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in records))


@unittest.skipUnless(os.environ.get('NORMAL_V14_MATERIAL_ROOT'),'Requires an explicit fresh external material root')
class OrdinaryIntegratedMaterialTest(unittest.TestCase):
    def test_real_open_graphs_and_disk_rejections(self):
        output=_fresh_output(os.environ['NORMAL_V14_MATERIAL_ROOT'])
        self.output=output;self.rows=[];self.stage='SETUP';self.bases={}
        from vnext.requirements import load_requirement_snapshot
        requirement=load_requirement_snapshot(snapshot_dir=ROOT/'requirements'/normal.REQUIREMENT_ID)
        paths=set(requirement['execution_authority']['files'])
        paths.update(str(p.relative_to(ROOT)) for p in (ROOT/'requirements'/normal.REQUIREMENT_ID).iterdir())
        paths.add('tests/vnext/test_normal_run_v3_material.py')
        self.identity={p:sha256_file(path=ROOT/p) for p in paths}
        before=_protected()
        prepare=normal.prepare_case
        def guarded_prepare(**kwargs):
            with original_sources_only():return prepare(**kwargs)
        with patch.object(normal,'prepare_case',side_effect=guarded_prepare), \
             patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden')), \
             patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS forbidden')), \
             patch.object(run_store,'validate_and_freeze_run',side_effect=AssertionError('No freeze in this material')) as freeze:
            for company,metric in [('marriott_international','B03'),('salesforce','B12'),('marriott_international','D01'),('macys','B08'),('marriott_international','E03')]:
                self.check('positive-'+metric,lambda c=company,m=metric:self.baseline(c,m))
            for name,metric,mutate in [
                ('missing-dependency-spec','B03',lambda m,d,r:m['spec_file_hashes'].pop('catalog/metrics/B01_revenue.md')),
                ('extra-unrequested-spec','B03',lambda m,d,r:m['spec_file_hashes'].update({'catalog/ordinary_zero_ai/B04.md':sha256_file(path=d/'catalog/ordinary_zero_ai/B04.md')})),
                ('missing-source-reference','B03',lambda m,d,r:m.update(source_references=m['source_references'][1:])),
                ('changed-fiscal-label','B12',lambda m,d,r:m['target_period'].update(fiscal_year=2025)),
                ('missing-dependency-result','B03',self.remove_dependency),
                ('missing-event-claim','E03',self.remove_claim),
                ('self-consistent-false-revenue','B03',self.false_revenue),
                ('missing-text-review','D01',lambda m,d,r:(r/'review_decisions.jsonl').write_text('')),
            ]:
                self.check(name,lambda m=metric,n=name,f=mutate:self.attack(m,n,f),reject=True)
            self.check('rehashed-input-primary-change',self.changed_primary_binding,reject=True)
            self.check('draft-freeze-rejection',lambda:normal.create_normal_run(data_root=self.bases['B03'][0],
                run_dir=output/'forbidden-frozen-run',company_id='marriott_international',metric_id='B03',freeze=True),
                reject=True,stage_required=None)
            self.assertEqual(0,freeze.call_count)
        self.assertEqual(before,_protected())
        save(output/'index.json',{'cases':self.rows,'protected_before':before,'protected_after':_protected(),
            'calls':{'provider':0,'paid':0,'sec':0},'freeze_calls':0})
        self.assertTrue(all(r['passed'] for r in self.rows),str([r for r in self.rows if not r['passed']]))

    def check(self,name,action,reject=False,stage_required='REPLAY'):
        start=time.monotonic();self.stage='SETUP';row={'case':name,'expected':'REJECT' if reject else 'PASS'}
        try:
            self.assertEqual(self.identity,{p:sha256_file(path=ROOT/p) for p in self.identity},'Material code or rule bytes changed')
            row['details']=action();row['passed']=not reject;row['outcome']='ACCEPTED'
        except Exception as error:
            expected_messages = {
                'missing-dependency-spec':('Run Spec closure cannot be compiled',),
                'extra-unrequested-spec':('ORDINARY_INTEGRATED_SOURCE_SPEC_OR_PERIOD_CHANGED',),
                'missing-source-reference':('ORDINARY_INTEGRATED_SOURCE_SPEC_OR_PERIOD_CHANGED',),
                'changed-fiscal-label':('ORDINARY_INTEGRATED_SOURCE_SPEC_OR_PERIOD_CHANGED',),
                'missing-dependency-result':('ORDINARY_INTEGRATED_COMPLETE_COMPUTATION_GRAPH_CHANGED',),
                'missing-event-claim':('ORDINARY_INTEGRATED_COMPLETE_COMPUTATION_GRAPH_CHANGED',),
                'self-consistent-false-revenue':('ORDINARY_INTEGRATED_COMPLETE_COMPUTATION_GRAPH_CHANGED',),
                'missing-text-review':('Review unit has no effective decision',),
                'rehashed-input-primary-change':('ORDINARY_INTEGRATED_INPUT_BINDING_CHANGED',),
                'draft-freeze-rejection':('ORDINARY_INTEGRATED_DRAFT_FREEZE_DISABLED',),
            }
            expected=reject and isinstance(error,(ValueError,run_store.RunStoreError)) and (stage_required is None or self.stage==stage_required)
            expected=expected and any(message in str(error) for message in expected_messages.get(name,()))
            row.update(passed=expected,outcome='REJECTED' if expected else 'FAILED',error_type=type(error).__name__,reason=str(error),stage=self.stage)
            (self.output/(name+'-trace.log')).write_text(traceback.format_exc())
        row['seconds']=round(time.monotonic()-start,3);self.rows.append(row)
        save(self.output/'progress.json',self.rows)

    def replay(self,data,run):
        self.stage='REPLAY'
        manifest,records,decisions=run_store._mechanically_replay_open_run(run_dir=run,repo_root=data,require_complete_results=True)
        self.assertEqual('OPEN',manifest['status'])
        return manifest,records,decisions

    def baseline(self,company,metric):
        root=self.output/'baselines'/metric;data,run=root/'data',root/'run'
        normal.install_normal_inputs(data_root=data,company_id=company,metric_id=metric)
        result=normal.create_normal_run(data_root=data,run_dir=run,company_id=company,metric_id=metric,freeze=False)
        manifest,records,decisions=self.replay(data,run)
        self.bases[metric]=(data,run)
        metrics={r['metric_id'] for r in records if r['record_type']=='METRIC_RESULT'}
        self.assertEqual({'B01','B03'} if metric=='B03' else {metric},metrics)
        if metric=='D01':self.assertEqual(['SYSTEM'],[d['reviewer_type'] for d in decisions])
        if metric=='B12':self.assertEqual({'fiscal_year':2026,'period_start':'2026-01-31','period_end':'2026-01-31'},manifest['target_period'])
        if metric=='B08':self.assertEqual({'fiscal_year':2025,'period_start':'2026-01-31','period_end':'2026-01-31'},manifest['target_period'])
        save(root/'outcome.json',result)
        return {'run_id':manifest['run_id'],'metric_ids':sorted(metrics),'status':manifest['status'],'review_count':len(decisions)}

    def attack(self,metric,name,change):
        data,base=self.bases[metric];run=self.output/'attacks'/name/'run'
        run.parent.mkdir(parents=True);shutil.copytree(base,run)
        manifest=json.loads((run/'manifest.json').read_text())
        change(manifest,data,run);save(run/'manifest.json',manifest)
        self.replay(data,run)

    @staticmethod
    def remove_dependency(manifest,data,run):
        records=read_records(run)
        write_records(run,[r for r in records if not (r['record_type'] in {'METRIC_RESULT','EXECUTION_TRACE'} and r.get('metric_id')=='B01')])

    @staticmethod
    def remove_claim(manifest,data,run):
        records=read_records(run)
        claim=next(r for r in records if r['record_type']=='DETERMINISTIC_VERIFIED_CLAIM')
        records.remove(claim);write_records(run,records)

    @staticmethod
    def false_revenue(manifest,data,run):
        case=normal.replay_case(data_root=data,manifest=manifest)
        component=case['input_binding']['component']
        prepared=component['prepared_input']
        source=next(r for r in case['references'] if r['source_role']=='companyfacts')
        raw=(data/prepared['companyfacts_input']['source_repo_relative_path']).read_bytes()
        concepts=sorted({c for spec in case['compiled_specs'].values() for c in _structured_concepts(compiled_spec=spec)})
        facts=companyfacts_structured_facts(raw_bytes=raw,source_reference=source,approved_concepts=concepts,
            allowed_ciks=[prepared['entity']],include_instant=False)
        target=case['traces']['B03']['calculation_target']
        target={k:v for k,v in target.items() if k!='metric_id'}
        changed=0
        for fact in facts:
            if fact['concept']=='us-gaap:Revenues' and fact['accession']==target['accession'] and fact['period_start']==target['period_start'] and fact['period_end']==target['period_end']:
                fact['value']='30000000000';changed+=1
        if not changed:raise AssertionError('Original source revenue fact was not found')
        result1,trace1,observations1=calculate_metric(compiled_spec=case['compiled_specs']['B01'],target=target,
            company_traits=manifest['company_traits'],structured_facts=facts,verified_observations=[])
        result3,trace3,observations3=calculate_metric(compiled_spec=case['compiled_specs']['B03'],target=target,
            company_traits=manifest['company_traits'],structured_facts=facts,verified_observations=observations1)
        if result1['value']!='30000000000' or result3['value']==case['results']['B03']['value']:
            raise AssertionError('False source facts did not produce a changed complete graph')
        records=[*case['source_records'],*observations1,trace1,result1,*observations3,trace3,result3]
        write_records(run,list({content_hash(value=r):r for r in records}.values()))

    def changed_primary_binding(self):
        original_data,original_run=self.bases['B03'];root=self.output/'attacks'/'changed-input-primary'
        data,run=root/'data',root/'run';root.mkdir(parents=True)
        shutil.copytree(original_data,data);shutil.copytree(original_run,run)
        manifest=json.loads((run/'manifest.json').read_text());key=manifest['run_id'][len(normal.PREFIX):]
        binding=json.loads((data/normal.BINDING_DIRECTORY/(key+'.json')).read_text())
        binding['primary_metric_id']='B01';new_key=content_hash(value=binding)[7:]
        save(data/normal.BINDING_DIRECTORY/(new_key+'.json'),binding)
        manifest['run_id']=normal.PREFIX+new_key;save(run/'manifest.json',manifest)
        self.replay(data,run)
