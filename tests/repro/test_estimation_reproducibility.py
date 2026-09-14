import numpy as np
import pytest
from sqlalchemy import func, select

from fip.services.portfolio_service.estimation import ApprovedEstimationProvider
from fip.services.portfolio_service.estimation.models import (
    CovarianceEstimate,
    EstimationRun,
    EstimationValidationResult,
)
from tests.integration.test_estimation_service import seed_estimation_service

pytestmark = pytest.mark.integration


def test_real_pit_estimation_is_reproducible_and_idempotent(db_session):
    service, context, snapshot_id, expected_order = seed_estimation_service(
        db_session, decision_id="repro-estimation"
    )

    first_result = service.run(context, snapshot_id)
    first_approved = ApprovedEstimationProvider(db_session).load(first_result.run_id)
    first_mu = first_approved.mu.copy()
    first_sigma = first_approved.Sigma.copy()
    first_rows = tuple(
        (
            row.return_basis,
            tuple(row.covariance_payload["instrument_order"]),
            row.covariance_payload["checksum"],
            row.correlation_payload["checksum"],
            tuple((item["share_class_id"], item["reason"]) for item in row.excluded_instruments),
        )
        for row in db_session.scalars(
            select(CovarianceEstimate)
            .where(CovarianceEstimate.run_id == first_result.run_id)
            .order_by(CovarianceEstimate.return_basis)
        )
    )
    first_rejections = tuple(
        (
            row.return_basis,
            tuple(row.detail["input_lineage"]["instrument_order"]),
            row.detail["input_fingerprint"],
            tuple(
                (item["share_class_id"], item["reason"])
                for item in row.detail["excluded_instruments"]
            ),
        )
        for row in db_session.scalars(
            select(EstimationValidationResult)
            .where(
                EstimationValidationResult.run_id == first_result.run_id,
                EstimationValidationResult.code == "BASIS_INPUT_REJECTED",
            )
            .order_by(EstimationValidationResult.return_basis)
        )
    )

    second_result = service.run(context, snapshot_id)
    second_approved = ApprovedEstimationProvider(db_session).load(second_result.run_id)
    second_rows = tuple(
        (
            row.return_basis,
            tuple(row.covariance_payload["instrument_order"]),
            row.covariance_payload["checksum"],
            row.correlation_payload["checksum"],
            tuple((item["share_class_id"], item["reason"]) for item in row.excluded_instruments),
        )
        for row in db_session.scalars(
            select(CovarianceEstimate)
            .where(CovarianceEstimate.run_id == second_result.run_id)
            .order_by(CovarianceEstimate.return_basis)
        )
    )
    second_rejections = tuple(
        (
            row.return_basis,
            tuple(row.detail["input_lineage"]["instrument_order"]),
            row.detail["input_fingerprint"],
            tuple(
                (item["share_class_id"], item["reason"])
                for item in row.detail["excluded_instruments"]
            ),
        )
        for row in db_session.scalars(
            select(EstimationValidationResult)
            .where(
                EstimationValidationResult.run_id == second_result.run_id,
                EstimationValidationResult.code == "BASIS_INPUT_REJECTED",
            )
            .order_by(EstimationValidationResult.return_basis)
        )
    )

    assert db_session.scalar(select(func.count()).select_from(EstimationRun)) == 1
    assert second_result.run_id == first_result.run_id
    assert second_result.status == first_result.status
    assert second_result.basis_statuses == first_result.basis_statuses
    assert {row[0] for row in first_rows} == {"ABSOLUTE", "EXCESS"}
    assert first_rejections == ()
    assert second_approved.instrument_order == first_approved.instrument_order == expected_order
    assert first_rows == second_rows
    assert first_rejections == second_rejections
    assert np.max(np.abs(first_mu - second_approved.mu)) <= 1.0e-10
    assert np.max(np.abs(first_sigma - second_approved.Sigma)) <= 1.0e-10
