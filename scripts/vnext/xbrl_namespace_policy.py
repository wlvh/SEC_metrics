"""Finite FASB namespace forms; no caller regex or runtime-global patching."""
import re

YEAR_ONLY='YEAR_ONLY'
YEAR_OR_DATE_RELEASE='YEAR_OR_DATE_RELEASE'
YEAR_QUARTER_OR_DATE='YEAR_QUARTER_OR_DATE'


def is_sec_namespace(uri, *, taxonomy, namespace_policy=YEAR_ONLY):
    """Accept only the selected release spellings of SEC DEI or ECD."""
    if (type(namespace_policy) is not str or
            namespace_policy not in {YEAR_ONLY,YEAR_QUARTER_OR_DATE} or
            type(taxonomy) is not str or taxonomy not in {'dei','ecd'}):
        raise ValueError('SEC_NAMESPACE_POLICY_UNSUPPORTED')
    suffix='' if namespace_policy==YEAR_ONLY else r'(?:q[1-4]|-\d{2}-\d{2})?'
    return isinstance(uri,str) and re.fullmatch(
        r'https?://xbrl\.sec\.gov/'+taxonomy+r'/\d{4}'+suffix,uri) is not None


def is_fasb_namespace(uri, *, taxonomy='us-gaap', namespace_policy=YEAR_ONLY):
    if namespace_policy not in {YEAR_ONLY,YEAR_OR_DATE_RELEASE} or taxonomy not in {'us-gaap','srt'}:
        raise ValueError('XBRL_NAMESPACE_POLICY_UNSUPPORTED')
    suffix='' if namespace_policy==YEAR_ONLY else r'(?:-\d{2}-\d{2})?'
    return isinstance(uri,str) and re.fullmatch(r'https?://fasb\.org/'+taxonomy+r'/[0-9]{4}'+suffix,uri) is not None
