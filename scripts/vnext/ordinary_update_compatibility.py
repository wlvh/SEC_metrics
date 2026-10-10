"""Finite compatibility for inspected D04-only dispatcher changes.

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


def compatible_configuration(previous, current):
    """Allow two known transitions without editing their original records."""
    if previous.get('metric_id') == 'D04' or current.get('metric_id') == 'D04':
        return False
    old, new = deepcopy(previous), deepcopy(current)
    left, right = old.get('processing_files', {}), new.get('processing_files', {})
    before = (left.get(CONTROLLER), left.get(STORE))
    after = (right.get(CONTROLLER), right.get(STORE))
    if before == BEFORE_D04 and after == AFTER_D04:
        pass  # 145a -> bdb: only D04 dependencies and dispatch were added.
    elif before in (BEFORE_D04, AFTER_D04, MAIN_C99) and after == EXTRACTED_D04:
        # Existing business dependencies still compare below. For example,
        # the actual revenue changes between 145a and c99 cannot pass here.
        if BRIDGE in left or BRIDGE not in right:
            return False
        right.pop(BRIDGE)
    else:
        return False
    for path in (CONTROLLER, STORE):
        left.pop(path); right.pop(path)
    return old == new
