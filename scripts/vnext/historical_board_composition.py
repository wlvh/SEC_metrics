"""Board composition facts, read the way a proxy statement lays them out.

Purpose:
    The owner's decision fixes C02's meaning as composition facts: the
    board's size, how many and which directors are independent, which
    committees exist, who sits on and who chairs them, and the determinations
    about committee members' independence and qualifications. General
    governance process and descriptions of what a committee does are outside
    it. The frozen selector (``text_business_candidates.board_composition_
    candidates``) cannot express that: it labels a block as committee
    information when any committee name and any structural word occur anywhere
    in it, which admitted biographies, fee tables and equity-plan terms, and it
    reads one block at a time, which cannot see a committee page at all.

    Measured on the ten saved governance filings: the committee pages that
    carry membership put the committee's name, a label, and one block per
    member in sequence, and no single block holds both the committee's name
    and a structural word. Pfizer's five pages yielded no member and no chair
    under the frozen rule. So the membership forms here are read as structures
    - a heading followed by the blocks that belong to it - and the prose forms
    are read sentence by sentence against the forms composition facts take.

    What this reader will not do, by design:
      * infer a count, a date or an association the filing does not print. A
        membership matrix whose marks lost their columns in the HTML
        (Southwest, Marriott, Enphase summary tables) is not reconstructed; the
        same facts are read from the committee pages where the filing prints
        them in full.
      * treat a director card as membership unless the card names its
        director in the block beside it. A card whose name sits behind other
        card fields is left out, not guessed.
      * read another organisation's board or committee as this one. The prose
        rules refuse a sentence that places a board or committee at another
        named body, which is how biographies speak.

    A block is the unit of an excerpt (``text_results.text_claim_from_block``
    supports whole blocks only), so a block that states a composition fact is
    taken whole even when it also says something else. The reading records
    which blocks are mixed rather than pretending the unit is a sentence.

Call relationships:
    ``historical_text_results.prepare_business_text_sources`` replaces the
    frozen proposal for C02's governance document with the one built here; the
    frozen preparation still owns every source, identity and period check, and
    the frozen candidate builder, Evidence and record shapes are reused
    unchanged.
"""
from __future__ import annotations

import re

from .canonical import content_hash
from .text_business_candidates import _check_document, _excerpt

SELECTION_POLICY = "BOARD_COMPOSITION_FACTS_V1"
SECTION_ID = "GOVERNANCE_DISCLOSURES"

_WS = re.compile("[\\s ​  ]+")
_BULLET_CHARS = "•●▪◦‣⯀■□◆◇\\-–—*"
_BULLET = re.compile("^[\\s" + _BULLET_CHARS + "]+")
_ONE_BULLET = re.compile("^[" + _BULLET_CHARS + "]$")
_BULLETS_ONLY = re.compile("^[\\s" + _BULLET_CHARS + "]*$")
_FOOTNOTE_TAIL = re.compile(r"(?:\s*(?:\(\d{1,2}\)|[*†‡§#+¹²³]+))+\s*$")
_CHAIR_TAIL = re.compile(
    r"\s*(?:,|\(|–|—|-)\s*(?:committee\s+)?(?:chair(?:man|person|woman)?"
    r"|vice[- ]chair(?:man|person|woman)?|lead independent director)\s*\)?\s*[*†‡§#+]*\s*$", re.I)
# A report signature prints "Richard Mora, Member" beside "Thurman John
# Rodgers, Chair": the word names the signatory's role on the committee.
_MEMBER_TAIL = re.compile(r"\s*(?:,|\(|–|—|-)\s*(?:committee\s+)?member\s*\)?\s*[*†‡§#+]*\s*$", re.I)
_HONORIFIC = re.compile(r"^(?:mr|ms|mrs|mses|messrs|dr|gen|general|adm|admiral|sir|dame|hon|ambassador"
                        r"|governor|senator|lt|col)\.?\s+", re.I)
_CREDENTIAL_TAIL = re.compile(
    r"(?:,?\s+|,\s*)(?:m\.?d\.?|ph\.?\s?d\.?|m\.p\.h\.?|mph|mba|cpa|j\.d\.|esq\.?|jr\.?|sr\.?|ii|iii|iv"
    r"|dds|dvm|rn|faan|facp|frcp|c\.p\.a\.)\s*$", re.I)
_UPPER = "A-ZÀ-Þ"
_LOWER = "a-zß-ÿ'’"
_NAME_TOKEN = re.compile(
    "^(?:[" + _UPPER + "][" + _LOWER + "]*(?:[-'’][" + _UPPER + "]?[" + _LOWER + "]+)*"
    "|(?:[" + _UPPER + "][" + _LOWER + "]+){2,}"
    "|[" + _UPPER + "]\\."
    "|[" + _UPPER + "][" + _UPPER + "'’\\-]+)$")
_PARTICLES = frozenset({"van", "von", "de", "del", "della", "da", "di", "du", "la", "le", "dos", "das",
                        "bin", "al", "st."})
# The words proxy headings, captions, table cells and titles are made of. A
# block of capitalised words is a heading as often as it is a name, so a word
# on this list makes a block not a name. Governance vocabulary, not a list of
# any filer's words.
STOP_WORDS = frozenset("""
committee committees board boards director directors member members chair chairman chairperson chairwoman
vice lead independent independence meeting meetings report reports governance corporate compensation audit
nominating finance financial risk security cybersecurity privacy technology sustainability safety operations
oversight fleet strategic executive culture talent policy policies public regulatory compliance science
innovation transformation business responsibilities responsibility key primary functions function focus areas
recent highlights overview summary proxy statement annual table contents company inc corporation corp llc ltd
plc lp international group holdings partners capital management additions departures name names age since
occupation total fees retainer cash stock awards the our and of for to in on at by with as from all each other
current former retiring incoming chief officer president founder partner senior counsel secretary treasurer
controller presiding skills experience qualifications background professional education tenure diversity gender
matrix notes note appendix exhibit item part page section questions voting proposal proposals election nominees
nominee shareholders stockholders date time place record information about how what why who where when your vote
yes no none human resources inclusion social impact development leadership structure engagement evaluation
evaluations refreshment succession planning charter charters actions consent written number agenda environmental
health quality product products research medical global employees employee labor relations service services
legal general its his her their cofounder cochair coceo incorporated limited parkway street avenue road
boulevard drive suite plaza floor
""".split())
_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def clean(text):
    """Collapse the whitespace variants HTML leaves in a block."""
    return _WS.sub(" ", text).strip()


def _strip_name(text):
    t = _BULLET.sub("", clean(text))
    t = _FOOTNOTE_TAIL.sub("", t)
    t = _CHAIR_TAIL.sub("", t)
    t = _MEMBER_TAIL.sub("", t)
    t = _FOOTNOTE_TAIL.sub("", t)
    t = _HONORIFIC.sub("", t)
    for _ in range(3):
        shorter = _CREDENTIAL_TAIL.sub("", t).rstrip(",").strip()
        if shorter == t:
            break
        t = shorter
    return t


def person_name(text):
    """True when the whole block is one person's name as proxies print them.

    A name here may carry a bullet, a footnote mark, a chair annotation, an
    honorific or credentials; what remains must be one to five capitalised
    tokens, initials or particles, none of them a governance word. A block made
    of surnames run together (``GoldbergCaposselaCollinsMcMillan``, a graphic's
    captions without separators) is one token of that shape and is accepted:
    it is what the filing prints.
    """
    raw = clean(text)
    if not raw or len(raw) > 60:
        return False
    t = _strip_name(raw)
    if not t or re.search(r"[\d:%$/@?;!“”\"()\[\]|]", t):
        return False
    tokens = [token for token in t.replace(",", " ").split(" ") if token]
    if not 1 <= len(tokens) <= 5:
        return False
    if any(re.sub(r"[^\w]", "", token).casefold() in STOP_WORDS for token in tokens):
        return False
    words = 0
    for token in tokens:
        if token.casefold() in _PARTICLES:
            continue
        if not _NAME_TOKEN.match(token):
            return False
        if not re.fullmatch("[" + _UPPER + "]\\.", token):
            words += 1
    if len(tokens) == 1:
        # A lone short capital token is an abbreviation ("IND", "CEO"), not a
        # surname printed on its own.
        return len(tokens[0]) >= (4 if tokens[0].isupper() else 3)
    return words > 0


