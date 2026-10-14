"""One local transition from inline dispatch to selected registration data.

No fixed Git head/approval is required. Original saved code must be available
and match its recorded component digest; unknown logic changes reprocess.
"""
import ast
from hashlib import sha256
from pathlib import Path
import subprocess

STORE = 'scripts/vnext/ordinary_saved_result.py'
# One demonstrated old-record format transition; route-data additions do not change it.
DISPATCH_TRANSITION_V1 = '5b5939ad634738f42ef6392d13d322163d08dddd74aae811db3499c1943b73a2'
CORE_FUNCTIONS = ('_need','_json','_program_version','_validate_records','_save_case',
                  'read_saved_result','save_calculated_case','current_e01_scope')
CORE_IMPORTS = {'fcntl','json','Path','subprocess','time','write_immutable_bytes',
    'content_hash','sha256_bytes','sha256_file','strict_json_file','strict_json_loads','validate_record',
    'prepare_ordinary_zero_ai_run_input'}


def _component(tree, names):
    functions={node.name:node for node in tree.body if isinstance(node,ast.FunctionDef)}
    if not set(names)<=functions.keys():return None
    constants={node.targets[0].id:node.value for node in tree.body
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name)}
    if 'CURRENT_E01_SPEC_PATH' not in constants:return None
    imports=[]
    for node in tree.body:
        if isinstance(node,(ast.Import,ast.ImportFrom)):
            selected=[alias for alias in node.names if (alias.asname or alias.name) in CORE_IMPORTS]
            if selected:
                clone=ast.Import(names=selected) if isinstance(node,ast.Import) else ast.ImportFrom(module=node.module,names=selected,level=node.level)
                imports.append(ast.dump(clone,include_attributes=False))
    return (tuple(sorted(imports)),ast.dump(constants['CURRENT_E01_SPEC_PATH'],include_attributes=False),
            tuple(ast.dump(functions[name],include_attributes=False) for name in names))


def _old_source(manifest, expected, root):
    program=manifest.get('program_root')
    if program:
        file=Path(program)/STORE
        if file.is_file():
            try:raw=file.read_bytes()
            except OSError:raw=b''
            if sha256(raw).hexdigest()==expected:return raw
    commit=manifest.get('program_version',{}).get('commit')
    if type(commit) is str and len(commit)==40 and all(c in '0123456789abcdef' for c in commit):
        result=subprocess.run(['git','-C',str(root),'show',commit+':'+STORE],capture_output=True)
        if result.returncode==0 and sha256(result.stdout).hexdigest()==expected:return result.stdout
    # A recorded dirty tree may have been committed later. Search only the
    # local history of this one component; do not fetch, execute old code,
    # infer equivalence from a commit label or keep a version whitelist.
    history=subprocess.run(['git','-C',str(root),'rev-list','-n','64','HEAD','--',STORE],capture_output=True,text=True)
    # A shallow/local object store can stop traversal at a missing parent.
    # Each returned component is still checked independently against its digest.
    for candidate in history.stdout.splitlines():
        if len(candidate)!=40 or any(c not in '0123456789abcdef' for c in candidate):continue
        result=subprocess.run(['git','-C',str(root),'show',candidate+':'+STORE],capture_output=True)
        if result.returncode==0 and sha256(result.stdout).hexdigest()==expected:return result.stdout
    return None


