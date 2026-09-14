"""Application orchestration for point-in-time return/risk estimation."""

import dataclasses
import json
from collections.abc import Mapping
from dataclasses import replace
from typing import Any, cast

import numpy as np
from sqlalchemy.orm import Session

from fip.platform.decision_data.context import DecisionExecutionContext, RuntimeMode
from fip.services.data_service.models.governance import PolicyVersion
from fip.services.portfolio_service.estimation.inputs import (
    EstimationBasisInput,
    EstimationInputAssembler,
    FactorRiskCrossCheckProvider,
)
from fip.services.portfolio_service.estimation.models import (
    FINAL_BUSINESS_STATUSES,
    EstimationMethodVersion,
    EstimationParameterVersion,
)
from fip.services.portfolio_service.estimation.policy import (
    EstimationPolicy,
    EstimationValidationPolicy,
    estimation_parameter_content,
)
from fip.services.portfolio_service.estimation.repositories import (
    EstimationBasisRejection,
    EstimationResultBundle,
    EstimationRunIdentity,
    EstimationRunRepository,
    EstimationRunResult,
    EstimationStateError,
    aggregate_input_lineage_fingerprint,
)
from fip.strategy_library.estimation.covariance import estimate_covariance
from fip.strategy_library.estimation.encoding import canonical_checksum
from fip.strategy_library.estimation.returns import estimate_expected_returns
from fip.strategy_library.estimation.types import FactorRiskObservation
from fip.strategy_library.estimation.validation import (
    ValidationBundle,
    ValidationPolicy,
    ValidationResult,
    validate_bundle,
)

_FACTOR_VALIDATION_CODES = frozenset({"FACTOR_RISK_CROSS_CHECK", "NOT_COMPARABLE"})
ESTIMATION_METHOD_SPECIFICATION = {
    "returns": "HISTORICAL_MEAN_JAMES_STEIN",
    "covariance": "LEDOIT_WOLF_CONSTANT_CORRELATION",
    "formula_version": "PLAN3_D4A_GAMMA_T_V1",
    "instrument_order": "SHARE_CLASS_ID_ASC",
}


class _NumericalInputRejected(ValueError):
    """A basis cannot produce a finite, defined numerical estimate."""


class EstimationConfigurationError(ValueError):
    """The injected policy objects and persisted immutable versions disagree."""


