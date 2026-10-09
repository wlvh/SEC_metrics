"""Finite FASB namespace forms; no caller regex or runtime-global patching."""
import re

YEAR_ONLY='YEAR_ONLY'
YEAR_OR_DATE_RELEASE='YEAR_OR_DATE_RELEASE'


def is_fasb_namespace(uri, *, taxonomy='us-gaap', namespace_policy=YEAR_ONLY):
    if namespace_policy not in {YEAR_ONLY,YEAR_OR_DATE_RELEASE} or taxonomy not in {'us-gaap','srt'}:
        raise ValueError('XBRL_NAMESPACE_POLICY_UNSUPPORTED')
    suffix='' if namespace_policy==YEAR_ONLY else r'(?:-\d{2}-\d{2})?'
    return isinstance(uri,str) and re.fullmatch(r'https?://fasb\.org/'+taxonomy+r'/[0-9]{4}'+suffix,uri) is not None
