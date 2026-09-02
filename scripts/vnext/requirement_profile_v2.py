"""Versioned extension proving policy evolution without editing the V1 engine.

No V2 Requirement or R5 execution is activated by this module. The extension
only supplies the typed product-meaning Decision needed to resolve a pending
policy; the V1 safety engine and all of its bounds remain unchanged.
"""

from pathlib import Path
from typing import Callable, Mapping

from . import requirement_profile_v1 as v1


PROFILE_REQUIREMENT_GENERATION = "PROFILE_DRIVEN_V2"
PROFILE_SEMANTIC_VERSION = "2"


def _metric_product_semantics(*, choice: Mapping[str, object]) -> dict:
    v1._exact_fields(
        value=choice,
        expected={"kind", "b06_economic_meaning", "b13_economic_meaning",},
        label="Metric product semantics",
    )
    for field in ("b06_economic_meaning", "b13_economic_meaning"):
        v1._text(value=choice[field], label=field)
    return dict(choice)


def load_profile_requirement_snapshot(
    *, snapshot_dir: Path, parent_loader: Callable[..., Mapping[str, object]],
) -> dict:
    """Load V2 using retained V1 machinery plus one closed typed extension."""
    return v1._load_profile_requirement_snapshot(
        snapshot_dir=snapshot_dir,
        parent_loader=parent_loader,
        generation=PROFILE_REQUIREMENT_GENERATION,
        semantic_version=PROFILE_SEMANTIC_VERSION,
        engine_file=Path(__file__),
        engine_dependencies=(Path(v1.__file__),),
        evaluators={
            **v1.INVARIANT_EVALUATORS,
            "METRIC_PRODUCT_SEMANTICS": _metric_product_semantics,
        },
    )
