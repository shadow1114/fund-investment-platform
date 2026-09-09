import json
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


class EstimationPolicyVersionConflict(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class EstimationPolicy:
    version: str
    lookback_trading_days: int
    window_type: str
    forecast_horizon: str
    rebalance_frequency: str
    primary_return_basis: str
    secondary_return_bases: tuple[str, ...]
    return_type: str
    return_method: str
    return_shrinkage_target: str
    return_shrinkage_intensity: str
    covariance_method: str
    covariance_shrinkage_target: str
    covariance_shrinkage_intensity: str
    observation_frequency: str
    annualization_factor: int
    missing_strategy: str
    outlier_handling: str
    minimum_t_over_n: int
    warning_t_over_n: int
    downside_threshold: Decimal
    provisional_parameters: tuple[str, ...]


def load_estimation_policy(path: Path, runtime_mode: RuntimeMode) -> EstimationPolicy:
    config = load_config_file(path, runtime_mode)
    provisional = tuple(
        sorted(
            parameter.path
            for parameter in config.parameters.values()
            if parameter.status is ParameterStatus.PROVISIONAL
        )
    )
    if runtime_mode is RuntimeMode.LIVE and provisional:
        raise ValueError(
            "LIVE estimation rejects provisional parameters: " + ", ".join(provisional)
        )

    def get(parameter_path: str) -> Any:
        return config.get(parameter_path)

    secondary_bases = tuple(str(value) for value in get("returns.secondary_bases"))
    policy = EstimationPolicy(
        version=path.stem,
        lookback_trading_days=int(get("window.lookback_trading_days")),
        window_type=str(get("window.type")),
        forecast_horizon=str(get("horizon.forecast")),
        rebalance_frequency=str(get("horizon.rebalance_frequency")),
        primary_return_basis=str(get("returns.primary_basis")),
        secondary_return_bases=secondary_bases,
        return_type=str(get("returns.type")),
        return_method=str(get("returns.method")),
        return_shrinkage_target=str(get("returns.shrinkage_target")),
        return_shrinkage_intensity=str(get("returns.shrinkage_intensity")),
        covariance_method=str(get("covariance.method")),
        covariance_shrinkage_target=str(get("covariance.shrinkage_target")),
        covariance_shrinkage_intensity=str(get("covariance.shrinkage_intensity")),
        observation_frequency=str(get("observations.frequency")),
        annualization_factor=int(get("observations.annualization_factor")),
        missing_strategy=str(get("observations.missing_strategy")),
        outlier_handling=str(get("observations.outlier_handling")),
        minimum_t_over_n=int(get("observations.minimum_t_over_n")),
        warning_t_over_n=int(get("observations.warning_t_over_n")),
        downside_threshold=Decimal(str(get("risk.downside_threshold"))),
        provisional_parameters=provisional,
    )
    _validate(policy)
    return policy


def _validate(policy: EstimationPolicy) -> None:
    if policy.lookback_trading_days <= 0:
        raise ValueError("lookback_trading_days must be positive")
    if policy.forecast_horizon != policy.rebalance_frequency:
        raise ValueError("forecast horizon must equal rebalance frequency")
    if policy.primary_return_basis != "ABSOLUTE":
        raise ValueError("Plan-3 primary return basis must be ABSOLUTE")
    if "EXCESS" not in policy.secondary_return_bases:
        raise ValueError("Plan-3 must retain EXCESS as a secondary return basis")
    if policy.return_type != "SIMPLE":
        raise ValueError("Plan-3 requires SIMPLE returns")
    if policy.annualization_factor <= 0:
        raise ValueError("annualization_factor must be positive")
    if policy.minimum_t_over_n < 1:
        raise ValueError("minimum_t_over_n must be positive")
    if policy.warning_t_over_n < policy.minimum_t_over_n:
        raise ValueError("warning_t_over_n must not be below minimum_t_over_n")


def persist_estimation_policy_version(session: Session, policy: EstimationPolicy) -> int:
    content = cast(dict[str, object], json.loads(json.dumps(asdict(policy), default=str)))
    row = session.execute(
        select(PolicyVersion).where(
            PolicyVersion.policy_kind == "estimation",
            PolicyVersion.version_label == policy.version,
        )
    ).scalar_one_or_none()
    if row is None:
        row = PolicyVersion(
            policy_kind="estimation",
            version_label=policy.version,
            content=content,
        )
        session.add(row)
        session.flush()
        return row.id
    if row.content != content:
        raise EstimationPolicyVersionConflict(
            f"estimation policy {policy.version} already has different content"
        )
    return row.id