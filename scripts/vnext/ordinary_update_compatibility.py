"""One finite old-configuration bridge, without changing saved results.

The received finance cases have exactly three nonbusiness differences from
their saved configuration: an unused session, its removal in the controller,
and a B12-only display note. Every other dependency and input still compares.
This is cache compatibility, never permission to execute or accept a result.
"""
from copy import deepcopy

CONTROLLER = 'scripts/vnext/ordinary_current_update.py'
SESSION = 'scripts/vnext/ordinary_source_session.py'
PRESENTATION = 'config/ordinary_public_projection_v1.json'
BRIDGE = 'scripts/vnext/ordinary_update_compatibility.py'
OLD_CONTROLLER = 'c47bb59eb044c0974582c42b8299b10ba925a55e23673f2ebe2a8d003a6ebe0e'
CURRENT_CONTROLLER = 'a694571002b98da791a7916eaaebd4d704acaea15cd482cf8a2606ca9bfc9724'
OLD_SESSION = '2357bfe3c2b62a835d01cd34de29d8f0076710d0327d721fe8bb97f6434be7e0'
OLD_PRESENTATION = 'f88cb1224a778237e2ce237a5e1c68827b228d3595cc9cf628a8e1c035937bbd'
CURRENT_PRESENTATION = '56b8ac7e116cecea31f1e2e323438351279b651a129c882c29111166702de4d8'
FINANCE_METRICS = frozenset({'A03','A04','A09','A11','A12','A13'})


def compatible_configuration(previous, current):
    """Recognize only the inspected transition; unknown changes reprocess."""
    if (previous.get('metric_id') not in FINANCE_METRICS
            or previous.get('requested_fiscal_year') is None):
        return False
    old,new=deepcopy(previous),deepcopy(current)
    left,right=old.get('processing_files',{}),new.get('processing_files',{})
    if (left.get(CONTROLLER)!=OLD_CONTROLLER or right.get(CONTROLLER)!=CURRENT_CONTROLLER
            or left.get(SESSION)!=OLD_SESSION or SESSION in right
            or left.get(PRESENTATION)!=OLD_PRESENTATION
            or right.get(PRESENTATION)!=CURRENT_PRESENTATION
            or BRIDGE in left or BRIDGE not in right):
        return False
    left.pop(SESSION);right.pop(BRIDGE)
    for path in (CONTROLLER,PRESENTATION):left.pop(path);right.pop(path)
    return old==new