class EstimationService:
    """Run both estimation bases within the D-9 A/B/C transaction protocol."""

    def __init__(
        self,
        session: Session,
        *,
        estimation_policy: EstimationPolicy,
        validation_policy: EstimationValidationPolicy,
        estimation_method_version_id: int,
        estimation_parameter_version_id: int,
        estimation_policy_version_id: int,
        validation_policy_version_id: int,
        adjustment_policy_version: str,
        factor_risk_provider: FactorRiskCrossCheckProvider,
        allow_experimental: bool = False,
    ) -> None:
        self._session = session
        self._estimation_policy = estimation_policy
        self._validation_policy = validation_policy
        self._estimation_method_version_id = estimation_method_version_id
        self._estimation_parameter_version_id = estimation_parameter_version_id
        self._estimation_policy_version_id = estimation_policy_version_id
        self._validation_policy_version_id = validation_policy_version_id
        self._adjustment_policy_version = adjustment_policy_version
        self._factor_risk_provider = factor_risk_provider
        self._allow_experimental = allow_experimental

    def run(
        self, context: DecisionExecutionContext, universe_snapshot_id: int
    ) -> EstimationRunResult:
        return self._run(context, universe_snapshot_id, retry_failed=False)

    def retry(
        self, context: DecisionExecutionContext, universe_snapshot_id: int
    ) -> EstimationRunResult:
        """Explicitly authorize reuse of a FAILED Run under the repository row lock."""
        return self._run(context, universe_snapshot_id, retry_failed=True)

    def _run(
        self, context: DecisionExecutionContext, universe_snapshot_id: int, *, retry_failed: bool
    ) -> EstimationRunResult:
        """Create or reproduce one immutable business Run.

        Transaction A commits the durable RUNNING marker. Transaction B rebuilds
        both independent bases and atomically persists their audit outcomes. If B
        raises, transaction C records FAILED without retaining partial results.
        """
        identity = EstimationRunIdentity(
            decision_id=context.decision_id,
            universe_snapshot_id=universe_snapshot_id,
            estimation_method_version_id=self._estimation_method_version_id,
            estimation_parameter_version_id=self._estimation_parameter_version_id,
            estimation_policy_version_id=self._estimation_policy_version_id,
            validation_policy_version_id=self._validation_policy_version_id,
            code_version=context.code_version,
        )
        repository = EstimationRunRepository(self._session)
        run_id: int | None = None
        must_mark_failed = False

        if self._session.in_transaction():
            self._session.commit()
        with self._session.begin():
            method_version, parameter_version = self._validated_versions()
            started = repository.start(identity)
            run_id = started.run_id
            if started.status == "FAILED" and retry_failed:
                started = repository.retry_failed(run_id)
            if not started.should_execute and started.status not in FINAL_BUSINESS_STATUSES:
                return EstimationRunResult(
                    run_id=run_id, status=started.status, approved_for_optimization=False,
                    input_lineage_fingerprint=None,
                )
            must_mark_failed = started.should_execute

        try:
            with self._session.begin():
                inputs = EstimationInputAssembler(
                    self._session,
                    adjustment_policy_version=self._adjustment_policy_version,
                    estimation_method_version=method_version.id,
                    estimation_parameter_version=parameter_version.id,
                    validation_policy_version=self._validation_policy_version_id,
                ).load(context, universe_snapshot_id, self._estimation_policy)
                bundles, rejections, basis_statuses = self._calculate_outcomes(context, inputs)
                basis_fingerprints = {
                    bundle.return_basis: bundle.input_fingerprint for bundle in bundles
                }
                basis_fingerprints.update(
                    {
                        rejection.return_basis: rejection.input_fingerprint
                        for rejection in rejections
                    }
                )
                fingerprint = aggregate_input_lineage_fingerprint(basis_fingerprints)
                persisted = repository.complete(
                    run_id,
                    bundles,
                    fingerprint,
                    basis_rejections=rejections,
                )
                return replace(persisted, basis_statuses=basis_statuses)
        except Exception as exc:
            if must_mark_failed:
                with self._session.begin():
                    repository.fail(run_id, _error_code(exc))
            raise

    def _validated_versions(
        self,
    ) -> tuple[EstimationMethodVersion, EstimationParameterVersion]:
        method = self._session.get(EstimationMethodVersion, self._estimation_method_version_id)
        parameters = self._session.get(
            EstimationParameterVersion, self._estimation_parameter_version_id
        )
        estimation_policy = self._session.get(PolicyVersion, self._estimation_policy_version_id)
        validation_policy = self._session.get(PolicyVersion, self._validation_policy_version_id)
        if method is None:
            raise EstimationConfigurationError("estimation method version does not exist")
        if parameters is None:
            raise EstimationConfigurationError("estimation parameter version does not exist")
        if (
            method.method_code != "PLAN3_M1"
            or method.implementation_path != "fip.strategy_library.estimation"
            or method.specification != ESTIMATION_METHOD_SPECIFICATION
        ):
            raise EstimationConfigurationError("estimation method version is not implemented")
        if parameters.parameters != estimation_parameter_content(self._estimation_policy):
            raise EstimationConfigurationError("estimation parameter version does not match policy")
        implemented_values = {
            "window_type": "ROLLING",
            "forecast_horizon": "QUARTER",
            "rebalance_frequency": "QUARTER",
            "primary_return_basis": "ABSOLUTE",
            "secondary_return_bases": ("EXCESS",),
            "return_type": "SIMPLE",
            "return_method": "HISTORICAL_MEAN_JAMES_STEIN",
            "return_shrinkage_target": "CROSS_SECTIONAL_MEAN",
            "return_shrinkage_intensity": "ANALYTIC",
            "covariance_method": "LEDOIT_WOLF_CONSTANT_CORRELATION",
            "covariance_shrinkage_target": "CONSTANT_CORRELATION",
            "covariance_shrinkage_intensity": "ANALYTIC",
            "observation_frequency": "DAILY",
            "annualization_factor": 252,
            "missing_strategy": "EXCLUDE_NO_FILL",
            "outlier_handling": "NONE",
            "numeric_scale": "ANNUALIZED",
            "covariance_ddof": 1,
            "mu_cross_section_ddof": 1,
            "downside_threshold": 0,
        }
        for field, expected in implemented_values.items():
            if getattr(self._estimation_policy, field) != expected:
                raise EstimationConfigurationError(f"unsupported estimation parameter: {field}")
        self._require_policy_version(
            estimation_policy,
            "estimation",
            self._estimation_policy.version,
            _policy_content(self._estimation_policy),
        )
        self._require_policy_version(
            validation_policy,
            "estimation_validation",
            self._validation_policy.version,
            _policy_content(self._validation_policy),
        )
        return method, parameters

    @staticmethod
    def _require_policy_version(
        row: PolicyVersion | None,
        expected_kind: str,
        expected_label: str,
        expected_content: dict[str, object],
    ) -> None:
        if row is None:
            raise EstimationConfigurationError(f"{expected_kind} policy version does not exist")
        if row.policy_kind != expected_kind or row.version_label != expected_label:
            raise EstimationConfigurationError(
                f"persisted {expected_kind} policy version does not match injected policy"
            )
        if row.content != expected_content:
            raise EstimationConfigurationError(
                f"persisted {expected_kind} policy content does not match injected policy"
            )

    def _calculate_outcomes(
        self,
        context: DecisionExecutionContext,
        inputs: tuple[EstimationBasisInput, ...],
    ) -> tuple[
        tuple[EstimationResultBundle, ...],
        tuple[EstimationBasisRejection, ...],
        dict[str, str],
    ]:
        bundles: list[EstimationResultBundle] = []
        rejections: list[EstimationBasisRejection] = []
        basis_statuses: dict[str, str] = {}
        eligibility = self._runtime_eligibility(context)
        for basis_input in inputs:
            basis_input, factor_candidates = self._with_factor_candidate_lineage(
                context, basis_input
            )
            lineage = {
                **basis_input.lineage,
                "runtime_eligibility": dataclasses.asdict(eligibility),
            }
            basis_input = replace(
                basis_input, lineage=lineage, basis_fingerprint=canonical_checksum(lineage)
            )
            if basis_input.status == "REJECTED":
                rejection = replace(self._input_rejection(basis_input), validations=(eligibility,))
                rejections.append(rejection)
                basis_statuses[basis_input.return_basis] = "REJECTED"
                continue
            try:
                bundle = self._estimate_basis(basis_input, factor_candidates)
            except _NumericalInputRejected as exc:
                lineage = {
                    **basis_input.lineage,
                    "numerical_rejection": {
                        "message": str(exc),
                        "code": "NUMERICAL_INPUT_REJECTED",
                    },
                }
                rejected_input = replace(
                    basis_input, status="REJECTED", rejection_reason="NUMERICAL_INPUT_REJECTED",
                    lineage=lineage, basis_fingerprint=canonical_checksum(lineage),
                )
                rejections.append(replace(
                    self._input_rejection(rejected_input), validations=(eligibility,)
                ))
                basis_statuses[basis_input.return_basis] = "REJECTED"
                continue
            bundle = replace(bundle, validations=bundle.validations + (eligibility,))
            bundles.append(bundle)
            basis_statuses[basis_input.return_basis] = _basis_status(bundle.validations)
        return tuple(bundles), tuple(rejections), basis_statuses

    def _runtime_eligibility(self, context: DecisionExecutionContext) -> ValidationResult:
        provisional = {
            "estimation": list(self._estimation_policy.provisional_parameters),
            "validation": list(self._validation_policy.provisional_parameters),
        }
        experimental = any(provisional.values())
        eligible = not experimental or (
            context.runtime_mode == RuntimeMode.BACKTEST and self._allow_experimental
        )
        return ValidationResult(
            "RUNTIME_ELIGIBILITY", "REJECT", "PASSED" if eligible else "FAILED",
            json.dumps({"runtime_mode": context.runtime_mode.value,
                        "allow_experimental": self._allow_experimental,
                        "provisional_parameters": provisional}, sort_keys=True),
        )

    def _estimate_basis(
        self,
        basis_input: EstimationBasisInput,
        factor_candidates: Mapping[int, tuple[FactorRiskObservation, ...]],
    ) -> EstimationResultBundle:
        # Only the pure estimators' domain/numerical failures are basis-local.
        # Provider, validation and persistence exceptions retain D-9 rollback semantics.
        try:
            returns = estimate_expected_returns(
                basis_input.matrix, self._estimation_policy.annualization_factor
            )
            covariance = estimate_covariance(
                basis_input.matrix, self._estimation_policy.annualization_factor
            )
        except (ValueError, np.linalg.LinAlgError) as exc:
            raise _NumericalInputRejected(str(exc)) from exc
        validations = self._validate_all_members(
            basis_input, returns.annualized_mu, covariance, factor_candidates
        )
        validations += _lineage_warning_results(basis_input.lineage)
        return EstimationResultBundle(
            return_basis=basis_input.return_basis,
            instrument_order=basis_input.instrument_order,
            return_estimate=returns,
            covariance_estimate=covariance,
            observation_count=len(basis_input.observation_dates),
            dropped_dates_count=len(basis_input.dropped_dates),
            excluded_instruments=basis_input.excluded_instruments,
            input_lineage=basis_input.lineage,
            input_fingerprint=basis_input.basis_fingerprint,
            validations=validations,
        )

    def _validate_all_members(
        self,
        basis_input: EstimationBasisInput,
        mu: Any,
        covariance: Any,
        factor_candidates: Mapping[int, tuple[FactorRiskObservation, ...]],
    ) -> tuple[ValidationResult, ...]:
        common_results: tuple[ValidationResult, ...] | None = None
        factor_results: list[tuple[int, ValidationResult]] = []
        for index, share_class_id in enumerate(basis_input.instrument_order):
            validation_bundle = ValidationBundle(
                matrix=basis_input.matrix,
                mu=mu,
                covariance=covariance.covariance,
                correlation=covariance.correlation,
                variance=covariance.variance,
                volatility=covariance.volatility,
                condition_number=covariance.final_condition_number,
                factor_volatility=float(covariance.volatility[index]),
                window=f"{self._estimation_policy.lookback_trading_days}D",
                observation_fingerprint=basis_input.observation_fingerprint,
                return_type=self._estimation_policy.return_type,
                ddof=self._estimation_policy.covariance_ddof,
                annualization=self._estimation_policy.annualization_factor,
            )
            member_results = validate_bundle(
                validation_bundle,
                cast(ValidationPolicy, self._validation_policy),
                factor_candidates[share_class_id],
            )
            if common_results is None:
                common_results = tuple(
                    result
                    for result in member_results
                    if result.code not in _FACTOR_VALIDATION_CODES
                )
            factor_results.append(
                (
                    share_class_id,
                    next(
                        result
                        for result in member_results
                        if result.code in _FACTOR_VALIDATION_CODES
                    ),
                )
            )
        if common_results is None:
            raise EstimationStateError("an available basis must contain at least one instrument")
        return common_results + (_aggregate_factor_results(tuple(factor_results)),)

    def _with_factor_candidate_lineage(
        self,
        context: DecisionExecutionContext,
        basis_input: EstimationBasisInput,
    ) -> tuple[
        EstimationBasisInput,
        dict[int, tuple[FactorRiskObservation, ...]],
    ]:
        candidates_by_member = {
            share_class_id: self._factor_risk_provider.load_candidates(
                share_class_id, context.decision_id
            )
            for share_class_id in basis_input.instrument_order
        }
        lineage = {
            **basis_input.lineage,
            "factor_risk_candidates": {
                str(share_class_id): [dataclasses.asdict(candidate) for candidate in candidates]
                for share_class_id, candidates in candidates_by_member.items()
            },
        }
        return (
            replace(
                basis_input,
                lineage=lineage,
                basis_fingerprint=canonical_checksum(lineage),
            ),
            candidates_by_member,
        )

    @staticmethod
    def _input_rejection(basis_input: EstimationBasisInput) -> EstimationBasisRejection:
        completeness = basis_input.lineage.get("data_completeness")
        counts = completeness if isinstance(completeness, Mapping) else {}
        return EstimationBasisRejection(
            return_basis=basis_input.return_basis,
            reason_code=basis_input.rejection_reason or "BASIS_INPUT_REJECTED",
            input_lineage=basis_input.lineage,
            input_fingerprint=basis_input.basis_fingerprint,
            observation_count=_nonnegative_int(counts.get("observation_count")),
            dropped_dates_count=len(basis_input.dropped_dates),
            excluded_instruments=basis_input.excluded_instruments,
        )


