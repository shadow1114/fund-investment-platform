import datetime as dt

import pytest

from fip.services.data_service.models.governance import DataProvider, DataProviderDataset
from fip.services.data_service.models.raw import CanonicalRaw, RawPayload

pytestmark = pytest.mark.integration


@pytest.fixture()
def dataset(db_session):
    provider = (
        db_session.query(DataProvider)
        .filter_by(provider_code="AKSHARE")
        .one_or_none()
    )
    if provider is None:
        provider = DataProvider(provider_code="AKSHARE", display_name="AKShare")
        db_session.add(provider)
        db_session.flush()
    ds = DataProviderDataset(
        provider_id=provider.id,
        dataset_code="fund_open_fund_info_em.单位净值走势",
        adapter_version="1",
        library_version="1.18.94",
    )
    db_session.add(ds)
    db_session.flush()
    return ds


def test_one_payload_can_be_parsed_multiple_times(db_session, dataset):
    """1:N 是关键 —— Adapter 修 bug 后可重解析而不重新抓取。"""
    payload = RawPayload(
        dataset_id=dataset.id,
        request_params={"symbol": "000001"},
        payload=b"PAR1-fake-parquet",
        row_count=3,
        library_version="1.18.94",
        published_at=None,
        provider_available_at=None,
        ingested_at=dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC),
    )
    db_session.add(payload)
    db_session.flush()
    db_session.add_all([
        CanonicalRaw(raw_payload_id=payload.id, adapter_version="1", parsed_row_count=3),
        CanonicalRaw(raw_payload_id=payload.id, adapter_version="2", parsed_row_count=3),
    ])
    db_session.flush()
    assert db_session.query(CanonicalRaw).filter_by(raw_payload_id=payload.id).count() == 2


def test_payload_records_library_version(db_session, dataset):
    """AKShare 版本必须随每行 payload 记录，否则无法定位错映射的来源。"""
    payload = RawPayload(
        dataset_id=dataset.id, request_params={}, payload=b"x", row_count=0,
        library_version="1.18.94",
        ingested_at=dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC),
    )
    db_session.add(payload)
    db_session.flush()
    assert payload.library_version == "1.18.94"
