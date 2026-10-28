"""Offline version contracts; these tests never request a database fixture."""

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from fip.services.data_service.classification import models, policy
from fip.services.data_service.classification.rules import classify

CURRENT_PATH = Path("config/policy/classification/current.yaml")
PAUSED = ("geography", "product_structure", "market_attributes")


def legacy_snapshot(version="1.0.0"):
    result = {"status": "UNKNOWN", "value": "UNKNOWN", "candidates": [], "evidence": []}
    raw = {
        "scheme": "FIP_CLASSIFICATION_V1",
        "rule_version": version,
        "enum_version": version,
        **{dimension: deepcopy(result) for dimension in models.DIMENSIONS},
        "review_items": [],
    }
    if version == "CURRENT":
        for dimension in PAUSED:
            raw[dimension]["evaluation_state"] = "NOT_EVALUATED"
    return raw


def current_snapshot():
    raw = legacy_snapshot("CURRENT")
    raw["scheme"] = "FIP_CLASSIFICATION"
    for dimension in PAUSED:
        raw[dimension]["evaluation_state"] = "NOT_EVALUATED"
    return raw


def evidence(field="investment_strategy", value="采用量化模型"):
    return models.Evidence(
        source="OFFICIAL",
        rule_id="TAG001",
        confidence="OFFICIAL_DOCUMENT",
        classified_at=datetime(2026, 10, 27, tzinfo=UTC),
        raw_field=field,
        raw_value=value,
        payload_ref="raw:123",
        locator="p.2",
    )


@pytest.mark.parametrize("version", ["1.0.0", "2.0.0"])
def test_legacy_json_keeps_absent_metadata_and_original_values(version):
    raw = legacy_snapshot(version)
    raw["strategy"].update(status="CONFIRMED", value="QUANTITATIVE")
    snapshot = models.ClassificationSnapshot.model_validate(raw)
    assert snapshot.strategy.value == "QUANTITATIVE"
    assert snapshot.strategy_tag_results is None
    assert snapshot.strategy_tags is None
    assert snapshot.geography.evaluation_state is None
    assert "rule_version" not in snapshot.to_dict()
    assert "enum_version" not in snapshot.to_dict()


def test_default_policy_is_the_single_current_classification_policy():
    loaded = policy.load_policy()

    assert loaded.scheme == "FIP_CLASSIFICATION"
    assert loaded.active_dimensions == ("asset_class", "strategy")
    assert loaded.strategy_tag_catalog == ("QUANTITATIVE",)
    assert classify([], classified_at=datetime.now(UTC)).scheme == "FIP_CLASSIFICATION"


def test_current_policy_separates_tags_from_core_dimensions():
    loaded = policy.load_policy()
    assert loaded == policy.load_policy(CURRENT_PATH)
    assert loaded.scheme == "FIP_CLASSIFICATION"
    assert loaded.scheme == "FIP_CLASSIFICATION"
    assert loaded.active_dimensions == ("asset_class", "strategy")
    assert loaded.paused_dimensions == PAUSED
    assert set(loaded.catalog) == set(models.DIMENSIONS)
    assert loaded.catalog["strategy"] == (
        "ACTIVE",
        "PASSIVE_INDEX",
        "ENHANCED_INDEX",
        "TARGET_DATE",
        "TARGET_RISK",
        "UNKNOWN",
    )
    assert loaded.strategy_tag_catalog == ("QUANTITATIVE",)
    assert "QUANTITATIVE" not in loaded.strategy_priority
    original = policy.load_policy()
    assert original.formal_types.items() <= loaded.formal_types.items()
    for dimension in ("asset_class", *PAUSED):
        assert loaded.catalog[dimension] == original.catalog[dimension]


@pytest.mark.parametrize(
    "mutation",
    [
        {"active_dimensions": ("asset_class", "strategy", "geography")},
        {"paused_dimensions": ("geography", "product_structure")},
        {"strategy_tag_catalog": ("QUANTITATIVE", "QUANTITATIVE")},
        {"strategy_tag_catalog": ("UNKNOWN",)},
        {"strategy_tag_catalog": ("QUANTITATIVE", "ACTIVE")},
        {"strategy_priority": ("ACTIVE",)},
        {"scheme": "OTHER_SCHEME"},
    ],
)
def test_invalid_current_policy_metadata_is_rejected(mutation):
    raw = policy.load_policy(CURRENT_PATH).model_dump()
    raw.update(mutation)
    with pytest.raises(ValidationError):
        policy.ClassificationPolicy.model_validate(raw)