def name_list(text):
    """True when the text is one name or a list of names."""
    t = re.sub(r"\((?:chair(?:man|person|woman)?|vice[- ]chair)\)", "", clean(text), flags=re.I)
    if person_name(t):
        return True
    parts = [part for part in re.split(r",\s*|\s+and\s+|;\s*", t) if part.strip()]
    return bool(parts) and all(person_name(part) for part in parts)


_CHAIR_MARKER = re.compile(r"^\(?\s*(?:committee\s+)?chair(?:man|person|woman)?\s*\)?\s*[*†‡§#+]*$", re.I)


def chair_marker(text):
    """A block that is only the word chair, printed beside a member's name."""
    return bool(_CHAIR_MARKER.match(clean(text)))


def chair_named(text):
    """A name block that carries its own chair annotation ("Gomo, Chair")."""
    t = _FOOTNOTE_TAIL.sub("", _BULLET.sub("", clean(text)))
    return bool(re.search(r"(?:,|\(|–|—|-)\s*(?:committee\s+)?chair(?:man|person|woman)?\s*\)?\s*[*†‡§#+]*$", t, re.I))


# Words that make a heading about committees rather than the name of one.
# ("Information" is not among them: "Technology and Information Security
# Oversight Committee" is a committee's name.)
_HEADING_EXCLUDE = frozenset("""report reports letter role interlocks processes procedures evaluation evaluations
refreshment memberships membership functions function actions charter charters pre-approval delegation
additional retainer members member chair chairs meetings meeting key focus highlights recent board committees
matters approved date name""".split())
_HEADING_WORD = re.compile(r"^(?:[A-Z][A-Za-z’'\-]*|[A-Z&]+|&|and|of|the|for|on)$")


def committee_name(text):
    """The committee a block names when the whole block is that name.

    Accepts the committee's own page heading ("The Audit Committee"), a report
    signature ("THE AUDIT COMMITTEE", "Members of the Compensation Committee")
    and a membership table's row label. A heading about committees ("Board
    Committees", "Compensation Committee Report", "Additional Committee
    Members:") names no committee and is refused.
    """
    t = clean(text)
    if not t or len(t) > 90:
        return None
    t = _BULLET.sub("", t)
    t = _FOOTNOTE_TAIL.sub("", t).rstrip(":").strip()
    t = _FOOTNOTE_TAIL.sub("", t)
    t = re.sub(r"^(?:members of\s+)?(?:the|our)\s+", "", t, flags=re.I)
    match = re.fullmatch(r"(.+?)\s+committee", t, flags=re.I)
    if not match:
        return None
    prefix = match.group(1).replace(",", " ")
    tokens = [token for token in prefix.split(" ") if token]
    if not 1 <= len(tokens) <= 8 or re.search(r"\d", prefix):
        return None
    for token in tokens:
        if token.casefold() in _HEADING_EXCLUDE or not _HEADING_WORD.match(token):
            return None
    return " ".join(tokens).casefold()


_MEMBER_LABEL = re.compile(r"^(?:(?:current|additional|other)\s+)?(?:committee\s+)?members\s*:?\s*$", re.I)
_MEMBER_INLINE = re.compile(r"^(?:(?:current|additional|other)\s+)?(?:committee\s+)?members?\s*:\s*(?P<names>\S.*)$", re.I)
_CHAIR_INLINE = re.compile(r"^(?:committee\s+)?(?:chair(?:man|person|woman)?|vice[- ]chair)\s*[:\-–—]\s*(?P<name>\S.*)$", re.I)
_META = re.compile(r"(?:^|\b)(?:meetings?|attendance|actions? by written|consent in|number of meetings|in fiscal"
                   r"|fiscal \d{4})\b|^\d{1,3}%?$", re.I)
_SECTION_REACH = 120


def _registrant_keys(document):
    return {re.sub(r"\W", "", name).casefold() for name in document.get("registrant_names", [])}


def _furniture(block, registrant):
    """Page furniture that can sit between a committee heading and its roster."""
    text = clean(block["text"])
    if block["linked"] and len(text) < 120:
        return True
    if re.fullmatch(r"\d{1,3}", text) or re.sub(r"\W", "", text.casefold()) in registrant:
        return True
    return bool(re.search(r"\bproxy statement\b", text, re.I) and len(text) < 60)


def _roster_run(blocks, start, stop, registrant):
    """Member names and chair marks from ``start`` while they last.

    A lone list bullet may stand before an item and is stepped over. A block of
    several marks is a membership matrix's cell - the marks lost their columns
    - and ends the run, so a matrix's column of directors is never read as a
    committee's roster.
    """
    taken, names, j = [], 0, start
    while j < stop:
        block = blocks[j]
        text = clean(block["text"])
        # A lone bullet, or a block of nothing but zero-width characters the
        # layout left between two names, is stepped over.
        if _ONE_BULLET.match(text) or not text:
            j += 1
            continue
        if (person_name(text) and not block["linked"]
                and re.sub(r"\W", "", text.casefold()) not in registrant):
            taken.append((j, "COMMITTEE_CHAIR_NAME" if chair_named(text) else "COMMITTEE_MEMBER_NAME"))
            names += 1
        elif chair_marker(text) and names:
            taken.append((j, "COMMITTEE_CHAIR_MARKER"))
        else:
            break
        j += 1
    return taken, names, j


_SIGNATURE_LEAD = re.compile(
    r"^submitted by (?:the members of )?(?:the |our )?(?P<name>[A-Z][\w&’'\- ,]{0,80}?\bcommittee)\b"
    r"(?:\s+of the board(?: of directors)?)?(?:\s+as of\s+[^.;]{0,40})?\.?$", re.I)


def _committee_headings(blocks):
    """Every block that names one committee, a heading broken in two included.

    A report's signature lead-in ("Submitted by the Audit Committee of the
    Board of Directors as of February 16, 2026.") names the committee whose
    members sign beneath it, so it heads that roster too.
    """
    headings = []
    for i, block in enumerate(blocks):
        if block["linked"]:
            continue
        name, span = committee_name(block["text"]), (i, i)
        if name is None:
            lead = _SIGNATURE_LEAD.match(clean(block["text"]))
            name = committee_name(lead.group("name")) if lead else None
        if i > 0 and not blocks[i - 1]["linked"] and blocks[i - 1].get("emphasized"):
            previous = clean(blocks[i - 1]["text"])
            joined = committee_name(previous + " " + clean(block["text"]))
            if joined and (re.search(r"(?:\band|&|,|\bof)$", previous, re.I)
                           or clean(block["text"]).casefold() == "committee"):
                name, span = joined, (i - 1, i)
        if name:
            headings.append((span, name))
    return headings


def _committee_structures(blocks, headings, registrant):
    """Rosters, chair lines and member lists that belong to one committee each."""
    taken = []
    starts = [span[0] for span, _ in headings]
    for n, (span, _name) in enumerate(headings):
        start = span[1] + 1
        stop = min(starts[n + 1] if n + 1 < len(starts) else len(blocks), start + _SECTION_REACH)
        found = []
        # Signature and table form: the committee's name, then its members.
        j = start
        while j < stop and (_META.search(clean(blocks[j]["text"])) or _ONE_BULLET.match(clean(blocks[j]["text"]))
                            or _furniture(blocks[j], registrant)):
            j += 1
        run, count, _ = _roster_run(blocks, j, stop, registrant)
        if count >= 2 or (count and any(label in ("COMMITTEE_CHAIR_MARKER", "COMMITTEE_CHAIR_NAME")
                                        for _, label in run)):
            found.extend(run)
        # Labelled forms anywhere in the committee's own section.
        k = start
        while k < stop:
            text = clean(blocks[k]["text"])
            chair = _CHAIR_INLINE.match(text)
            inline = _MEMBER_INLINE.match(text)
            if chair and name_list(chair.group("name")):
                found.append((k, "COMMITTEE_CHAIR_DESIGNATION"))
                run, count, end = _roster_run(blocks, k + 1, stop, registrant)
                found.extend(run)
                k = max(k + 1, end)
                continue
            if _MEMBER_LABEL.match(text):
                run, count, end = _roster_run(blocks, k + 1, stop, registrant)
                if count == 0:
                    # Laid out in another column: the names are read after the
                    # other column's content, still inside this section.
                    q, run, count = end, [], 0
                    while q < stop:
                        run, count, _ = _roster_run(blocks, q, stop, registrant)
                        if count >= 2:
                            break
                        q += 1
                    else:
                        run, count = [], 0
                if count:
                    found.append((k, "COMMITTEE_MEMBERS_LABEL"))
                    found.extend(run)
                k += 1
                continue
            if inline and name_list(inline.group("names")):
                found.append((k, "COMMITTEE_MEMBERS_LIST"))
            k += 1
        if found:
            taken.extend((h, "COMMITTEE_HEADING") for h in range(span[0], span[1] + 1))
            taken.extend(found)
    return taken


