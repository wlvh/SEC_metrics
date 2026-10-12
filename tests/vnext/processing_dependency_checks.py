"""Test-only executed-function coverage of ordinary processing fingerprints.

This does not inspect runtime file access or infer a recursive import graph.
Consumers supply their actual factory and saved/small inputs in their tests.
"""
from contextlib import contextmanager
from pathlib import Path
import sys


SOURCE_CHECK_EXCEPTIONS = {
    'scripts/vnext/ordinary_current_update.py': 'control/source checking reruns before reuse',
    'scripts/vnext/request_bindings.py': 'request/body checking reruns before reuse',
}


@contextmanager
def processing_calls(program_root):
    prefix=str((Path(program_root)/'scripts/vnext').resolve())+'/'
    observed={};previous=sys.getprofile()
    def profile(frame,event,arg):
        filename=frame.f_code.co_filename
        if event=='call' and frame.f_code.co_flags & 1 and filename.startswith(prefix):
            relative='scripts/vnext/'+filename[len(prefix):]
            observed.setdefault(relative,set()).add(frame.f_code.co_name)
        if previous is not None:
            previous(frame,event,arg)
    sys.setprofile(profile)
    try:
        yield observed
    finally:
        sys.setprofile(previous)


def undeclared_processing_calls(observed,configuration,declared_files=()):
    allowed=(set(configuration.get('processing_files',{}))
        | set(configuration.get('declared_processing_files',{}))
        | set(declared_files) | set(SOURCE_CHECK_EXCEPTIONS))
    return {path:sorted(functions) for path,functions in sorted(observed.items()) if path not in allowed}


def assert_processing_calls(observed,configuration,declared_files=()):
    missing=undeclared_processing_calls(observed,configuration,declared_files)
    if missing:
        detail='; '.join(path+':'+','.join(functions) for path,functions in missing.items())
        raise AssertionError('PROCESSING_DEPENDENCY_UNDECLARED: '+detail)