@pytest.mark.parametrize("invalid", ["QUANTITATIVE", "FUTURE_STRATEGY"])
def test_invalid_current_main_strategy_catalog_is_rejected(invalid):
    raw = policy.load_policy(CURRENT_PATH).model_dump()
    raw["catalog"]["strategy"] += (invalid,)
    raw["strategy_priority"] += (invalid,)
    with pytest.raises(ValidationError):
        policy.ClassificationPolicy.model_validate(raw)


@pytest.mark.parametrize("dimension", ["asset_class", *PAUSED])
def test_current_rejects_unregistered_dimension_catalog_values(dimension):
    raw = policy.load_policy(CURRENT_PATH).model_dump()
    raw["catalog"][dimension] += ("INCOMPATIBLE_OLD_CODE",)
    with pytest.raises(ValidationError):
        policy.ClassificationPolicy.model_validate(raw)


@pytest.mark.parametrize("dimension", models.DIMENSIONS)
def test_current_snapshot_rejects_values_outside_current_catalog(dimension):
    raw = current_snapshot()
    raw[dimension].update(status="CONFIRMED", value="INCOMPATIBLE_OLD_CODE")
    with pytest.raises(ValidationError):
        models.ClassificationSnapshot.model_validate(raw)


def test_paused_carry_requires_a_source_revision():
    with pytest.raises(ValidationError):
        models.DimensionResult(
            status="CONFIRMED",
            value="US",
            evaluation_state="PAUSED",
            evidence=(evidence(),),
        )


@pytest.mark.parametrize("status", ["CANDIDATE", "CONFLICT"])
def test_joint_rule_keeps_candidate_and_conflict_status(status):
    joint = models.Evidence.model_validate(
        {
            **evidence().model_dump(),
            "rule_id": "STR030",
            "assertion_status": status,
            "required_observations": [evidence("formal_type", "混合型"), evidence()],
            "rationale": "All independent inputs retained",
        }
    )
    assert joint.assertion_status == status
    assert len(joint.required_observations) == 2


@pytest.mark.parametrize("state", ["NOT_EVALUATED", "EVALUATED"])
def test_tag_evaluation_is_explicit_even_when_no_confirmed_tags(state):
    raw = current_snapshot()
    raw["strategy_tag_results"] = {"QUANTITATIVE": {"status": "UNKNOWN", "evaluation_state": state}}
    snapshot = models.ClassificationSnapshot.model_validate(raw)
    assert snapshot.strategy_tags == ()
    assert snapshot.strategy_tag_results["QUANTITATIVE"].evaluation_state == state
    assert models.ClassificationSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot


@pytest.mark.parametrize("status", ["CONFIRMED", "CANDIDATE", "CONFLICT", "UNKNOWN"])
def test_tag_projection_includes_only_confirmed_evidence_results(status):
    raw = current_snapshot()
    raw["strategy_tag_results"] = {
        "QUANTITATIVE": {
            "status": status,
            "value": "QUANTITATIVE" if status == "CONFIRMED" else "UNKNOWN",
            "candidates": ["QUANTITATIVE"] if status in {"CANDIDATE", "CONFLICT"} else [],
            "evidence": [evidence()],
            "evaluation_state": "EVALUATED",
        }
    }
    snapshot = models.ClassificationSnapshot.model_validate(raw)
    assert snapshot.strategy_tags == (("QUANTITATIVE",) if status == "CONFIRMED" else ())
    assert snapshot.strategy.status == "UNKNOWN"
    assert snapshot.strategy_tag_results["QUANTITATIVE"].evidence[0].payload_ref == "raw:123"


def test_snapshot_rejects_unbacked_confirmed_tag_projection():
    raw = current_snapshot()
    raw["strategy_tags"] = ["QUANTITATIVE"]
    with pytest.raises(ValidationError):
        models.ClassificationSnapshot.model_validate(raw)


def test_paused_carry_and_incompatible_history_reference_roundtrip():
    raw = current_snapshot()
    raw["geography"].update(
        status="CONFIRMED",
        value="US",
        evidence=[evidence("geography", "US")],
        evaluation_state="PAUSED",
        carried_from_revision_id=42,
    )
    raw["product_structure"].update(
        evaluation_state="NOT_EVALUATED",
        carried_from_revision_id=41,
    )
    raw["market_attributes"].update(evaluation_state="NOT_EVALUATED")
    snapshot = models.ClassificationSnapshot.model_validate(raw)
    assert snapshot.geography.value == "US"
    assert not snapshot.geography.is_evaluated
    assert not snapshot.product_structure.is_evaluated
    assert not snapshot.market_attributes.is_evaluated
    assert snapshot.product_structure.value == "UNKNOWN"
    assert snapshot.product_structure.carried_from_revision_id == 41
    assert models.ClassificationSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot


