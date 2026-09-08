import pytest

from fip.services.data_service.batch import BatchItemStatus, FundIngestSubject
from fip.services.data_service.ingest import IngestService
from fip.services.data_service.models.fund import Fund
from fip.services.data_service.normalization.adjusted_nav import AdjustedNavUnavailable

pytestmark = pytest.mark.integration


def test_one_unavailable_subject_rolls_back_only_itself_and_batch_continues(
    db_session, monkeypatch
):
    service = IngestService(db_session, object(), disclosure_lag_days=1)  # type: ignore[arg-type]

    def ingest_nav(share_class_id: int, _provider_fund_id: str) -> int:
        db_session.add(
            Fund(
                fund_code=f"P-BATCH-{share_class_id}",
                product_name=f"batch {share_class_id}",
                grouping_status="CONFIRMED",
            )
        )
        db_session.flush()
        return 1

    def ingest_distributions(_share_class_id: int, _provider_fund_id: str) -> int:
        return 0

    def rebuild(share_class_id: int, _decision_at) -> int:
        if share_class_id == 2:
            raise AdjustedNavUnavailable("broken chain")
        return 1

    monkeypatch.setattr(service, "ingest_nav", ingest_nav)
    monkeypatch.setattr(service, "ingest_distributions", ingest_distributions)
    monkeypatch.setattr(service, "rebuild_adjusted_nav", rebuild)

    result = service.ingest_nav_batch(
        [
            FundIngestSubject(1, "P-1"),
            FundIngestSubject(2, "P-2"),
            FundIngestSubject(3, "P-3"),
        ]
    )

    assert [item.status for item in result.items] == [
        BatchItemStatus.SUCCESS,
        BatchItemStatus.UNAVAILABLE,
        BatchItemStatus.SUCCESS,
    ]
    assert {
        fund.fund_code for fund in db_session.query(Fund).order_by(Fund.id).all()
    } == {"P-BATCH-1", "P-BATCH-3"}
