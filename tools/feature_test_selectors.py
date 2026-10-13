"""Read small additive feature selector declarations for the existing runner."""
import json
from pathlib import Path


def _unique_fields(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('FEATURE_TEST_FIELD_DUPLICATE:'+key)
        result[key]=value
    return result


def load_feature_selectors(*,directory,existing_fast=(),existing_source=()):
    directory=Path(directory)
    if not directory.is_dir():raise ValueError('FEATURE_TEST_DIRECTORY_MISSING')
    additions={'fast':[],'source-material':[]}
    seen=set((*existing_fast,*existing_source))
    if len(seen)!=len(existing_fast)+len(existing_source):
        raise ValueError('FEATURE_TEST_EXISTING_SELECTOR_DUPLICATE')
    for path in sorted(directory.glob('*.json')):
        record=json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=_unique_fields)
        if type(record) is not dict or not record or not set(record)<=set(additions):
            raise ValueError('FEATURE_TEST_DECLARATION_INVALID:'+path.name)
        for suite,selectors in record.items():
            if type(selectors) is not list or not all(type(s) is str and s.strip()==s and s for s in selectors):
                raise ValueError('FEATURE_TEST_SELECTOR_SHAPE_INVALID:'+path.name)
            for selector in selectors:
                if selector in seen:raise ValueError('FEATURE_TEST_SELECTOR_DUPLICATE:'+selector)
                seen.add(selector);additions[suite].append(selector)
        if not any(record.values()):raise ValueError('FEATURE_TEST_EMPTY_DECLARATION:'+path.name)
    return {suite:tuple(selectors) for suite,selectors in additions.items()}