# --------------------------------------------------------------- prose facts
_NUM = (r"(?:\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen"
        r"|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)")
# Periods inside honorifics, initials and suffixes are not sentence ends. They
# are removed before any window below is measured, or "(other than Dr. Albert
# Bourla)" ends a sentence in the middle of a determination.
_ABBREVIATION = re.compile(
    r"\b(Mr|Ms|Mrs|Dr|Messrs|Mses|Jr|Sr|Inc|Co|Corp|Ltd|No|St|Gen|Adm|Hon|Lt|Col|vs|etc|U\.S|U\.K|Ph\.D|M\.D"
    r"|M\.P\.H|L\.P|N\.A)\.")
_INITIAL = re.compile(r"\b([A-Z])\.(?=\s|,|$)")
_SENTENCE = re.compile("(?<=[.;!?])\\s+(?=[A-Z“\"(•●])")


def sentences(text):
    """The block's sentences, abbreviations disarmed first."""
    t = _ABBREVIATION.sub(lambda m: m.group(1).replace(".", ""), clean(text))
    t = _INITIAL.sub(r"\1", t)
    return [s for s in _SENTENCE.split(t) if s.strip()]


_NOT_DIRECTOR_INDEPENDENCE = re.compile(
    r"independent registered public accounting firm|independent (?:auditors?|accountants?)"
    r"|independent (?:compensation )?(?:consultants?|advisors?|advisers?|counsel|legal counsel)"
    r"|independent third[- ]part(?:y|ies)|auditor independence"
    r"|independence of (?:the )?(?:firm|auditors?|consultants?|advisors?)"
    r"|independent (?:review|investigation|oversight|assessment|valuation|evaluation|appraisal|voice)"
    r"|lead independent director", re.I)
# Words that make a sentence describe a rule, a standard or a hypothetical
# rather than report a fact. Checked against the sentence with its qualifying
# references removed, and only where they come before a determination: "has
# determined that all members are independent, as required by Rule 5605" is a
# determination; "the Principles require that a majority ... who the Board has
# determined" is a requirement.
_POLICY = re.compile(
    r"\b(?:shall|must|should|may not|requires?|required|at least|no fewer than|not less than|a minimum of"
    r"|charter provides|guidelines provide|policy provides|can(?:not)? be (?:considered )?independent if"
    r"|is not independent if|are not independent if|would (?:not )?be (?:considered )?independent|family members?"
    r"|expected to|intends? to|seeks? to|strives? to|may (?:be|serve|include)|requirements? that|exempt\w*"
    r"|elected not to comply|controlled company|provides? that|is free to|if)\b", re.I)
_QUALIFYING_REFERENCE = re.compile(r"\bas (?:is |are )?(?:currently )?(?:required|defined|set forth|provided"
                                   r"|contemplated)\b[^;]*", re.I)
_DETERMINATION = re.compile(r"\b(?:has|have|had)\s+(?:\w+\s+){0,2}(?:determined|concluded|found)\b"
                            r"|\b(?:determined|concluded)\s+that\b", re.I)
# Topics that are never composition: pay, votes, attendance, correspondence,
# plan administration. A sentence that reaches one of them is set aside.
_EXCLUDED_TOPIC = re.compile(
    r"\$\s?\d|\bretainers?\b|\bfees?\b|\bRSUs?\b|\bequity awards?\b|\bcompensation (?:earned|paid)\b"
    r"|\bcommunicat\w*|\bcorrespondence\b|\b(?:have|has) joined the board (?:within|since|in the (?:last|past))\b"
    r"|\bplurality\b|\bvotes? cast\b|\bbroker non-votes?\b|\bquorum\b|\bproxy card\b|\badministered by\b"
    r"|\bis administered\b|\bwaived\b|\bvotes?\b|\bawards?\b|\battend\w*|\bliable\b", re.I)
_FIRST_PERSON = re.compile(r"\bI\b")
_BOARD_SIZE = (
    re.compile(r"\bboard(?: of directors)?\b[^.;:]{0,60}?\b(?:consists|is (?:currently |now )?(?:composed|comprised"
               r"|made up)|currently (?:has|consists)|has|is fixed at|will (?:consist|be (?:composed|comprised|reduced"
               r"|increased))|comprises)\b[^.;]{0,30}?\b" + _NUM + r"\s+(?:directors?|members?|seats?)\b", re.I),
    re.compile(r"\b(?:elect|election|nominated|nominee|stand|standing|slate|propos)\w*\b[^.;]{0,80}\b" + _NUM
               + r"\s+(?:director\s+|board\s+)?nominees\b", re.I),
    re.compile(r"\b" + _NUM + r"\s+(?:director\s+|board\s+)?nominees\b[^.;]{0,80}\b(?:elect|election|nominated"
               r"|stand|standing|slate)\w*\b", re.I),
    re.compile(r"\bto elect\s+" + _NUM + r"\s+(?:members of (?:the|our) board|directors|nominees)\b", re.I),
    re.compile(r"\b" + _NUM + r"\s+(?:directors|members of (?:our|the) board|nominees|individuals)\b[^.;]{0,40}"
               r"\b(?:are\s+|is\s+|will\s+|have been\s+|were\s+)?(?:standing|nominated|up|stand)\b", re.I),
    re.compile(r"\bnominated\s+(?:each of\s+)?(?:the\s+)?" + _NUM + r"\s+(?:directors|nominees|individuals"
               r"|candidates)\b", re.I),
    re.compile(r"\bsize of the board\b[^.;]{0,80}\b" + _NUM + r"\b", re.I),
    re.compile(r"\b(?:there are|we have)\s+(?:currently\s+)?" + _NUM + r"\s+(?:directors|members)\b", re.I),
    re.compile(r"\b(?:our|the|all)\s+" + _NUM + r"\s+(?:director\s+)?nominees\b", re.I),
)
_BOARD_INDEPENDENCE = (
    re.compile(r"\b(?:" + _NUM + r"|all|each|every|majority|substantial majority|none|\d{1,3}\s?%)\b[^.;]{0,20}"
               r"\b(?:of|out of)\b[^.;]{0,30}\b(?:directors?|director nominees|nominees|members of (?:our|the) board)\b"
               r"[^.;]{0,80}\bindependent\b", re.I),
    re.compile(r"\ball (?:of )?(?:our |the )?(?:current )?(?:directors|director nominees|nominees)\b[^.;]{0,100}"
               r"\b(?:are|is) independent\b", re.I),
    re.compile(r"\b(?:mr|ms|mrs|dr|messrs|mses|he|she|they)\b[^.;]{0,250}?\b(?:is|are|was|were)\s+(?:considered\s+"
               r"|deemed\s+|determined to be\s+)?(?:not\s+)?independent\b", re.I),
    re.compile(r"\bboard(?: of directors)?\b[^.;]{0,120}\b(?:affirmatively\s+)?(?:determined|concluded|found)\b"
               "[^.;]{0,300}\\b(?:is|are|was|were|be|qualif(?:y|ies) as)\\s+(?:considered\\s+)?[“\"]?independent\\b",
               re.I),
    re.compile(r"\b" + _NUM + r"\s+(?:of\s+(?:whom|which)\s+are\s+)?independent\s+(?:directors|director nominees"
               r"|nominees|members)\b", re.I),
    re.compile(r"\b(?:mr|ms|mrs|dr|he|she)\b[^.;]{0,120}\b(?:does|do|did) not (?:meet|satisfy|qualify)\b[^.;]{0,60}"
               r"\bindependen", re.I),
)
_COMMITTEE_COMPOSITION = (
    re.compile(r"\bcommittee\b[^.;]{0,60}?\b(?:is|was|are|were)\s+(?:currently\s+|now\s+|also\s+)?(?:composed"
               r"|comprised|made up)\s+(?:entirely\s+|solely\s+|exclusively\s+|wholly\s+)?of\b", re.I),
    re.compile(r"\bcommittee\b[^.;]{0,40}\bconsist(?:s|ed)\s+of\b", re.I),
    re.compile(r"\bmembers of the\b[^.;]{0,60}\bcommittee\b[^.;]{0,20}\b(?:are|were|include|included)\b", re.I),
    re.compile(r"\b(?:served|serve|serves|serving|sit|sits|sat)\s+(?:as\s+(?:a\s+)?members?\s+)?on\s+(?:the|our"
               r"|its|each of the)\b[^.;]{0,80}\bcommittees?\b", re.I),
    re.compile(r"\b(?:is|was|serves as|served as|has served as|will serve as|appointed(?: as)?|named(?: as)?"
               r"|designated(?: as)?|elected(?: as)?)\s+(?:the\s+)?(?:chair(?:man|person|woman)?|vice[- ]chair)"
               r"\s+of\s+(?:the|our|its)\b[^.;]{0,60}\bcommittee\b", re.I),
    re.compile(r"\bcommittee\b[^.;]{0,40}\b(?:is\s+|was\s+)?chaired by\b", re.I),
    re.compile(r"\bas (?:the )?chair(?:man|person|woman)? of the\b[^.;]{0,60}\bcommittee\b", re.I),
    re.compile("\\bas (?:the |our )?(?:[A-Z][\\w&’'\\-]*\\s+){0,6}committee chair\\b", re.I),
    re.compile(r"\b(?:none of the members|no (?:current |former )?members?|neither)\s+of\s+(?:the|our)\b[^.;]{0,60}"
               r"\bcommittee\b[^.;]{0,80}\b(?:was|is|were|are|has (?:ever )?been|have (?:ever )?been)\b[^.;]{0,40}"
               r"\b(?:officer|employee)", re.I),
)
_QUALIFICATION = re.compile(
    r"\b(?:independent|financially literate|financial literacy|financially sophisticated|financial sophistication"
    r"|financial experts?|non-employee directors?|outside directors?|non-management directors?"
    r"|independence (?:standards|requirements|criteria))\b", re.I)
