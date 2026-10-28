from .legacy import LegacyProjection, project_legacy
from .models import DIMENSIONS, ClassificationSnapshot, DimensionResult, Evidence, StrategyTagResult
from .policy import ClassificationPolicy, load_policy
from .rules import CATALOG, classify, normalize_evidence

__all__ = [
    "LegacyProjection",
    "project_legacy",
    "CATALOG",
    "DIMENSIONS",
    "ClassificationSnapshot",
    "DimensionResult",
    "Evidence",
    "StrategyTagResult",
    "ClassificationPolicy",
    "load_policy",
    "classify",
    "normalize_evidence",
]
