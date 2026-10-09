"""Check a native monetary representation before normalizing its amount.

Subject, period, unit and concept selection belong to the caller. This small
helper only handles numeric tags, lexical forms and nil; it reads no files.
"""
import re

from .governance_signals import _qname, _source_value


def _need(condition, reason):
    if not condition:
        raise ValueError('REPORTED_MONETARY_' + reason)


def reported_monetary_value(*, fact, metadata, policy):
    tag_uri, tag_name = _qname(metadata['tag'], metadata['namespaces'])
    inline = tag_uri in policy['numeric_inline_namespaces'] and tag_name == 'nonfraction'
    xml = (tag_uri == metadata['concept'][0]
           and tag_name.casefold() == metadata['concept'][1].casefold())
    _need(inline or xml, 'NUMERIC_TAG_NOT_SUPPORTED')
    nil = [v for k, v in metadata['attrs'].items()
           if _qname(k, metadata['namespaces']) == ('http://www.w3.org/2001/XMLSchema-instance', 'nil')]
    _need(not nil or nil == ['false'] or nil == ['0'], 'NIL_OR_INVALID_SOURCE_VALUE')
    transform = metadata['attrs'].get('format', '')
    if xml:
        _need(not transform and metadata['attrs'].get('scale', '0') == '0'
              and not metadata['attrs'].get('sign'), 'XML_NUMERIC_ATTRIBUTES_NOT_SUPPORTED')
    local = _qname(transform, metadata['namespaces'])[1] if transform else ''
    if local not in {'fixed-zero', 'numdash'}:
        pattern = policy['dot_decimal_supported_lexical_pattern'] if transform else policy['unformatted_decimal_lexical_pattern']
        _need(re.fullmatch(pattern, str(fact['text']).strip()) is not None, 'NUMERIC_LEXICAL_FORM_NOT_SUPPORTED')
    try:
        return _source_value(fact, metadata)
    except ValueError as error:
        raise ValueError('REPORTED_MONETARY_NUMERIC_VALUE_NOT_SUPPORTED:' + str(error)) from error