_MEMBER_REFERENCE = re.compile(
    r"\b(?:(?:all|each|every|none)(?: of the)? (?:committee )?members?|members? of (?:the|our|each|its)\b[^.;]{0,60}"
    r"\bcommittees?|committee members?|committee financial experts?|serves? on the\b[^.;]{0,60}\bcommittee"
    r"|each of (?:mr|ms|mrs|dr|messrs|mses)\b|only independent directors serve on|committees? (?:is|are) composed)", re.I)
_STATE = re.compile(r"\b(?:is|are|was|were|qualif(?:y|ies)|meets?|satisf(?:y|ies)|determined|has been|have been"
                    r"|serve)\b", re.I)
_STANDING = (
    re.compile(r"\b(?:has|had|maintains|established|following)\b[^.;]{0,40}\b(?:standing|permanent)\s+"
               r"(?:board\s+)?committees?\b", re.I),
    re.compile(r"\b" + _NUM + r"\s+standing\s+(?:board\s+)?committees\b", re.I),
)
# A committee's setup changing: formed, dissolved, reconstituted, or a
# subcommittee or special committee set up. The committee is what changes;
# "the Audit Committee has established procedures" establishes procedures.
# A change is dated; "was established by the Board in accordance with
# Section 3(a)(58)(A)" is the statute every audit committee cites.
_COMMITTEE_SETUP = (
    re.compile(r"\bcommittee\b[^.;]{0,40}?\b(?:was|were|has been|have been|had been|will be)\s+(?:formally\s+)?"
               r"(?:dissolved|disbanded|eliminated|established|formed|created|reconstituted|renamed|merged|combined"
               r"|constituted|reorganized)\b[^.;]{0,60}?\b(?:19|20)\d{2}\b", re.I),
    re.compile(r"\b(?:established|set up|formed|created|constituted)\s+(?:a|an)\s+(?:(?:new|separate|special|standing"
               r"|ad hoc)\s+)*(?:sub-?committee|committee)\b", re.I),
    re.compile(r"\b(?:a|the)\s+special committee of (?:the|our) board\b", re.I),
)
_CHAIR_WORD = r"(?:vice[- ])?chair(?:man|person|woman)?"
# A chair title that names no board: "Chairman" is the board's chair, but a
# "Vice Chair" is as often an officer's title ("Vice Chair, Policy"), so it is
# the board's only where the text says "of the Board".
_SOLE_CHAIR = r"(?<!vice )(?<!vice-)chair(?:man|person|woman)?"
_BOARD_QUALIFIER = r"(?:(?:independent|non-executive|executive|incoming|retiring|next|new|current|interim)[,\s]+)*"
_LEADERSHIP_VERB = (r"(?:serves?|served|serving|has served|is|was|elected|appointed|named|selected|re-?elected"
                    r"|continues?|continued|continuing|remains?|remained|will (?:continue to )?serve|to serve)")
# A chair title that names no board belongs to this board only when the
# sentence says whose it is: "our", "the company's", or the registrant's own
# name in the possessive, checked against the registrant's name words.
_LEADERSHIP = (
    re.compile(r"\b" + _LEADERSHIP_VERB + r"\b[^.;]{0,40}\bas\s+(?:our\s+|the\s+|its\s+|the company['’]s\s+)?"
               + _BOARD_QUALIFIER + r"(?:" + _CHAIR_WORD + r" of the board|board chair|lead independent director"
               r"|presiding (?:independent )?director)\b", re.I),
    re.compile(r"\b(?:our|the)\s+(?:independent\s+|non-executive\s+|executive\s+)*(?:chair(?:man|person|woman)? of the"
               r" board|lead independent director)\s*,\s*(?:(?:mr|ms|mrs|dr)\s+)?(?-i:[A-Z][a-z])", re.I),
    re.compile(r"\b" + _LEADERSHIP_VERB + r"\b[^.;]{0,40}\bas\s+(?:the\s+)?" + _BOARD_QUALIFIER + _SOLE_CHAIR
               + r"(?:\s+and\s+(?:chief executive officer|ceo|president))?\s+of\s+(?:the|our)\s+company\b", re.I),
    re.compile(r"\b" + _LEADERSHIP_VERB + r"\b[^.;]{0,40}\bas\s+(?:our|the company['’]s)\s+" + _BOARD_QUALIFIER
               + _SOLE_CHAIR + r"\b(?!\s+of\s+(?:the|our|its)\s+[^.;]{0,60}\bcommittee)", re.I),
)
_OWNED_LEADERSHIP = re.compile(
    r"\b" + _LEADERSHIP_VERB + r"\b[^.;]{0,40}\bas\s+(?P<owner>(?-i:[A-Z])[\w&\-]*)['’]s\s+" + _BOARD_QUALIFIER
    + _SOLE_CHAIR + r"\b(?!\s+of\s+(?:the|our|its)\s+[^.;]{0,60}\bcommittee)", re.I)
# People named in a row: "C. David Cush, Sarah E. Feinberg, and Patricia A.
# Watson", "Mses. Feinberg and Watson and Messrs. Cush, Grissen, and Saretsky".
_NAME_LIST = ("(?:(?:(?:mr|ms|mrs|dr|messrs|mses)\\.?\\s+)?(?-i:[A-Z])[\\w’'\\-]*\\.?"
              "(?:[\\s,]+(?:and\\s+)?(?:(?:mr|ms|mrs|dr|messrs|mses)\\.?\\s+)?(?-i:[A-Z])[\\w’'\\-]*\\.?){0,24})")
# Who joins, leaves or stays on the board or a committee. These name the
# person (checked separately), so "candidates are appointed to the Board"
# describes a process and is not taken.
_MEMBERSHIP_CHANGE = (
    re.compile(r"\b(?:not (?:be )?stand(?:ing)? for re-?election|will not stand|(?:will )?retire[sd]? from (?:the|our)"
               r" board|retiring from (?:the|our) board|joined (?:the|our) board|became (?:a )?members? of (?:the|our)"
               r" board|resign(?:ed|s|ation)? from (?:the|our) board|remain (?:a member of|on) (?:the|our) board"
               r"|(?:service|term) on the board will (?:cease|end|expire)|will (?:cease|leave) (?:to serve )?(?:on )?"
               r"(?:the|our) board)\b", re.I),
    re.compile(r"\b(?:appoint|elect|add)(?:ed|ing|s)?\s+" + _NAME_LIST + r"\s*,?\s+to (?:the|our) board\b", re.I),
    re.compile(r"\b(?:appointment|election|addition)s?\s+of\s+" + _NAME_LIST + r"\s+to (?:the|our) board\b", re.I),
    re.compile(r"(?-i:[A-Z])[\w’'\-]*['’]s\s+(?:appointment|election|addition)\s+to (?:the|our) board\b", re.I),
    re.compile(r"\b(?:was|were|been|is|are|being)\s+(?:appointed|elected|added|named)\s+to\s+(?:the|our)\s+board\b",
               re.I),
    re.compile(r"\bceased to (?:be|serve as)\b[^.;]{0,60}?\b(?:directors?|members? of (?:the|our) board)\b", re.I),
    re.compile(r"\bjoined (?:the|our)\s+[^.;]{0,60}?\bcommittee\b", re.I),
    re.compile(r"\bserved (?:as (?:a )?members? )?(?:on|of) (?:the|our) board(?: of directors)? from\b", re.I),
)
_OWNED_CHANGE = re.compile(
    r"\bserved (?:as (?:a )?members? )?(?:on|of) (?P<owner>(?-i:[A-Z])[\w&\-]*)['’]s board(?: of directors)? from\b", re.I)
