import datetime as dt

import pandas as pd
import pytest

from fip.services.data_service.adapters.akshare.client import (
    AkShareContractError,
    AkShareSourceAdapter,
)
from fip.services.data_service.grouping import GroupingStatus, split_share_class_name


def test_name_is_only_candidate():
    assert split_share_class_name('测试混合A').status == GroupingStatus.UNCONFIRMED


def test_overview_contract_retains_raw_on_drift():
    adapter = AkShareSourceAdapter(
        caller=lambda *a, **kw: pd.DataFrame({'changed': ['x']}),
        clock=lambda: dt.datetime.now(dt.UTC),
    )
    with pytest.raises(AkShareContractError) as error:
        adapter.fetch('fund_overview', symbol='000001')
    assert error.value.record.payload
