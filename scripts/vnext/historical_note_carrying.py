"""Four note forms in the historical frame, with the ordinary proof retained.

The #28-bound note reader stays byte-identical. These are substitutions of its
existing inventory functions, using the historical route's existing successor
mechanism; the composition, source reconciliation, lease and completeness
checks are unchanged. No issuer, accession, year or amount selects a branch.
"""
import datetime
import re

from . import b06_note_carrying as frozen
from .historical_dei import release_aware, release_aware_with
from .historical_financial_wording import successor

_MONTHS = 'January February March April May June July August September October November December'.split()
_POINT = re.compile(r'\bas of (' + '|'.join(_MONTHS) + r') ([0-9]{1,2}), ([0-9]{4})\b', re.I)
_DATE = re.compile(r'\b(?:' + '|'.join(_MONTHS) + r') [0-9]{1,2}, [0-9]{4}\b', re.I)


def prior_principal_balance(sentence, end):
    """An entire balance assertion attributed solely to one earlier date.

    The optional introductory repurchase clause contains no other assertion or
    monetary amount. A current, future, mixed-date or additional balance keeps
    the frozen reader's refusal rather than being treated as a prior balance.
    """
    points = list(_POINT.finditer(sentence))
    if len(points) != 1 or len(_DATE.findall(sentence)) != 1:
        return False
    point = points[0]
    try:
        month = next(i for i, name in enumerate(_MONTHS, 1) if name.casefold() == point[1].casefold())
        dated = datetime.date(int(point[3]), month, int(point[2]))
        target = datetime.date.fromisoformat(end)
    except (ValueError, StopIteration):
        return False
    if dated >= target or not re.fullmatch(
            r'\s*(?:Following the repurchase combined with repurchase in previous years,\s*)?',
            sentence[:point.start()], re.I):
        return False
    return bool(re.fullmatch(
        r'\s*,?\s*\$[0-9,.]+\s+(?:thousand|million|billion)\s+'
        r'aggregate principal amount of the Notes due [0-9]{4}\s+remained outstanding\.\s*',
        sentence[point.end():], re.I))


def equity_share_counts(sentence, money):
    """Every apparent monetary token is explicitly a count of equity shares."""
    return bool(money and re.search(r'\b(?:options|warrants)\b', sentence, re.I) and all(
        match[1] is None and re.match(r'\s+shares\b', sentence[match.end():], re.I)
        for match in money))


SOURCE_FORMS = (
    ("                else:\n                    raise NoteCarryingError('NOTE_CARRYING_UNRESOLVED_FINANCING_FACT:'+local)",
     "                elif standard and local.casefold() == 'debtinstrumentinterestrateeffectivepercentage' and unit == {\n"
     "                        'measures':[('http://www.xbrl.org/2003/instance','pure')],'divided':False}:\n"
     "                    record['disposition'] = 'DIMENSIONED_DEBT_EFFECTIVE_INTEREST_RATE'\n"
     "                else:\n                    raise NoteCarryingError('NOTE_CARRYING_UNRESOLVED_FINANCING_FACT:'+local)"),)
NARRATIVE_FORMS = (
    ("            _need(_date_text(end) in sentence, 'NARRATIVE_PERIOD_UNPROVEN:'+sentence)",
     "            if _prior_principal_balance(sentence, end):\n"
     "                item['disposition'] = 'EXPLICIT_PRIOR_PERIOD_PRINCIPAL_BALANCE'\n"
     "                inventory.append(item)\n                continue\n"
     "            _need(_date_text(end) in sentence, 'NARRATIVE_PERIOD_UNPROVEN:'+sentence)"),
    ("            _need(money, 'NARRATIVE_AMOUNT_UNREADABLE')",
     "            _need(money, 'NARRATIVE_AMOUNT_UNREADABLE')\n"
     "            if _equity_share_counts(sentence, money):\n"
     "                item['disposition'] = 'EQUITY_INSTRUMENT_SHARE_COUNTS'\n"
     "                inventory.append(item)\n                continue"),)
ASSET_FORMS = (
    ("text.startswith('Cash equivalents, restricted cash and marketable securities consist of the following:')",
     "text.startswith(('Cash equivalents, restricted cash and marketable securities consist of the following:', "
     "'The cash equivalents, restricted cash and marketable securities consist of the following:'))"),)

source_inventory = release_aware(successor(frozen._source, SOURCE_FORMS))
narrative_inventory = release_aware_with(successor(frozen._narrative, NARRATIVE_FORMS),
    _prior_principal_balance=prior_principal_balance, _equity_share_counts=equity_share_counts)
related_tables_inventory = release_aware(successor(frozen._related_tables_inventory, ASSET_FORMS))
inspect_note_carrying = release_aware_with(frozen.inspect_note_carrying,
    _source=source_inventory, _narrative=narrative_inventory,
    _related_tables_inventory=related_tables_inventory)