# Changes stated without a person: a count of new directors with its date, or
# that none were added. A count or a denial is itself the fact.
_MEMBERSHIP_COUNT = (
    re.compile(r"\b(?:did not|has not|have not|had not)\s+(?:elect|appoint|add|nominate)(?:ed)?\s+any new\s+"
               r"(?:independent\s+)?directors?\b", re.I),
    re.compile(r"\b" + _NUM + r"\s+new\s+(?:independent\s+)?directors?\b[^.;]{0,30}?\b(?:effective|appointed|elected"
               r"|added|joined|since|in\s+\d{4})\b", re.I),
    re.compile(r"\b(?:appoint|elect|add)(?:ed|ing)\s+" + _NUM + r"\s+new\s+(?:independent\s+)?directors?\b", re.I),
)
_BOARD_SIZE_CHANGE = (
    re.compile(r"\b(?:reduc|increas|decreas|expand)\w*\s+(?:its|the)\s+(?:board\s+)?size\s+(?:from\s+" + _NUM
               + r"\s+)?to\s+" + _NUM + r"\b", re.I),
    re.compile(r"\b(?:reduc|increas|decreas|expand)\w*\s+the\s+(?:size of the board|board(?:['’]s)? size)\s+(?:from\s+"
               + _NUM + r"\s+)?to\s+" + _NUM + r"\b", re.I),
    re.compile(r"\bboard size\s+(?:was\s+|will be\s+|has been\s+)?(?:reduced|increased|decreased|expanded)\s+(?:from\s+"
               + _NUM + r"\s+)?to\s+" + _NUM + r"\b", re.I),
    re.compile(r"\b" + _NUM + r"\s+(?:directors|members)\s+(?:then[- ]|currently\s+|now\s+)?serving\s+on\s+(?:our|the)"
               r"\s+board\b", re.I),
)
# A count of the board's non-employee directors on a date. It is stated
# wherever the filing states it - an equity plan's eligibility paragraph
# included - so the pay and plan topics that set a sentence aside do not set
# this one aside.
_DIRECTOR_COUNT = re.compile(
    r"\b(?:had|has|have|there (?:were|are)|including|of (?:our|the|its))\b[^.;]{0,60}?\b" + _NUM
    + r"\s+(?:non-employee|non-management|outside)\s+directors\b", re.I)
# A committee chair named where the filing explains a fee: "Cash fees paid
# to Mr. Roos relate to his service as Chair of the Compensation Committee for
# the first quarter". The pay is set aside; who chaired which committee is not.
_SERVICE_AS_CHAIR = re.compile(r"\b(?:his|her|their)\s+service\s+as\s+(?:the\s+)?chair(?:man|person|woman)?\s+of\s+"
                               r"(?:the|our)\s+[^.;]{0,60}?\bcommittee\b", re.I)
# Determinations about the directors themselves: that all of them meet the
# board's criteria, or a finding made under the director independence
# standards.
_DIRECTOR_DETERMINATION = (
    re.compile(r"\b(?:determined|concluded|found)\s+that\s+(?:all|each)\s+(?:of\s+(?:our|the)\s+)?(?:current\s+)?"
               r"(?:non-employee\s+)?directors?\b[^.;]{0,160}\b(?:are|is|have|has|meet|meets|satisf(?:y|ies)"
               r"|compl(?:y|ies)|qualif(?:y|ies))\b", re.I),
    re.compile(r"\b(?:determined|concluded|found)\s+that\s+the\s+(?:criteria|qualifications|standards)\s+for\s+"
               r"(?:board\s+)?membership\s+(?:have been|has been|are|were)\s+(?:satisfied|met)\b", re.I),
    re.compile(r"\b(?:board|committee)\b[^.;]{0,80}\b(?:determined|concluded|found)\b[^.;]{0,400}\b(?:standards? for"
               r" director independence|director independence standards)\b", re.I),
)
_ROSTER_STATEMENT = re.compile(
    r"\b(?:nominees for election|director nominees|nominees|current directors|members of (?:the|our) board)\b"
    r"[^.;]{0,60}\b(?:are|include)\b\s*(?:the following\b|:)", re.I)
_HONORIFIC_WORD = re.compile(r"\b(?:Mr|Ms|Mrs|Dr|Messrs|Mses)\b")
_CAPITAL_SPAN = re.compile("\\b[A-Z][\\w’'\\-]+(?:\\s+(?:[A-Z]\\.?|[A-Z][\\w’'\\-]+)){1,3}\\b")


_LEADING_TITLE = re.compile(r"^(?:(?:ceo|cfo|coo|chief|executive|officer|president|chairman|chair|director"
                            r"|general|governor|judge|former|our|the|and|founder|co-founder|vice)\s+)+", re.I)


def _mentions_person(sentence):
    """True when the sentence names a person, by honorific or by a full name.

    A change to who sits on the board is a fact about someone; "candidates are
    appointed to the Board" describes the process by which it happens. A full
    name is two or more name words once any leading title is set aside ("CEO
    Jeffrey K. Storey"), ending in a surname written as a word ("Agentic AI"
    ends in an abbreviation and is not one).
    """
    if _HONORIFIC_WORD.search(sentence):
        return True
    for match in _CAPITAL_SPAN.finditer(sentence):
        span = _LEADING_TITLE.sub("", match.group(0))
        tokens = span.split()
        if (len(tokens) >= 2 and person_name(span) and not tokens[0].isupper()
                and re.fullmatch("[" + _UPPER + "][" + _LOWER + "]{2,}(?:[-'’][" + _UPPER + "]?[" + _LOWER + "]+)*",
                                 tokens[-1])):
            return True
    return False


def _other_organization(sentence, own_words):
    """True when the sentence places a board or committee at another body.

    Biographies speak of "the audit committee of Acme", "a director of the
    Federal Home Loan Bank", "on the State Street Corporation board" and "At
    Vonage, he served on the audit and compensation committees". The words of
    this registrant's name and of its own committees are not another body.
    """
    for match in re.finditer("\\b(?:board(?:s| of directors)?|committees?)\\s+(?:of|at|for)\\s+(?:the\\s+)?"
                             "([A-Z][A-Za-z&’'\\-]+)", sentence, re.I):
        word = re.sub("[’']s$", "", match.group(1))
        if word[0].isupper() and word.casefold() not in {"board", "directors", "company", "committee",
                                                           "committees"} | own_words:
            return True
    for match in re.finditer("\\b(?:director|trustee|member|board member|member of the board|chair(?:man|person"
                             "|woman)?|vice chair|president|chief executive officer|ceo|partner|founder|governor"
                             "|dean|professor)\\s+(?:of|at)\\s+(?:the\\s+)?([A-Z][A-Za-z&’'\\-]+)",
                             sentence, re.I):
        word = re.sub("[’']s$", "", match.group(1))
        if word[0].isupper() and word.casefold() not in {"board", "directors", "company", "committee"} | own_words:
            return True
    if re.search("\\bon the (?:[A-Z][\\w&’'\\-]*\\s+){1,5}board\\b", sentence):
        return True
    match = re.search("\\b[Aa]t\\s+([A-Z][\\w&’'\\-]+)(?:\\s+[A-Z][\\w&’'\\-]+)*\\s*,", sentence)
    return bool(match and re.sub("[’']s$", "", match.group(1)).casefold() not in own_words)


