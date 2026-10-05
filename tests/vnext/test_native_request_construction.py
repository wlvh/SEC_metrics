from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json,tempfile,unittest,hashlib
from unittest.mock import patch
from vnext import native_request_construction as cache,continuous_semantic_calls as calls,continuous_request_context as context
from vnext.canonical import content_hash,canonical_json_bytes
from vnext.offline_execution_session import OfflineSessionError
from vnext.requirements import load_requirement_snapshot
from vnext.normal_source_authority import ROOT
from tests.vnext.test_native_request_variants import synthetic_source

class RequestConstructionScopeTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.requirement=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
 def setUp(self):
  self.source,_=synthetic_source();self.source['request_context_format']=context.FORMAT_VERSION;self.seal(self.source)
 def seal(self,s):s['semantic_source_id']=content_hash(value={k:v for k,v in s.items()if k!='semantic_source_id'});return s
 def test_full_input_raw_unicode_and_changed_source_id_do_not_share_entries(self):
  nfc=deepcopy(self.source);nfc['documents'][0]['registrant_name_binding']={'name':'Café'};self.seal(nfc)
  nfd=deepcopy(nfc);nfd['documents'][0]['registrant_name_binding']['name']='Cafe\u0301';self.seal(nfd)
  self.assertEqual(nfc['semantic_source_id'],nfd['semantic_source_id'])
  with cache.request_construction_session(self.requirement)as scope:
   first=calls.source_requests(nfc);second=calls.source_requests(nfd)
   self.assertEqual(scope.builds,2);self.assertNotEqual(cache._raw(first),cache._raw(second));self.assertEqual(second[0]['document_context']['registrant_name_binding']['name'],'Cafe\u0301')
   changed=deepcopy(nfd);changed['construction_provenance_test']='new original source bytes';self.seal(changed)
   third=calls.source_requests(changed);self.assertEqual(scope.builds,3);self.assertNotEqual(second[0]['source_id'],third[0]['source_id'])
 def test_returned_nested_objects_cannot_mutate_stored_bytes(self):
  with cache.request_construction_session(self.requirement)as scope:
   first=calls.source_requests(self.source);raw=calls._json(first)
   first[0]['document_context']['registrant_name_binding']['caller_mutation']='Changed'
   again=calls.source_requests(deepcopy(self.source));self.assertEqual(calls._json(again),raw);self.assertEqual((scope.builds,scope.hits),(1,1))
  self.assertEqual(scope.entries,{});self.assertEqual(scope.size,0)
  with cache.request_construction_session(self.requirement)as fresh:
   self.assertEqual(calls._json(calls.source_requests(self.source)),raw);self.assertEqual(fresh.builds,1)
 def test_input_mutation_with_stale_identity_is_not_a_cache_hit(self):
  with cache.request_construction_session(self.requirement)as scope:
   calls.source_requests(self.source);self.source['units'][0]['payload']['blocks'][0]['text']='Changed source'
   with self.assertRaisesRegex(ValueError,'COMPLETE_SOURCE_REQUIRED'):calls.source_requests(self.source)
   self.assertEqual(scope.hits,0)
 def test_dictionary_order_preserved_for_deterministic_constructor_input(self):
  changed=dict(reversed(list(self.source.items())))
  with cache.request_construction_session(self.requirement)as scope:
   original=calls.source_requests(self.source);reordered=calls.source_requests(changed)
   self.assertEqual(scope.builds,2);self.assertEqual(calls._json(original),calls._json(reordered))
 def test_actual_rule_file_change_latches_failed_even_after_restore(self):
  from vnext import d04_native_assessment as native
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp).resolve();p=native.COMPLETE_POLICY_PATH;(root/p).parent.mkdir(parents=True)
   raw=(ROOT/p).read_bytes();(root/p).write_bytes(raw)
   requirement={'requirement_closure_hash':'probe-bound-current-rule','execution_authority':{'files':{p:{'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}}}}
   with patch.object(cache,'ROOT',root),patch.object(native,'ROOT',root):
    with self.assertRaisesRegex(OfflineSessionError,'SCOPE_FAILED'):
     with cache.request_construction_session(requirement)as scope:
      calls.source_requests(self.source)
      changed=json.loads(raw);changed['system_prompt']+=' Altered rule.';(root/p).write_text(json.dumps(changed))
      with self.assertRaisesRegex(OfflineSessionError,'RULE_CHANGED'):calls.source_requests(self.source)
      (root/p).write_bytes(raw)
      with self.assertRaisesRegex(OfflineSessionError,'SCOPE_FAILED'):calls.source_requests(self.source)
 def test_format_limit_and_tokenizer_state_changes_reject_cached_output(self):
  import tokenizers
  for module,field,value in [(context,'OUTPUT_RESERVE',4095),(context,'MAX_CONTEXT',199999),(tokenizers,'__version__','unsupported')]:
   with self.subTest(field=field):
    with self.assertRaisesRegex(OfflineSessionError,'SCOPE_FAILED'):
     with cache.request_construction_session(self.requirement)as scope:
      calls.source_requests(self.source)
      with patch.object(module,field,value),self.assertRaisesRegex(OfflineSessionError,'FORMAT_OR_ENGINE_CHANGED'):calls.source_requests(self.source)
 def test_tokenizer_object_state_cannot_silently_change_between_hits(self):
  tokenizer,_=context._load_tokenizer()
  try:
   with self.assertRaisesRegex(OfflineSessionError,'SCOPE_FAILED'):
    with cache.request_construction_session(self.requirement):
     calls.source_requests(self.source);tokenizer.enable_truncation(17)
     with self.assertRaisesRegex(OfflineSessionError,'TOKENIZER_STATE_CHANGED'):calls.source_requests(self.source)
  finally:tokenizer.no_truncation()
 def test_source_authenticity_check_runs_again_with_warm_construction(self):
  self.source.setdefault('source_proofs',[]);self.seal(self.source)
  with cache.request_construction_session(self.requirement)as scope:
   request=calls.source_requests(self.source)[0];policy=calls.configured_transport_policy(requirement=self.requirement,repo_root=ROOT)
   prepared=calls.SemanticRequest(calls._FACTORY,calls._json(self.source),calls._json(request),calls.request_body(request,policy),calls._json(request['response_protocol']),self.requirement,SimpleNamespace(_check=lambda:None))
   calls.source_requests(json.loads(prepared.source_bytes))
   with patch.object(calls,'verify_saved_source_proofs',side_effect=[None,ValueError('CURRENT_SOURCE_AUTHENTICITY_REJECTED')])as verify:
    prepared.validate(policy);self.assertGreaterEqual(scope.hits,1)
    with self.assertRaisesRegex(ValueError,'CURRENT_SOURCE_AUTHENTICITY_REJECTED'):prepared.validate(policy)
    self.assertEqual(verify.call_count,2)
 def test_existing_non_plain_json_types_use_original_constructor_without_cache(self):
  from decimal import Decimal
  self.source['extra_decimal']=Decimal('1.20');self.seal(self.source)
  expected=calls._construct_source_requests(self.source)
  with cache.request_construction_session(self.requirement)as scope:
   actual=calls.source_requests(self.source)
   self.assertEqual(calls._json(expected),calls._json(actual));self.assertEqual((scope.builds,scope.hits,scope.size),(1,0,0))
 def test_integer_key_cannot_hit_a_valid_string_key_entry(self):
  self.source['extra_mapping']={'1':'value'};self.seal(self.source)
  with cache.request_construction_session(self.requirement)as scope:
   calls.source_requests(self.source)
   invalid=deepcopy(self.source);invalid['extra_mapping']={1:'value'}
   self.assertEqual(cache._raw(self.source),cache._raw(invalid))
   with self.assertRaisesRegex(ValueError,'Canonical object keys must be strings'):
    calls._construct_source_requests(invalid)
   with self.assertRaisesRegex(ValueError,'Canonical object keys must be strings'):
    calls.source_requests(invalid)
   self.assertEqual(scope.hits,0)
 def test_tuple_and_container_subclasses_do_not_use_plain_json_entries(self):
  class DictSubclass(dict):pass
  class ListSubclass(list):pass
  for original,converted in [(['value'],('value',)),({'1':'value'},DictSubclass({'1':'value'})),(['value'],ListSubclass(['value']))]:
   with self.subTest(kind=type(converted).__name__):
    source=deepcopy(self.source);source['extra_container']=original;self.seal(source)
    with cache.request_construction_session(self.requirement)as scope:
     calls.source_requests(source)
     alternate=deepcopy(source);alternate['extra_container']=converted
     self.assertEqual(cache._raw(source),cache._raw(alternate))
     # The constructor, not JSON coercion, decides whether this type is legal.
     try:expected=calls._construct_source_requests(alternate)
     except Exception as error:
      with self.assertRaises(type(error)):calls.source_requests(alternate)
     else:self.assertEqual(calls.source_requests(alternate),expected)
     self.assertEqual(scope.hits,0);self.assertEqual(scope.builds,2)
 def test_non_plain_output_retains_original_types_and_is_not_cached(self):
  source=deepcopy(self.source)
  with cache.request_construction_session(self.requirement)as scope:
   for _ in range(2):
    result=scope.get(source,lambda value:{'tuple':('value',)})
    self.assertIs(type(result['tuple']),tuple)
   self.assertEqual((scope.builds,scope.hits,scope.size),(2,0,0))
 def test_nested_different_authority_rejects_and_size_bound_does_not_change_output(self):
  with cache.request_construction_session(self.requirement):
   with self.assertRaisesRegex(OfflineSessionError,'NESTED_RULES_CHANGED'):
    with cache.request_construction_session({**self.requirement,'requirement_closure_hash':'different'}):pass
  with patch.object(cache,'_MAX_BYTES',1),cache.request_construction_session(self.requirement)as scope:
   first=calls.source_requests(self.source);second=calls.source_requests(self.source)
   self.assertEqual(calls._json(first),calls._json(second));self.assertEqual((scope.builds,scope.hits,scope.size),(2,0,0))

if __name__=='__main__':unittest.main(verbosity=2)
