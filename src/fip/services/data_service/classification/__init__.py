from .legacy import LegacyProjection, project_legacy
from .models import DIMENSIONS, ClassificationSnapshot, DimensionResult, Evidence
from .rules import CATALOG, classify, normalize_evidence

__all__ = [
    "LegacyProjection",
    "project_legacy",
    "CATALOG",
    "DIMENSIONS",
    "ClassificationSnapshot",
    "DimensionResult",
    "Evidence",
    "classify",
    "normalize_evidence",
]
