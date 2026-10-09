from pathlib import Path
import fcntl,sys,importlib.util,tempfile,json
from types import SimpleNamespace
from unittest.mock import patch
T=Path(__file__).resolve().parents[1];runtime=T/'runtime';sys.dont_write_bytecode=True;sys.path[:0]=[str(T/'dependencies'),str(runtime/'scripts'),str(runtime)]
from vnext import ordinary_isolated_publication as old,publication as pub
mode=sys.argv[1]
if mode=='old':guard=old
else:
 path=Path(__file__).with_name('ordinary_isolated_publication_candidate.py')
 spec=importlib.util.spec_from_file_location('vnext.ordinary_recovery_lock_candidate',path);guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
with tempfile.TemporaryDirectory() as temporary:
 root=Path(temporary).resolve();(root/'outputs').mkdir();lock=root/'outputs/active_publication.json.lock';lock.touch()
 selected={'publication_id':'selected','previous_publication_id':'previous'}
 with lock.open('a+b') as held:
  fcntl.flock(held,fcntl.LOCK_EX)
  returned='foreign' if mode=='foreign' else 'selected'
  with patch.object(guard,'_edge',return_value=(root,selected)),patch.object(pub.PublicationView,'_open_paths',return_value=SimpleNamespace(publication_id=returned)) as internal:
   try:guard.guard_mirror_repair(publication_root=root)
   except pub.PublicationError as e:
    assert mode=='foreign' and str(e)=='ORDINARY_PUBLICATION_MIRROR_EDGE_CHANGED',str(e)
    print(json.dumps({'mode':mode,'status':'FOREIGN_ACTIVE_REJECTED_WITH_REAL_LOCK_HELD','error':str(e)}),flush=True)
   else:
    assert mode!='foreign';assert internal.call_count==1
    print(json.dumps({'mode':mode,'status':'CORRECT_ACTIVE_VERIFIED_WITH_REAL_LOCK_HELD'}),flush=True)