def _legacy_registration(tree, metric):
    functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    outer=functions.get('create_saved_result')
    if outer is None:return None
    prepare=next((n for n in outer.body if isinstance(n,ast.FunctionDef) and n.name=='prepare'),None)
    if prepare is None:return None
    sets={}
    for node in tree.body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            value=node.value
            if isinstance(value,ast.Call) and isinstance(value.func,ast.Name) and value.func.id=='frozenset' and len(value.args)==1:
                try:sets[node.targets[0].id]=ast.literal_eval(value.args[0])
                except (ValueError,TypeError):pass
    def condition(test):
        if not isinstance(test,ast.Compare) or not isinstance(test.left,ast.Name) or test.left.id!='metric_id' or len(test.ops)!=1:return None
        right=test.comparators[0]
        if isinstance(test.ops[0],ast.Eq) and isinstance(right,ast.Constant):return metric==right.value
        if isinstance(test.ops[0],ast.In):
            if isinstance(right,ast.Name) and right.id in sets:return metric in sets[right.id]
            if isinstance(right,(ast.Set,ast.Tuple,ast.List)):
                try:return metric in ast.literal_eval(right)
                except (ValueError,TypeError):return None
        return None
    imports={};selected=None
    for node in prepare.body:
        body=[node]
        if isinstance(node,ast.If):
            decision=condition(node.test)
            if decision is None:return None
            if not decision:continue
            body=node.body
        for item in body:
            if isinstance(item,ast.ImportFrom):
                imports.update({alias.asname or alias.name:'vnext.'+item.module for alias in item.names})
            elif isinstance(item,ast.Return):selected=item.value;break
        if selected is not None:break
    if not isinstance(selected,ast.Call) or not isinstance(selected.func,ast.Name):return None
    name=selected.func.id
    if name in {'_ordinary_case','_current_financial_case'}:
        if selected.keywords or [ast.dump(a,include_attributes=False) for a in selected.args]!=[
                ast.dump(ast.Name(id=n,ctx=ast.Load()),include_attributes=False) for n in ('source','company_id','metric_id')]:return None
        return {'module':'vnext.ordinary_saved_result','function':name,'call_style':'positional3'}
    if name not in imports:return None
    keys={k.arg for k in selected.keywords}
    if selected.args:return None
    expected={'source_root':'source','repo_root':'source','company_id':'company_id','metric_id':'metric_id'}
    for keyword in selected.keywords:
        if keyword.arg in expected and (not isinstance(keyword.value,ast.Name)
                or keyword.value.id!=expected[keyword.arg]):return None
    if keys=={'source_root','company_id','metric_id'}:style='source_company_metric'
    elif keys=={'source_root','company_id'}:style='source_company'
    elif keys=={'repo_root','company_id','metric_id','rules_root'}:style='repo_company_metric_rules'
    else:return None
    if style=='repo_company_metric_rules':
        rules=next(k.value for k in selected.keywords if k.arg=='rules_root')
        expected_rules=ast.parse('Path(__file__).resolve().parents[2]',mode='eval').body
        if ast.dump(rules,include_attributes=False)!=ast.dump(expected_rules,include_attributes=False):return None
    return {'module':imports[name],'function':name,'call_style':style}


def _dispatch_transition_signature(tree, source):
    # Source segments are stable across supported Python versions. ast.dump
    # includes fields added by Python releases even when source is unchanged.
    wanted={'_route_catalog','selected_case_registration','create_saved_result'}
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
    if len(nodes)!=len(wanted):return None
    segments=[ast.get_source_segment(source,n) for n in sorted(nodes,key=lambda n:n.name)]
    if any(segment is None for segment in segments):return None
    return sha256('\n'.join(segments).encode()).hexdigest()



def same_registered_processing(previous,current,manifest,root):
    """Preserve an old conclusion only for the demonstrated mechanical split."""
    if 'saved_result_registration' in previous:return False
    old_hash=previous.get('processing_files',{}).get(STORE)
    if type(old_hash) is not str:return False
    old=_old_source(manifest,old_hash,root)
    if old is None:return False
    try:
        before=ast.parse(old)
        current_source=(Path(root)/STORE).read_text(encoding='utf-8')
        after=ast.parse(current_source)
    except (SyntaxError,UnicodeError):return False
    explicit='case_producer' in previous or 'current_case_producer' in previous
    selected=current.get('saved_result_registration')
    if not isinstance(selected,dict):return False
    names=list(CORE_FUNCTIONS)
    if not explicit:
        # Changing from the old default producer to an explicit factory is
        # a real processing change, not this dispatch-only transition.
        if not {'module','function','call_style'}<=selected.keys():return False
        route=_legacy_registration(before,previous.get('metric_id'))
        if route is None or route!={k:selected[k] for k in ('module','function','call_style')}:return False
        if route['module']=='vnext.ordinary_saved_result':names.append(route['function'])
    if _dispatch_transition_signature(after,current_source) != DISPATCH_TRANSITION_V1:return False
    if _component(before,names) is None or _component(before,names)!=_component(after,names):return False
    # Everything outside the shared dispatch conversion still compares normally.
    def rest(config):
        return {k:({p:d for p,d in v.items() if p not in {STORE,
            'scripts/vnext/ordinary_current_update.py','scripts/vnext/request_bindings.py',
            'scripts/vnext/ordinary_update_compatibility.py','scripts/vnext/ordinary_result_registration.py'}}
            if k=='processing_files' else v) for k,v in config.items() if k!='saved_result_registration'}
    return rest(previous)==rest(current)