def _acronym_service(sentence, acronyms):
    """True when the sentence seats directors on a committee named by its acronym."""
    if not acronyms:
        return False
    return bool(re.search(r"\b(?:served|serve|serves|serving|sit|sits|sat)\s+(?:as\s+(?:a\s+)?members?\s+)?on\s+"
                          r"(?:the|our)\s+(?-i:" + "|".join(sorted(acronyms)) + r")\b", sentence, re.I))


def statement_labels(text, own_words=frozenset(), *, acronyms=frozenset(), registrant=frozenset()):
    """The composition facts a prose block states, one label per kind.

    Args:
        text: The block's text.
        own_words: Words of the registrant's name and of its committees' names;
            a board or committee named with them is not another body.
        acronyms: The short forms this filing uses for its own committees.
        registrant: Words of the registrant's name, for a possessive owner.
    """
    labels = set()
    for sentence in sentences(text):
        if _FIRST_PERSON.search(sentence):
            continue
        unqualified = _QUALIFYING_REFERENCE.sub(" ", sentence)
        policy = _POLICY.search(unqualified)
        determination = _DETERMINATION.search(unqualified)
        if policy and (determination is None or policy.start() < determination.start()):
            continue
        if _other_organization(sentence, own_words):
            continue
        if _DIRECTOR_COUNT.search(sentence):
            labels.add("BOARD_SIZE_STATEMENT")
        if _SERVICE_AS_CHAIR.search(sentence) and _mentions_person(sentence):
            labels.add("COMMITTEE_COMPOSITION_STATEMENT")
        if _EXCLUDED_TOPIC.search(sentence):
            continue
        independence = _NOT_DIRECTOR_INDEPENDENCE.sub(" ", sentence)
        if any(p.search(sentence) for p in (*_BOARD_SIZE, *_BOARD_SIZE_CHANGE)):
            labels.add("BOARD_SIZE_STATEMENT")
        if any(p.search(independence) for p in _BOARD_INDEPENDENCE):
            labels.add("BOARD_INDEPENDENCE_STATEMENT")
        if any(p.search(sentence) for p in _DIRECTOR_DETERMINATION):
            labels.add("DIRECTOR_QUALIFICATION_DETERMINATION")
        if any(p.search(sentence) for p in _COMMITTEE_COMPOSITION) or _acronym_service(sentence, acronyms):
            labels.add("COMMITTEE_COMPOSITION_STATEMENT")
        if any(p.search(sentence) for p in (*_STANDING, *_COMMITTEE_SETUP)):
            labels.add("STANDING_COMMITTEES_STATEMENT")
        owned = _OWNED_LEADERSHIP.search(sentence)
        if (any(p.search(sentence) for p in _LEADERSHIP)
                or (owned and owned.group("owner").casefold() in registrant)):
            labels.add("BOARD_LEADERSHIP_STATEMENT")
        owned = _OWNED_CHANGE.search(sentence)
        if (_mentions_person(sentence)
                and (any(p.search(sentence) for p in _MEMBERSHIP_CHANGE)
                     or (owned and owned.group("owner").casefold() in registrant))):
            labels.add("BOARD_MEMBERSHIP_CHANGE")
        if any(p.search(sentence) for p in _MEMBERSHIP_COUNT):
            labels.add("BOARD_MEMBERSHIP_CHANGE")
        if _ROSTER_STATEMENT.search(sentence):
            labels.add("BOARD_ROSTER_STATEMENT")
        if (_QUALIFICATION.search(independence) and _MEMBER_REFERENCE.search(sentence)
                and _STATE.search(sentence)):
            labels.add("COMMITTEE_MEMBER_QUALIFICATION")
    return sorted(labels)


# --------------------------------------------------------- smaller structures
_CARD_LABEL = re.compile(r"^committees?\s*:\s*(?P<rest>.*)$", re.I)
_NONE_ITEM = re.compile("^[" + _BULLET_CHARS + "]?\\s*(?P<none>n/?a|none)\\s*\\.?$", re.I)
_ITEM_CHAIR = re.compile(r"\s*(?:\(\s*(?:chair(?:man|person|woman)?|vice[- ]chair)\s*\)|,\s*chair(?:man|person|woman)?)"
                         r"\s*[*†‡§#+]*$", re.I)
_CHANGE_LABEL = re.compile(r"^(?:additions|departures|changes|committee changes)\s*:?\s*$", re.I)
_CHANGE_LINE = re.compile(r"^(?:(?:" + _MONTHS + r")\s+\d{4}|\d{4})\s*:\s*\S", re.I)
_LIST_ITEM = re.compile("^[" + _BULLET_CHARS + "]\\s*\\S")
_CHANGE_REACH = 40
_CARD_REACH = 8
_NOT_YET_DIRECTOR = re.compile(r"^director since\s*:?\s*(?:n/?a|nominated\b|new nominee\b|nominee\b)", re.I)
_SMALL_WORDS = frozenset({"and", "of", "the", "&", "for", "on"})


def _committee_vocabulary(headings):
    """How this filing refers to each of its committees in a card or a sentence.

    Built from the committee headings the filing prints: the name, the name
    with "Committee", and its initials with and without a trailing C ("NCG",
    "HRCC", "A" for Audit). A card item or an acronym counts as a committee
    only when it is one of these.
    """
    vocabulary = {}
    for _span, name in headings:
        words = name.split()
        vocabulary.setdefault(name, name)
        vocabulary.setdefault(name + " committee", name)
        initials = "".join(word[0] for word in words if word not in _SMALL_WORDS)
        if initials:
            vocabulary.setdefault(initials, name)
            vocabulary.setdefault(initials + "c", name)
    return vocabulary


def _card_item(text, vocabulary):
    """The committee a card item names, or None."""
    bare = _ITEM_CHAIR.sub("", _BULLET.sub("", clean(text))).strip()
    if not bare or len(bare) > 90:
        return None
    return committee_name(bare) or vocabulary.get(bare.casefold())


def _card_field(block):
    """A short field of a director card: age, tenure, title, a designation."""
    text = clean(block["text"])
    return bool(text) and not block["linked"] and len(text) <= 120 and not _CARD_LABEL.match(text)


def _full_name(blocks, k, registrant):
    """The blocks of the full name that ends at ``k``, or None.

    A card prints its director's full name - two or more name words. Where the
    layout broke it in two ("Michael" / "Collins", "Thurman John" / "Rodgers")
    the two blocks together are the name. A single word on its own ("Mastercard",
    "Williams-Sonoma") is a card field, not a name.
    """
    block = blocks[k]
    text = clean(block["text"])
    if block["linked"] or not person_name(text) or re.sub(r"\W", "", text.casefold()) in registrant:
        return None
    if len(_strip_name(text).split()) >= 2:
        return [k]
    if k > 0 and not blocks[k - 1]["linked"] and person_name(blocks[k - 1]["text"]):
        joined = clean(blocks[k - 1]["text"]) + " " + text
        if person_name(joined) and len(_strip_name(joined).split()) >= 2:
            return [k - 1, k]
    return None


def _name_from(blocks, j, registrant):
    """A full name that starts at ``j``: one block, or ``j`` and the next."""
    single = _full_name(blocks, j, registrant)
    if single == [j]:
        return single
    split = _full_name(blocks, j + 1, registrant) if j + 1 < len(blocks) else None
    return split if split == [j, j + 1] else None


def _card_name(blocks, before, after, registrant, *, passable=_card_field):
    """The card's director: the full name after ``after`` or before ``before``.

    Card fields (age, tenure, a title, a designation) may stand between the
    name and the field that was read; nothing else may. A name found on both
    sides belongs to one of two cards and is not chosen.
    """
    following = None
    for j in range(after, min(len(blocks), after + _CARD_REACH)):
        text = clean(blocks[j]["text"])
        if not text or _ONE_BULLET.match(text):
            continue
        following = _name_from(blocks, j, registrant)
        if following or not passable(blocks[j]):
            break
    preceding = None
    for k in range(before - 1, max(-1, before - 1 - _CARD_REACH), -1):
        if not clean(blocks[k]["text"]):
            continue
        preceding = _full_name(blocks, k, registrant)
        if preceding or not _card_field(blocks[k]):
            break
    if following and preceding:
        return None
    return following or preceding


def _card_fields(blocks, label, name):
    """The card's own field blocks from its name to its label, either order."""
    low, high = (name, label) if name < label else (label, name)
    return [clean(blocks[k]["text"]) for k in range(max(0, low - _CARD_REACH), high + 1)
            if _card_field(blocks[k])]


