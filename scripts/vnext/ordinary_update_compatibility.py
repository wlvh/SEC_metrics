"""Finite compatibility for inspected unrelated dispatcher changes.

This is input comparison, not permission, result acceptance, or an instruction
that old files remain immutable. Unknown changes go through normal processing.
Every source, scope, producer and other dependency must still match exactly.
"""
from copy import deepcopy

CONTROLLER = 'scripts/vnext/ordinary_current_update.py'
STORE = 'scripts/vnext/ordinary_saved_result.py'
BRIDGE = 'scripts/vnext/ordinary_update_compatibility.py'
BEFORE_D04 = (
    '5c3657bd9023f1b5a0afb865d039a2e81cabef58e3c396c508b71f292132dcca',
    'f71cca5ed3ab7260764a83d58feb9e835eb8ce8da5b911c6b14b887623318a2d',
)
AFTER_D04 = (
    '434c645f5cfa61999483d1927b06158a51a58c9d977e552c801c7d7de1e20713',
    'ff23e46659e065bbc1c98c6eb4fef6702e9ebba594bf0f2c7e5110d0f49202dd',
)
MAIN_C99 = (
    '7270d5b23acbababd292f8f3833812d5927c1881ed925321d453b97f3908f700',
    'cfba3fa8cd6f1d6b9dcb6b49c50b8d40362069c0965171b9b022e79afcf9d0fd',
)
EXTRACTED_D04 = (
    '54e940cfe274a7abb2ef484d6e48231e8fc80569c817a27d58f1bf03ae7b1654',
    'd9ae369f7cc19c4728537fa91df4024a620917d57ec5c7cebf929d0968b11876',
)

MAIN_F51 = ('3c741f3500b34f1778b89875e2c19af71084a53749dc1cc7f2fabd368dc96976', 'cfba3fa8cd6f1d6b9dcb6b49c50b8d40362069c0965171b9b022e79afcf9d0fd')
EXTRACTED_MAIN_F51 = ('349d11b6ebbb35c41b2c5e38e8a3e3c3f32fb7d806d8e8a5379c69dd71f2ca85',
                      'd9ae369f7cc19c4728537fa91df4024a620917d57ec5c7cebf929d0968b11876')
EXTRACTED_BRIDGE = 'bf0f171024b086f4f85b6c8d81b31255c652fc76d70b51a92e929b971aa13fe3'

# db403009 -> main6efe adds only B04/B07 dispatch to the writer; the
# 16294aee D02 successor additionally registers D02 as an explicit case.
# Neither change alters E01's historical case, record writer or renderer.
E01_BEFORE_STORE = 'f7229fa090da9558f8fbbe759491671bc0adbf668e193e303fbbc42206947681'
E01_AFTER_STORES = frozenset({
    'd2cee7e3527cd99eb15a653b6d9778357acced0345af172a64a3c37a96f74ae2',
    '9f7de93d41929669c7f08f394425c1e3ad181896bdde3fa6d079ca3924272d21',
})
E01_PREVIOUS_BRIDGE = '14aba908024c3331d5f1e40301c5145ad294560d2dc267cf3bdce4e38f599950'
D02_SOURCE = 'scripts/vnext/d02_text_results_v3.py'


# Preserve the already reviewed explicit-year financial transition separately.
SESSION = 'scripts/vnext/ordinary_source_session.py'
PRESENTATION = 'config/ordinary_public_projection_v1.json'
OLD_CONTROLLER = 'c47bb59eb044c0974582c42b8299b10ba925a55e23673f2ebe2a8d003a6ebe0e'
INITIAL_FINANCE_CONTROLLER = 'a694571002b98da791a7916eaaebd4d704acaea15cd482cf8a2606ca9bfc9724'
CURRENT_CONTROLLER = '0dd95f46fb6058ddb65e2ee8adb3db33b5837e2cb143f92bc1597e6ad918d42c'
FINANCE_CURRENT_CONTROLLERS = frozenset({INITIAL_FINANCE_CONTROLLER,CURRENT_CONTROLLER})
OLD_SESSION = '2357bfe3c2b62a835d01cd34de29d8f0076710d0327d721fe8bb97f6434be7e0'
OLD_PRESENTATION = 'f88cb1224a778237e2ce237a5e1c68827b228d3595cc9cf628a8e1c035937bbd'
INITIAL_FINANCE_PRESENTATION = '56b8ac7e116cecea31f1e2e323438351279b651a129c882c29111166702de4d8'
# Received main adds only unrelated C03/E01 overrides; all six finance rows match.
CURRENT_PRESENTATION = 'b4eaca33cbf799e00ecf97f3bcbb2ac601c973b4d8c73e23248dc5cd0b8db403'
FINANCE_CURRENT_PRESENTATIONS = frozenset({INITIAL_FINANCE_PRESENTATION,CURRENT_PRESENTATION})
FINANCE_METRICS = frozenset({'A03','A04','A09','A11','A12','A13'})


