"""The existing organization-name words, without loading C02 selection.

This pure helper preserves the original suffix/state-marker treatment. Its
output is a comparison input, not proof of a filing's issuer or authority.
"""
import re

_LEGAL_SUFFIX = frozenset({"inc", "co", "corp", "corporation", "company", "ltd", "llc", "plc", "the", "lp"})


def _name_core(text):
    """The words of an organisation's name without legal suffixes or state tags."""
    text = re.sub(r"/[A-Z]{2}/", " ", text).casefold().replace("’", "'")
    return tuple(word for word in re.findall(r"[a-z0-9']+", text) if word not in _LEGAL_SUFFIX)