def _cards(blocks, vocabulary, registrant):
    """A director card: its committee label, its items and the director it names.

    Items are the filing's own committee names or short forms; an item list may
    follow the label on its own lines or share its line. "None" and "N/A" say a
    director sits on no committee - but not on the card of a nominee who is not
    yet a director ("Director since: N/A"), where they state nothing about the
    board. A card whose director cannot be told apart from a neighbour's is left
    out rather than guessed.
    """
    taken = []
    for i, block in enumerate(blocks):
        match = _CARD_LABEL.match(clean(block["text"]))
        if not match or block["linked"]:
            continue
        rest = match.group("rest").strip()
        j, items, negative = i + 1, [], False
        if rest:
            if _NONE_ITEM.match(rest):
                negative = True
            elif not all(_card_item(part, vocabulary) for part in re.split(r"\s*,\s*(?![^()]*\))", rest)):
                continue
        else:
            while j < len(blocks):
                text = clean(blocks[j]["text"])
                if not text or _ONE_BULLET.match(text):
                    j += 1
                    continue
                if not items and _NONE_ITEM.match(text):
                    items.append(j)
                    negative = True
                    j += 1
                    break
                if not blocks[j]["linked"] and _card_item(text, vocabulary):
                    items.append(j)
                    j += 1
                    continue
                break
            if not items:
                continue
        name = _card_name(blocks, i, j, registrant, passable=lambda block: False)
        if name is None:
            continue
        if negative and any(_NOT_YET_DIRECTOR.match(field) for field in _card_fields(blocks, i, name[0])):
            continue
        taken.append((i, "DIRECTOR_NO_COMMITTEE" if negative else "DIRECTOR_COMMITTEE_LABEL"))
        taken.extend((k, "DIRECTOR_NO_COMMITTEE" if negative else "DIRECTOR_COMMITTEE_ITEM") for k in items)
        taken.extend((k, "DIRECTOR_NAME") for k in name)
    return taken


_AGE_PREFIX = re.compile(r"^age\s*:?\s*\d{2}\s*\|\s*", re.I)
_CARD_EVIDENCE = re.compile(r"^(?:age\s*:?\s*\d{2}\b|\d{2}\s+years old$|director since\s*:?\s*(?:\w+\s+)?(?:\d{4}|n/?a"
                            r"|nominated)|\(\d{2}\)$)", re.I)
_DESIGNATION_WORDS = frozenset("""independent director directors nominee chair chairman chairperson chairwoman vice lead
of the board and non-executive executive current new incoming retiring chief officer president ceo""".split())
_DESIGNATION_CORE = frozenset({"independent", "director", "nominee", "chair", "chairman", "chairperson", "chairwoman"})


def _designation(text):
    """True when a card field is only a designation of the person on the board."""
    words = re.findall(r"[a-z\-]+", _AGE_PREFIX.sub("", clean(text)).casefold())
    return bool(words) and not set(words) - _DESIGNATION_WORDS and bool(set(words) & _DESIGNATION_CORE)


def _designations(blocks, registrant):
    """A card's designation field and the director it belongs to.

    The designation is the filing's own word for what the person is on the
    board - "Independent", "Director Nominee", "Independent Chair of the
    Board", or "Director" where the other cards print "Independent Director"
    - so a card says so itself. A designation counts only on a card: an age,
    a "years old" or a "Director since" field sits beside it, so a table's
    "Director" column header is not read as one.
    """
    taken = []

    def passable(block):
        text = clean(block["text"])
        return _card_field(block) or bool(_CARD_LABEL.match(text)) or bool(_NONE_ITEM.match(text))

    for i, block in enumerate(blocks):
        text = clean(block["text"])
        if block["linked"] or not text or len(text) > 90 or not _designation(text):
            continue
        near = [clean(blocks[k]["text"]) for k in range(max(0, i - 3), min(len(blocks), i + 4))]
        if not (_AGE_PREFIX.match(text) or any(_CARD_EVIDENCE.match(field) for field in near)):
            continue
        name = _card_name(blocks, i, i + 1, registrant, passable=passable)
        if name is None:
            continue
        taken.append((i, "DIRECTOR_DESIGNATION"))
        taken.extend((k, "DIRECTOR_NAME") for k in name)
    return taken


# A title line that places a board chair title at this registrant:
# "Chairman and Chief Executive Officer, Macy's, Inc.", "President, CEO, and
# Vice Chairman of the Board of Southwest Airlines Co.". Any other body named
# in the same clause, or a former title, makes it a line about someone else.
_TITLE_LINE_CHAIR = re.compile(r"\b(?:vice[- ])?chair(?:man|person|woman)?\b", re.I)
_TITLE_LINE_PAST = re.compile(r"\b(?:former|formerly|retired|previously|prior|emerit\w*|until)\b", re.I)
_CAPITALISED_RUN = re.compile("(?:[A-Z][\\w’'&\\.\\-]*)(?:\\s+(?:[A-Z][\\w’'&\\.\\-]*|&))*")
_RUN_IGNORED = frozenset("""president chief executive officer operating financial ceo cfo coo vice chair chairman
chairperson chairwoman board directors director lead independent non-executive since present founder co-founder
and inc inc. co co. corp corp. corporation company ltd llc plc the of""".split()) | frozenset(_MONTHS.split("|"))
_LEGAL_SUFFIX = frozenset({"inc", "co", "corp", "corporation", "company", "ltd", "llc", "plc", "the", "lp"})


def _name_core(text):
    """The words of an organisation's name without legal suffixes or state tags."""
    text = re.sub(r"/[A-Z]{2}/", " ", text).casefold().replace("’", "'")
    return tuple(word for word in re.findall(r"[a-z0-9']+", text) if word not in _LEGAL_SUFFIX)


def _registrant_cores(document):
    return {core for core in (_name_core(name) for name in document.get("registrant_names", [])) if core}


def _is_registrant(run, cores):
    core = _name_core(run)
    return bool(core) and any(set(core) <= set(full) and core[0] == full[0] for full in cores)


def _registrant_title_lines(blocks, cores):
    """Title lines that give a board chair title at this registrant."""
    taken = []
    for i, block in enumerate(blocks):
        text = clean(block["text"])
        if block["linked"] or not text or len(text) > 250 or not _TITLE_LINE_CHAIR.search(text):
            continue
        for clause in re.split(r"[;|]", text):
            if not _TITLE_LINE_CHAIR.search(clause) or _TITLE_LINE_PAST.search(clause):
                continue
            runs = [run for run in _CAPITALISED_RUN.findall(clause)
                    if {w.strip(".,").casefold() for w in run.split()} - _RUN_IGNORED]
            if runs and all(_is_registrant(run, cores) for run in runs):
                taken.append((i, "BOARD_LEADERSHIP_TITLE"))
                break
    return taken


# A heading over a table of directors grouped by class or status, and the
# names that lead the table's rows.
_GROUP_HEADING = re.compile(
    r"^(?:continuing\s+)?class\s+(?:i{1,3}|iv|v|[1-5])\s+(?:director\s+)?(?:nominees|directors)\b"
    r"|^(?:director\s+)?nominees\s+for\s+election\b|^continuing\s+directors\b"
    r"|^directors\s+continuing\s+in\s+office\b", re.I)
_GROUP_REACH = 60


def _director_groups(blocks, registrant):
    """Director-group headings and the names in the rows beneath them.

    Rows lead with the director's name, emphasised; the fields after it
    (occupation, age, year, marks) are not names. The table ends at the next
    emphasised block that is not a name - the next group's heading - or at
    prose. A heading followed by anything but a name within three blocks, or
    by a single name, heads director cards, not a table, and is left to the
    cards.
    """
    taken = []
    for i, block in enumerate(blocks):
        if block["linked"] or not _GROUP_HEADING.match(clean(block["text"])):
            continue
        names, j = [], i + 1
        while j < min(len(blocks), i + 1 + _GROUP_REACH):
            text = clean(blocks[j]["text"])
            if len(text) > 150:
                break
            is_name = (person_name(text) and not blocks[j]["linked"]
                       and re.sub(r"\W", "", text.casefold()) not in registrant)
            if is_name and blocks[j].get("emphasized"):
                names.append(j)
            elif blocks[j].get("emphasized") and len(re.sub(r"[^A-Za-z]", "", text)) >= 5:
                break
            if not names and j > i + 3:
                break
            j += 1
        # One name under a heading is a card that follows it, not a table.
        if len(names) >= 2:
            taken.append((i, "DIRECTOR_GROUP_HEADING"))
            taken.extend((k, "DIRECTOR_GROUP_MEMBER") for k in names)
    return taken