def _nonnegative_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _policy_content(
    policy: EstimationPolicy | EstimationValidationPolicy,
) -> dict[str, object]:
    serialized = json.loads(json.dumps(dataclasses.asdict(policy), default=str))
    if not isinstance(serialized, dict):
        raise EstimationConfigurationError("policy content must serialize to an object")
    return cast(dict[str, object], serialized)


def _aggregate_factor_results(
    results: tuple[tuple[int, ValidationResult], ...],
) -> ValidationResult:
    detail = json.dumps(
        [{"share_class_id": share_class_id, **dataclasses.asdict(result)}
         for share_class_id, result in results], sort_keys=True,
    )
    rejected = tuple(
        (share_class_id, result)
        for share_class_id, result in results
        if result.code == "FACTOR_RISK_CROSS_CHECK" and result.status == "FAILED"
    )
    if rejected:
        return ValidationResult(
            "FACTOR_RISK_CROSS_CHECK",
            "REJECT",
            "FAILED",
            detail,
        )
    not_comparable = tuple(
        share_class_id for share_class_id, result in results if result.code == "NOT_COMPARABLE"
    )
    if not_comparable:
        return ValidationResult(
            "NOT_COMPARABLE",
            "WARNING",
            "FAILED",
            detail,
        )
    return ValidationResult(
        "FACTOR_RISK_CROSS_CHECK",
        "REJECT",
        "PASSED",
        detail,
    )


def _lineage_warning_results(lineage: Mapping[str, object]) -> tuple[ValidationResult, ...]:
    warnings = lineage.get("warnings")
    if not isinstance(warnings, list):
        return ()
    results: list[ValidationResult] = []
    for warning in warnings:
        if not isinstance(warning, dict):
            continue
        code = warning.get("code")
        if not isinstance(code, str) or not code:
            continue
        results.append(ValidationResult(code, "WARNING", "FAILED", str(warning)))
    return tuple(results)


def _basis_status(validations: tuple[ValidationResult, ...]) -> str:
    if any(result.severity == "REJECT" and result.status == "FAILED" for result in validations):
        return "REJECTED"
    if any(result.status == "FAILED" for result in validations):
        return "COMPLETED_WITH_WARNING"
    return "COMPLETED"


def _error_code(exc: Exception) -> str:
    name = type(exc).__name__
    characters: list[str] = []
    for index, character in enumerate(name):
        if character.isupper() and index > 0 and not name[index - 1].isupper():
            characters.append("_")
        characters.append(character.upper())
    return "".join(characters)[:64]
