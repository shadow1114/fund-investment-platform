"""Offline version contracts; these tests never request a database fixture."""

import hashlib
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from fip.services.data_service.classification import models, policy
from fip.services.data_service.classification.rules import classify

V1_PATH = Path("config/policy/classification/v1.yaml")
V3_PATH = Path("config/policy/classification/v3.yaml")
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
    if version == "3.0.0":
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
    assert snapshot.to_dict() == raw


def test_v1_policy_bytes_and_runtime_default_are_unchanged():
    assert hashlib.sha256(V1_PATH.read_bytes()).hexdigest() == (
        "73373afd0c7af81e8251ca3bb729e974876481d72c79ebc45829aec312633170"
    )
    assert policy.load_policy().rule_version == "1.0.0"
    assert classify([], classified_at=datetime.now(UTC)).rule_version == "1.0.0"


def test_v3_registered_loading_separates_tags_from_core_dimensions():
    loaded = policy.load_policy(rule_version="3.0.0", enum_version="3.0.0")
    assert loaded == policy.load_policy(V3_PATH)
    assert loaded.scheme == "FIP_CLASSIFICATION_V1"
    assert loaded.rule_version == loaded.enum_version == "3.0.0"
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


def test_unregistered_version_pair_is_rejected():
    with pytest.raises(ValueError, match="Unsupported classification policy version"):
        policy.load_policy(rule_version="3.0.0", enum_version="1.0.0")


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
def test_invalid_v3_policy_metadata_is_rejected(mutation):
    raw = policy.load_policy(V3_PATH).model_dump()
    raw.update(mutation)
    with pytest.raises(ValidationError):
        policy.ClassificationPolicy.model_validate(raw)


@pytest.mark.parametrize("invalid", ["QUANTITATIVE", "FUTURE_STRATEGY"])
def test_invalid_v3_main_strategy_catalog_is_rejected(invalid):
    raw = policy.load_policy(V3_PATH).model_dump()
    raw["catalog"]["strategy"] += (invalid,)
    raw["strategy_priority"] += (invalid,)
    with pytest.raises(ValidationError):
        policy.ClassificationPolicy.model_validate(raw)


@pytest.mark.parametrize("dimension", ["asset_class", *PAUSED])
def test_v3_rejects_unregistered_dimension_catalog_values(dimension):
    raw = policy.load_policy(V3_PATH).model_dump()
    raw["catalog"][dimension] += ("INCOMPATIBLE_OLD_CODE",)
    with pytest.raises(ValidationError):
        policy.ClassificationPolicy.model_validate(raw)


@pytest.mark.parametrize("dimension", models.DIMENSIONS)
def test_v3_snapshot_rejects_values_outside_its_enum_version(dimension):
    raw = legacy_snapshot("3.0.0")
    raw[dimension].update(status="CONFIRMED", value="INCOMPATIBLE_OLD_CODE")
    with pytest.raises(ValidationError):
        models.ClassificationSnapshot.model_validate(raw)


def test_paused_carry_requires_complete_source_revision_and_versions():
    with pytest.raises(ValidationError):
        models.DimensionResult(
            status="CONFIRMED",
            value="US",
            evaluation_state="PAUSED",
            evidence=(evidence(),),
            carried_from_revision_id=42,
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
    raw = legacy_snapshot("3.0.0")
    raw["strategy_tag_results"] = {"QUANTITATIVE": {"status": "UNKNOWN", "evaluation_state": state}}
    snapshot = models.ClassificationSnapshot.model_validate(raw)
    assert snapshot.strategy_tags == ()
    assert snapshot.strategy_tag_results["QUANTITATIVE"].evaluation_state == state
    assert models.ClassificationSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot


@pytest.mark.parametrize("status", ["CONFIRMED", "CANDIDATE", "CONFLICT", "UNKNOWN"])
def test_tag_projection_includes_only_confirmed_evidence_results(status):
    raw = legacy_snapshot("3.0.0")
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
    raw = legacy_snapshot("3.0.0")
    raw["strategy_tags"] = ["QUANTITATIVE"]
    with pytest.raises(ValidationError):
        models.ClassificationSnapshot.model_validate(raw)


def test_paused_carry_and_incompatible_history_reference_roundtrip():
    raw = legacy_snapshot("3.0.0")
    raw["geography"].update(
        status="CONFIRMED",
        value="US",
        evidence=[evidence("geography", "US")],
        evaluation_state="PAUSED",
        carried_from_revision_id=42,
        source_rule_version="1.0.0",
        source_enum_version="1.0.0",
    )
    raw["product_structure"].update(
        evaluation_state="NOT_EVALUATED",
        carried_from_revision_id=41,
        source_rule_version="1.0.0",
        source_enum_version="1.0.0",
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
def test_v3_paused_dimensions_cannot_claim_current_evaluation(dimension):
    raw = legacy_snapshot("3.0.0")
    raw[dimension]["evaluation_state"] = "EVALUATED"
    with pytest.raises(ValidationError):
        models.ClassificationSnapshot.model_validate(raw)


@pytest.mark.parametrize("dimension", PAUSED)
@pytest.mark.parametrize("missing", ["omitted", "null"])
def test_v3_paused_dimensions_require_explicit_evaluation_state(dimension, missing):
    raw = legacy_snapshot("3.0.0")
    if missing == "omitted":
        raw[dimension].pop("evaluation_state")
    else:
        raw[dimension]["evaluation_state"] = None
    with pytest.raises(ValidationError):
        models.ClassificationSnapshot.model_validate(raw)


@pytest.mark.parametrize(
    ("rule_version", "enum_version"),
    [("3.0.0", "1.0.0"), ("3.0.0", "2.0.0"), ("1.0.0", "3.0.0"), ("2.0.0", "3.0.0")],
)
def test_v3_snapshot_rejects_unregistered_version_pairs(rule_version, enum_version):
    raw = legacy_snapshot("3.0.0")
    raw.update(rule_version=rule_version, enum_version=enum_version)
    with pytest.raises(ValidationError):
        models.ClassificationSnapshot.model_validate(raw)


def test_v3_rule_version_cannot_bypass_quantitative_strategy_rejection():
    raw = legacy_snapshot("3.0.0")
    raw["enum_version"] = "1.0.0"
    raw["strategy"].update(status="CONFIRMED", value="QUANTITATIVE", evidence=[evidence()])
    with pytest.raises(ValidationError):
        models.ClassificationSnapshot.model_validate(raw)


@pytest.mark.parametrize("status", ["CONFIRMED", "CANDIDATE", "CONFLICT"])
def test_tag_assertions_require_evidence_and_unknown_remains_available(status):
    raw = legacy_snapshot("3.0.0")
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
    raw = legacy_snapshot("3.0.0")
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