_FOOTNOTE_MARK = re.compile(r"^\(?(?P<mark>\d{1,2}|[*†‡§#]+)\)?$")
_FOOTNOTED_CHANGE = re.compile(
    r"^(?:retired|resigned|departed|stepped down|appointed|elected|joined|ceased)\b[^.;]{0,60}\b(?:from|to|as)"
    r"\s+(?:a\s+(?:member|director)\s+of\s+)?(?:the|our)\s+board\b", re.I)
_FOOTNOTE_REACH = 80


def _footnoted_changes(blocks, registrant):
    """A table's footnote that states a change, and the names that carry its mark.

    "(2) Retired from the Board effective May 14, 2025." states the change of
    every row whose name ends in "(2)"; without those names it says nothing
    about whom, so it is taken only with them.
    """
    taken = []
    for i, block in enumerate(blocks):
        if i == 0 or block["linked"] or not _FOOTNOTED_CHANGE.match(clean(block["text"])):
            continue
        mark = _FOOTNOTE_MARK.match(clean(blocks[i - 1]["text"]))
        if not mark:
            continue
        suffix = "(" + mark.group("mark") + ")"
        names = [k for k in range(max(0, i - _FOOTNOTE_REACH), i - 1)
                 if clean(blocks[k]["text"]).endswith(suffix) and not blocks[k]["linked"]
                 and person_name(blocks[k]["text"])
                 and re.sub(r"\W", "", clean(blocks[k]["text"]).casefold()) not in registrant]
        if names:
            taken.extend((k, "FOOTNOTED_DIRECTOR") for k in names)
            taken.append((i, "FOOTNOTED_MEMBERSHIP_CHANGE"))
    return taken


def _changes(blocks, heading_starts):
    """Dated membership changes a committee page lists under a label."""
    taken = []
    for i, block in enumerate(blocks):
        if not _CHANGE_LABEL.match(clean(block["text"])):
            continue
        if not any(h < i <= h + _CHANGE_REACH for h in heading_starts):
            continue
        j, lines = i + 1, []
        while j < len(blocks):
            line = clean(blocks[j]["text"])
            # A line the layout wrapped continues in lower case.
            if _CHANGE_LINE.match(line) or (lines and line[:1].islower()):
                lines.append(j)
                j += 1
                continue
            break
        if lines:
            taken.append((i, "COMMITTEE_CHANGE_LABEL"))
            taken.extend((line, "COMMITTEE_CHANGE") for line in lines)
    return taken


# A lead-in introduces a list of people only when what precedes its colon is
# about people - directors, members, nominees - and not about duties.
_PEOPLE_LEAD_IN = re.compile(r"\b(?:directors|members|nominees|individuals|served|serve|serving|independent)\b",
                             re.I)
_DUTY_LEAD_IN = re.compile(r"\b(?:responsib\w*|duties|duty|oversee\w*|oversight|role|functions?|purpose"
                           r"|among other things|include[sd]?\s+(?:the following\s+)?(?:matters|tasks|activities))\b",
                           re.I)


def _introduces_people(sentence):
    tail = clean(sentence)[-80:]
    return bool(_PEOPLE_LEAD_IN.search(tail)) and not _DUTY_LEAD_IN.search(tail)


def _list_items(blocks, index):
    """The bulleted items a lead-in sentence ending in a colon introduces."""
    taken, j, after_marker = [], index + 1, False
    while j < len(blocks):
        text = clean(blocks[j]["text"])
        if _BULLETS_ONLY.match(text):
            after_marker = True
            j += 1
            continue
        if (after_marker or _LIST_ITEM.match(text)) and not blocks[j]["linked"]:
            taken.append((j, "LIST_ITEM"))
            after_marker = False
            j += 1
            continue
        break
    return taken


def _policy_identity():
    """The rule set this reader applies, as data: what the proposal names.

    Every module-level pattern, pattern group, word list and reach is part of
    the rule, so a change to any of them changes the proposal's identity.
    """
    rules = {}
    for name, value in sorted(globals().items()):
        if isinstance(value, re.Pattern):
            rules[name] = value.pattern
        elif isinstance(value, tuple) and value and all(isinstance(p, re.Pattern) for p in value):
            rules[name] = [p.pattern for p in value]
        elif isinstance(value, frozenset):
            rules[name] = sorted(value)
        elif isinstance(value, int) and not isinstance(value, bool) and name.isupper() and name.startswith("_"):
            rules[name] = value
    return content_hash(value={"selection_policy": SELECTION_POLICY, "rules": rules})


def _acronyms(headings):
    """The initials a filing uses for its own committees, as it prints them."""
    found = set()
    for _span, name in headings:
        initials = "".join(word[0] for word in name.split() if word not in _SMALL_WORDS).upper()
        if len(initials) >= 2:
            found.update({initials, initials + "C"})
    return frozenset(found)


def board_composition_facts(*, document):
    """Return the composition facts one governance document states.

    Args:
        document: The governance document record the frozen preparation built
            (``text_business_candidates.governance_source_document``).

    Returns:
        A proposal of the frozen record type, whose candidates are whole-block
        excerpts in document order, each carrying the structures that selected
        it. Counts, dates and associations are never inferred.
    """
    _check_document(document)
    blocks = document["blocks"]
    registrant = _registrant_keys(document)
    cores = _registrant_cores(document)
    headings = _committee_headings(blocks)
    registrant_words = frozenset(word.casefold() for name in document.get("registrant_names", [])
                                 for word in re.findall(r"[A-Za-z]+", name)) - _LEGAL_SUFFIX
    own_words = frozenset({word for _, name in headings for word in name.split()} | registrant_words) - _SMALL_WORDS
    acronyms = _acronyms(headings)
    vocabulary = _committee_vocabulary(headings)
    picked = {}

    def take(index, label):
        picked.setdefault(index, set()).add(label)

    for index, label in _committee_structures(blocks, headings, registrant):
        take(index, label)
    for i, block in enumerate(blocks):
        text = clean(block["text"])
        if block["linked"] or not re.search(r"[A-Za-z]", text) or re.sub(r"\W", "", text.casefold()) in registrant:
            continue
        labels = statement_labels(block["text"], own_words, acronyms=acronyms, registrant=registrant_words)
        for label in labels:
            take(i, label)
        # A lead-in introduces a list only when the sentence that ends in the
        # colon is itself a composition statement about people; "Its
        # responsibilities include:" introduces duties.
        last = sentences(block["text"])[-1] if labels and text.endswith(":") else ""
        if last and _introduces_people(last) and statement_labels(
                last, own_words, acronyms=acronyms, registrant=registrant_words):
            for index, label in _list_items(blocks, i):
                take(index, label)
    for index, label in (*_changes(blocks, sorted(span[0] for span, _ in headings)),
                         *_cards(blocks, vocabulary, registrant), *_designations(blocks, registrant),
                         *_registrant_title_lines(blocks, cores), *_director_groups(blocks, registrant),
                         *_footnoted_changes(blocks, registrant)):
        take(index, label)
    candidates = [_excerpt(document, blocks[i], SECTION_ID, sorted(picked[i])) for i in sorted(picked)]
    body = {"record_type": "BOARD_COMPOSITION_SOURCE_CANDIDATES", "metric_id": "C02",
            "document_id": document["text_document_id"], "source_reference_id": document["source_reference_id"],
            "scope": "LOCAL_PROXY_OR_ANNUAL_AMENDMENT_TEXT", "source_filing": document["source_filing"],
            "coverage_status": document["source_state"], "source_reasons": document["source_reasons"],
            "finding_status": "SOURCE_EXCERPTS_FOUND" if candidates else "NO_SUPPORTED_STATEMENT_PATTERN",
            "candidates": candidates, "numeric_board_counts_asserted": False,
            "board_measurement_date_assigned": False, "not_disclosed_confirmed": False,
            "semantic_interpretation": "VERBATIM_BOARD_COMPOSITION_FACTS_NOT_AS_OF_BOARD_INFERENCE",
            "selection_policy": SELECTION_POLICY,
            "committee_headings": [{"blocks": list(range(span[0], span[1] + 1)), "committee": name}
                                   for span, name in headings],
            "native_result_created": False, "publication_credit": False}
    policy_hash = _policy_identity()
    return {**body, "policy_hash": policy_hash,
            "proposal_id": content_hash(value={**body, "policy_hash": policy_hash})}
