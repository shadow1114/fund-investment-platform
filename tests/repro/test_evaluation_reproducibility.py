import pytest

from tests.integration.test_evaluation_pipeline import (
    test_assembled_pipeline_persists_the_complete_evaluation_chain as run_real_pipeline,
)

pytestmark = pytest.mark.integration


def test_real_evaluation_pipeline_is_reproducible(db_session):
    run_real_pipeline(db_session)