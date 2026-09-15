"""One native update's deterministic request bytes; never execution credit.

The existing FileBinding/read discipline is reused, but the table-oriented
OfflineExecutionSession (one DerivedAsset and child tasks) does not own native
request construction. This small scope stores only complete input/output bytes
and expires on return. All source, receipt and meaning checks remain callers.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import json
from pathlib import Path

from .canonical import sha256_bytes
from .normal_source_authority import ROOT
from .offline_execution_session import FileBinding,OfflineSessionError
from .sources import resolve_repository_file

_ACTIVE=ContextVar('native_request_construction_scope',default=None)
_MAX_ENTRIES=2
_MAX_BYTES=64*1024*1024


def _plain_json(value,active=None):
    """Exclude JSON encoder coercions from both cache keys and cached output."""
    kind=type(value)
    if value is None or kind in (str,int,bool):return True
    if kind not in (dict,list):return False
    if active is None:active=set()
    identity=id(value)
    if identity in active:return False
    active.add(identity)
    try:
        if kind is dict:
            return all(type(key) is str and _plain_json(item,active) for key,item in value.items())
        return all(_plain_json(item,active) for item in value)
    finally:active.remove(identity)


def _raw(value):
    # Canonical hashing normalizes Unicode. A cache key must instead retain
    # every original code point because the actual JSON/HTTP/token count does.
    return json.dumps(value,ensure_ascii=False,sort_keys=False,separators=(',',':')).encode('utf-8')


class _Construction:
    def __init__(self,requirement):
        self.closure=requirement['requirement_closure_hash'];self.failed=False
        self.pins=tuple(FileBinding(p,b['sha256'],b['size'])
            for p,b in requirement['execution_authority']['files'].items())
        if not self.pins:raise OfflineSessionError('NATIVE_REQUEST_CONSTRUCTION_RULES_REQUIRED')
        self.own_path=Path(__file__).resolve();self.own_bytes=self.own_path.read_bytes()
        self.entries={};self.size=0;self.builds=0;self.hits=0
        self.format_state=self._format_state();self.encoder_state=None
        self.check()

    @staticmethod
    def _format_state():
        from . import continuous_request_context as context
        import tokenizers
        return (context.FORMAT_VERSION,context.ENGINE_VERSION,tokenizers.__version__,
                context.MAX_CONTEXT,context.MAX_BYTES,context.OUTPUT_RESERVE,
                context.TOKENIZER_PATH,context.TOKENIZER_SHA256,context.ARCHIVE_SHA256,
                context.UPSTREAM_REVISION,context.UPSTREAM_FORMAT_SHA256)

    def check(self):
        if self.failed:raise OfflineSessionError('NATIVE_REQUEST_CONSTRUCTION_SCOPE_FAILED')
        try:
            if self._format_state()!=self.format_state:
                raise OfflineSessionError('NATIVE_REQUEST_CONSTRUCTION_FORMAT_OR_ENGINE_CHANGED')
            for binding in self.pins:
                path=resolve_repository_file(repo_root=ROOT,repo_relative_path=binding.path)
                raw=path.read_bytes()
                if len(raw)!=binding.size or sha256_bytes(content=raw)!=binding.sha256:
                    raise OfflineSessionError('NATIVE_REQUEST_CONSTRUCTION_RULE_CHANGED:'+binding.path)
            if self.own_path.is_symlink() or self.own_path.read_bytes()!=self.own_bytes:
                raise OfflineSessionError('NATIVE_REQUEST_CONSTRUCTION_IMPLEMENTATION_CHANGED')
            from .continuous_request_context import _load_tokenizer
            tokenizer,reason=_load_tokenizer()
            if tokenizer is None:raise OfflineSessionError('NATIVE_REQUEST_CONSTRUCTION_TOKENIZER_CHANGED:'+str(reason))
            encoder_state=sha256_bytes(content=tokenizer.to_str().encode('utf-8'))
            if self.encoder_state is not None and encoder_state!=self.encoder_state:
                raise OfflineSessionError('NATIVE_REQUEST_CONSTRUCTION_TOKENIZER_STATE_CHANGED')
            self.encoder_state=encoder_state
        except BaseException:
            self.failed=True
            raise

    def get(self,source,construct):
        self.check()
        if not _plain_json(source):
            # Retain any less common input types accepted by the existing
            # constructor (e.g. Decimal); no new serialization is introduced.
            self.builds+=1;value=construct(source);self.check();return value
        key=_raw(source)
        raw=self.entries.get(key)
        if raw is not None:
            self.hits+=1
            return json.loads(raw)
        # No references to the caller's mutable source or returned objects are
        # retained, including on the first build.
        self.builds+=1;value=construct(deepcopy(source));self.check()
        if not _plain_json(value):return value
        raw=_raw(value)
        if _raw(source)!=key:raise OfflineSessionError('NATIVE_REQUEST_CONSTRUCTION_SOURCE_CHANGED_DURING_BUILD')
        size=len(key)+len(raw)
        if size<=_MAX_BYTES:
            while self.entries and (len(self.entries)>=_MAX_ENTRIES or self.size+size>_MAX_BYTES):
                old=next(iter(self.entries));self.size-=len(old)+len(self.entries.pop(old))
            self.entries[key]=raw;self.size+=size
        return json.loads(raw)


@contextmanager
def request_construction_session(requirement):
    current=_ACTIVE.get()
    if current is not None:
        if current.closure!=requirement['requirement_closure_hash']:
            raise OfflineSessionError('NATIVE_REQUEST_CONSTRUCTION_NESTED_RULES_CHANGED')
        current.check();yield current;return
    current=_Construction(requirement);token=_ACTIVE.set(current)
    try:
        yield current
        current.check()
    finally:
        current.entries.clear();current.size=0
        _ACTIVE.reset(token)


def reuse_source_requests(source,construct):
    from .continuous_request_context import FORMAT_VERSION
    scope=_ACTIVE.get()
    if scope is None or source.get('request_context_format')!=FORMAT_VERSION or source.get('record_type') not in {
        'D04_NATIVE_COMPLETE_SEMANTIC_SOURCE','B13_COMPLETE_SEMANTIC_SOURCE','D04_NATIVE_HISTORICAL_CONTROL_SOURCE'}:
        return construct(source)
    return scope.get(source,construct)