@pytest.mark.parametrize("dimension", PAUSED)
def test_current_paused_dimensions_cannot_claim_current_evaluation(dimension):
    raw = current_snapshot()
    raw[dimension]["evaluation_state"] = "EVALUATED"
    with pytest.raises(ValidationError):
        models.ClassificationSnapshot.model_validate(raw)


@pytest.mark.parametrize("dimension", PAUSED)
@pytest.mark.parametrize("missing", ["omitted", "null"])
def test_current_paused_dimensions_require_explicit_evaluation_state(dimension, missing):
    raw = current_snapshot()
    if missing == "omitted":
        raw[dimension].pop("evaluation_state")
    else:
        raw[dimension]["evaluation_state"] = None
    with pytest.raises(ValidationError):
        models.ClassificationSnapshot.model_validate(raw)


def test_historical_rule_labels_are_ignored_when_loading_a_snapshot():
    raw = current_snapshot()
    raw.update(rule_version="old", enum_version="old")
    snapshot = models.ClassificationSnapshot.model_validate(raw)
    assert "rule_version" not in snapshot.to_dict()
    assert "enum_version" not in snapshot.to_dict()


def test_current_catalog_rejects_quantitative_as_a_main_strategy():
    raw = current_snapshot()
    raw["strategy"].update(status="CONFIRMED", value="QUANTITATIVE", evidence=[evidence()])
    with pytest.raises(ValidationError):
        models.ClassificationSnapshot.model_validate(raw)


@pytest.mark.parametrize("status", ["CONFIRMED", "CANDIDATE", "CONFLICT"])
def test_tag_assertions_require_evidence_and_unknown_remains_available(status):
    raw = current_snapshot()
    raw["strategy_tag_results"] = {
        "QUANTITATIVE": {
            "status": status,
            "value": "QUANTITATIVE" if status == "CONFIRMED" else "UNKNOWN",
            "candidates": ["QUANTITATIVE"] if status in {"CANDIDATE", "CONFLICT"} else [],
            "evaluation_state": "EVALUATED",
        }
    }
    with pytest.raises(ValidationError):
        models.ClassificationSnapshot.model_validate(raw)
    raw["strategy_tag_results"]["QUANTITATIVE"].update(
        status="UNKNOWN", value="UNKNOWN", candidates=[]
    )
    snapshot = models.ClassificationSnapshot.model_validate(raw)
    assert snapshot.strategy_tags == ()
    assert snapshot.strategy_tag_results["QUANTITATIVE"].status == "UNKNOWN"


def test_snapshot_tag_results_cannot_mutate_after_validation():
    raw = current_snapshot()
    raw["strategy_tag_results"] = {
        "QUANTITATIVE": {
            "status": "CONFIRMED",
            "value": "QUANTITATIVE",
            "evidence": [evidence()],
            "evaluation_state": "EVALUATED",
        }
    }
    snapshot = models.ClassificationSnapshot.model_validate(raw)
    before = snapshot.model_dump_json()
    with pytest.raises(TypeError):
        snapshot.strategy_tag_results["QUANTITATIVE"] = models.StrategyTagResult(status="UNKNOWN")
    with pytest.raises(TypeError):
        del snapshot.strategy_tag_results["QUANTITATIVE"]
    raw["strategy_tag_results"].clear()
    exported = snapshot.to_dict()
    exported["strategy_tag_results"].clear()
    assert snapshot.strategy_tags == ("QUANTITATIVE",)
    assert snapshot.model_dump_json() == before
    assert models.ClassificationSnapshot.model_validate_json(before) == snapshot


def test_unevaluated_placeholder_cannot_contain_facts():
    with pytest.raises(ValidationError):
        models.DimensionResult(
            status="CONFIRMED",
            value="US",
            evidence=(evidence(),),
            evaluation_state="NOT_EVALUATED",
        )


def test_joint_rule_keeps_all_required_inputs_and_conflict_rationale():
    inputs = (evidence("formal_type", "混合型"), evidence("investment_strategy", "主动管理"))
    joint = evidence().model_copy(update={})
    joint = models.Evidence.model_validate(
        {
            **joint.model_dump(),
            "rule_id": "STR030",
            "assertion_status": "CONFLICT",
            "rationale": "Reliable explicit passive declaration contradicts active mechanism",
            "required_observations": inputs,
        }
    )
    assert joint.rule_id == "STR030"
    assert joint.assertion_status == "CONFLICT"
    assert joint.required_observations == inputs
    assert joint.rationale
    assert models.Evidence.model_validate_json(joint.model_dump_json()) == joint