def finance_configuration_compatible(previous, current):
    """Recognize only the inspected transition; unknown changes reprocess."""
    if (previous.get('metric_id') not in FINANCE_METRICS
            or previous.get('requested_fiscal_year') is None):
        return False
    old,new=deepcopy(previous),deepcopy(current)
    left,right=old.get('processing_files',{}),new.get('processing_files',{})
    if (left.get(CONTROLLER)!=OLD_CONTROLLER or right.get(CONTROLLER) not in FINANCE_CURRENT_CONTROLLERS
            or left.get(SESSION)!=OLD_SESSION or SESSION in right
            or left.get(PRESENTATION)!=OLD_PRESENTATION
            or right.get(PRESENTATION) not in FINANCE_CURRENT_PRESENTATIONS
            or BRIDGE in left or BRIDGE not in right):
        return False
    left.pop(SESSION);right.pop(BRIDGE)
    for path in (CONTROLLER,PRESENTATION):left.pop(path);right.pop(path)
    return old==new


def _compatible_e01_dispatch(old, new):
    """Keep the inspected old E01 conclusion without waiving its inputs.

    The controller rechecks sources and the saved content-confirmed scope.
    Only the known store additions, unused D02 rule and comparison/control
    versions are removed here. Every other field compares normally.
    """
    if old.get('metric_id') != 'E01' or new.get('metric_id') != 'E01':
        return False
    left, right = old.get('processing_files', {}), new.get('processing_files', {})
    previous_store, current_store = left.get(STORE), right.get(STORE)
    if not (current_store in E01_AFTER_STORES and
            (previous_store == E01_BEFORE_STORE or previous_store in E01_AFTER_STORES)):
        return False
    if left.get(BRIDGE) != E01_PREVIOUS_BRIDGE or BRIDGE not in right:
        return False
    for path in (CONTROLLER, STORE, BRIDGE, D02_SOURCE):
        left.pop(path, None); right.pop(path, None)
    return old == new


def compatible_configuration(previous, current):
    """Allow inspected transitions without editing their original records."""
    if previous.get('metric_id') == 'D04' or current.get('metric_id') == 'D04':
        return False
    if finance_configuration_compatible(previous,current):
        return True
    old, new = deepcopy(previous), deepcopy(current)
    if _compatible_e01_dispatch(deepcopy(old), deepcopy(new)):
        return True
    left, right = old.get('processing_files', {}), new.get('processing_files', {})
    before = (left.get(CONTROLLER), left.get(STORE))
    after = (right.get(CONTROLLER), right.get(STORE))
    if before == BEFORE_D04 and after == AFTER_D04:
        pass  # 145a -> bdb: only D04 dependencies and dispatch were added.
    elif before in (BEFORE_D04, AFTER_D04, MAIN_C99, MAIN_F51, EXTRACTED_D04) and after in (EXTRACTED_D04, EXTRACTED_MAIN_F51):
        # f51 adds one actual B01/B03 source dependency to the controller.
        # That dependency and every other business field still compare below;
        # the known dispatcher pair alone cannot waive it.
        if BRIDGE not in right:
            return False
        if before == EXTRACTED_D04:
            if left.get(BRIDGE) != EXTRACTED_BRIDGE:
                return False
            left.pop(BRIDGE)
        elif BRIDGE in left:
            return False
        right.pop(BRIDGE)
    else:
        return False
    for path in (CONTROLLER, STORE):
        left.pop(path); right.pop(path)
    return old == new
