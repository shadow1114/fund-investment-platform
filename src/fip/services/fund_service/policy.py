import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.platform.config.loader import load_config_file
from fip.platform.config.models import ParameterStatus
from fip.platform.decision_data.context import RuntimeMode
from fip.services.data_service.models.governance import PolicyVersion


class PolicyVersionConflict(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class EvaluationPolicy:
    version: str
    minimum_peer_group_size: int
    mar: Decimal
    profile_weights: Mapping[str, Mapping[str, Decimal]]
    beta_target_ranges: Mapping[str, tuple[Decimal, Decimal]]
    tracking_error_rules: Mapping[str, str]
    minimum_scoring_factors: int
    minimum_data_completeness: Decimal


@dataclass(frozen=True, slots=True)
class ValidationPolicy:
    version: str
    ic_mean_min: Decimal
    icir_abs_min: Decimal
    min_cross_sections: int
    min_names_per_cross_section: int
    ic_std_ddof: int
    forward_horizon_days: int
    redundancy_threshold: Decimal
    recent_lookback_days: int
    require_both_segments: bool


ProfileWeights = Mapping[str, Mapping[str, Decimal]]
BetaTargetRanges = Mapping[str, tuple[Decimal, Decimal]]
TrackingErrorRules = Mapping[str, str]
_PROFILES = ("active_equity", "passive_equity", "bond", "hybrid")


def load_evaluation_policy(path: Path, runtime_mode: RuntimeMode) -> EvaluationPolicy:
    config = load_config_file(path, runtime_mode)
    for parameter in config.parameters.values():
        if parameter.status is not ParameterStatus.DECIDED:
            raise ValueError(f"undecided evaluation parameter: {parameter.path}")

    def get(parameter_path: str) -> Any:
        return config.get(parameter_path)

    weights = {
        profile: {
            key.rsplit(".", 1)[-1]: Decimal(str(parameter.value))
            for key, parameter in config.parameters.items()
            if key.startswith(f"scoring.{profile}.") and key.rsplit(".", 1)[-1] != "r_squared"
        }
        for profile in _PROFILES
    }
    if any(sum(values.values(), Decimal(0)) != Decimal(1) for values in weights.values()):
        raise ValueError("each scoring profile weights must sum to 1")
    ranges: dict[str, tuple[Decimal, Decimal]] = {}
    for profile in _PROFILES:
        values = tuple(
            Decimal(str(item)) for item in get(f"factor_normalization.beta_target_range.{profile}")
        )
        if len(values) != 2:
            raise ValueError(f"beta target range for {profile} must contain two values")
        ranges[profile] = cast(tuple[Decimal, Decimal], values)
    return EvaluationPolicy(
        version=path.stem,
        minimum_peer_group_size=int(get("peer_group.minimum_effective_sample")),
        mar=(Decimal(0) if get("mar.policy") == "ZERO" else Decimal(str(get("mar.policy")))),
        profile_weights=weights,
        beta_target_ranges=ranges,
        tracking_error_rules={
            profile: str(get(f"factor_normalization.tracking_error.{profile}"))
            for profile in _PROFILES
        },
        minimum_scoring_factors=int(get("scoring.minimum_weighted_metrics")),
        minimum_data_completeness=Decimal(str(get("scoring.minimum_data_completeness"))),
    )


def load_validation_policy(path: Path, runtime_mode: RuntimeMode) -> ValidationPolicy:
    config = load_config_file(path, runtime_mode)
    return ValidationPolicy(
        version=path.stem,
        ic_mean_min=Decimal(str(config.get("effectiveness.ic_mean_min"))),
        icir_abs_min=Decimal(str(config.get("effectiveness.icir_abs_min"))),
        min_cross_sections=int(config.get("effectiveness.min_cross_sections")),
        min_names_per_cross_section=int(
            config.get("effectiveness.min_names_per_cross_section")
        ),
        ic_std_ddof=int(config.get("effectiveness.ic_std_ddof")),
        forward_horizon_days=int(config.get("effectiveness.forward_horizon_days")),
        redundancy_threshold=Decimal(
            str(config.get("effectiveness.redundancy_threshold"))
        ),
        recent_lookback_days=int(config.get("segments.recent_lookback_days")),
        require_both_segments=bool(config.get("segments.require_both")),
    )


def _content(policy: EvaluationPolicy | ValidationPolicy) -> dict[str, object]:
    return cast(dict[str, object], json.loads(json.dumps(asdict(policy), default=str)))


def persist_policy_version(session: Session, policy: EvaluationPolicy) -> int:
    content = _content(policy)
    row = session.execute(
        select(PolicyVersion).where(
            PolicyVersion.policy_kind == "evaluation",
            PolicyVersion.version_label == policy.version,
        )
    ).scalar_one_or_none()
    if row is None:
        row = PolicyVersion(policy_kind="evaluation", version_label=policy.version, content=content)
        session.add(row)
        session.flush()
        return row.id
    if row.content != content:
        raise PolicyVersionConflict(
            f"evaluation policy {policy.version} already has different content"
        )
    return row.id


def persist_validation_policy_version(session: Session, policy: ValidationPolicy) -> int:
    content = _content(policy)
    row = session.execute(
        select(PolicyVersion).where(
            PolicyVersion.policy_kind == "validation",
            PolicyVersion.version_label == policy.version,
        )
    ).scalar_one_or_none()
    if row is None:
        row = PolicyVersion(policy_kind="validation", version_label=policy.version, content=content)
        session.add(row)
        session.flush()
        return row.id
    if row.content != content:
        raise PolicyVersionConflict(
            f"validation policy {policy.version} already has different content"
        )
    return row.id
