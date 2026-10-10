"""Keep two annual claims on one reported measure before dividing them.

This is the shared, source-only form of the Issue #47 B02/A07 guard at
48b46a2d. The approved catalog still chooses each component independently;
this check never selects another concept or a restated prior-year value.
"""
from decimal import Decimal


PAIRED_MEASURE_REASON = 'NORMAL_PAIRED_MEASURE_NOT_COMPARABLE'


def _paired_concept_lists(route):
    paired = set()
    for branch in route['branches']:
        roles = {}
        for component in branch['components']:
            roles.setdefault(tuple(component['approved_concepts']), set()).add(
                component['accession_role'])
        paired.update(concepts for concepts, seen in roles.items()
                      if {'current', 'prior'} <= seen)
    return paired


def _claim_view(claim):
    locator = claim['locator']
    return {'concept': locator['concept'],
            'period_start': locator['period_start'],
            'period_end': locator['period_end'],
            'accession': claim['attributes']['accession'],
            'unit': claim['unit'], 'value': str(claim['value'])}


def paired_measure_problem(*, route, claims, current_claims, accessions):
    """Return a named mismatch unless the target filing bridges two labels.

    The bridge is a fact in the target filing under the current selected
    concept, for the prior period, equal to the *selected prior filing value*.
    It proves the two labels refer to the same reported quantity for that
    comparison. It does not authorize choosing a different branch or replacing
    that prior value with a later restatement.
    """
    bridged = []
    for concepts in sorted(_paired_concept_lists(route)):
        used = {role: [claim for claim in claims
                       if claim['locator']['concept'] in concepts
                       and claim['attributes']['accession'] == accessions[role]]
                for role in ('current', 'prior')}
        if len(used['current']) != 1 or len(used['prior']) != 1:
            continue
        current, prior = _claim_view(used['current'][0]), _claim_view(used['prior'][0])
        reported = sorted({str(Decimal(str(claim['value'])))
                           for claim in current_claims
                           if claim['attributes']['accession'] == accessions['current']
                           and claim['locator']['concept'] == current['concept']
                           and claim['locator']['period_start'] == prior['period_start']
                           and claim['locator']['period_end'] == prior['period_end']
                           and claim['unit'] == prior['unit']})
        pair = {'current': current, 'prior': prior,
                'target_filing_reports_the_prior_year_under_the_current_concept': reported}
        comparison_matches = {Decimal(v) for v in reported} == {Decimal(prior['value'])}
        if current['concept'] == prior['concept']:
            # A shared label does not resolve an explicit contradictory
            # prior-period comparison in the current filing. Keep the original
            # prior value; never replace it with a later recast amount.
            if reported and not comparison_matches:
                return {'reason_code': PAIRED_MEASURE_REASON, **pair}, bridged
            continue
        if comparison_matches:
            bridged.append(pair)
            continue
        return {'reason_code': PAIRED_MEASURE_REASON, **pair}, bridged
    return None, bridged
