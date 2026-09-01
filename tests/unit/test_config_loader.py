import pathlib

import pytest

from fip.platform.config.loader import load_config_file
from fip.platform.config.models import Parameter, ParameterStatus
from fip.platform.decision_data.context import RuntimeMode

YAML = """
scoring:
  weights:
    return_score:
      value: 0.30
      status: PROVISIONAL
      source: "P1-6 待投研定案"
    risk_adjusted_score:
      value: 0.30
      status: DECIDED
      source: "2026-08-20 投研评审纪要"
  normalization:
    method:
      value: Z_SCORE
      status: DECIDED
      source: "04-factor/05-factor-normalization"
"""


@pytest.fixture()
def cfg_file(tmp_path: pathlib.Path) -> pathlib.Path:
    p = tmp_path / "scoring.yaml"
    p.write_text(YAML, encoding="utf-8")
    return p


def test_loads_leaf_parameters_by_dotted_path(cfg_file):
    cfg = load_config_file(cfg_file, runtime_mode=RuntimeMode.BACKTEST)
    assert cfg.get("scoring.weights.return_score") == 0.30
    assert cfg.get("scoring.normalization.method") == "Z_SCORE"


def test_leaf_missing_status_is_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("a:\n  b:\n    value: 1\n    source: x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="status"):
        load_config_file(bad, runtime_mode=RuntimeMode.BACKTEST)


def test_leaf_missing_source_is_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("a:\n  b:\n    value: 1\n    status: DECIDED\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source"):
        load_config_file(bad, runtime_mode=RuntimeMode.BACKTEST)


def test_unknown_path_raises(cfg_file):
    cfg = load_config_file(cfg_file, runtime_mode=RuntimeMode.BACKTEST)
    with pytest.raises(KeyError, match="scoring.weights.nonexistent"):
        cfg.get("scoring.weights.nonexistent")


def test_provisional_use_under_live_fires_hook(cfg_file):
    """LIVE 消费 PROVISIONAL 参数必须发出告警事件。"""
    seen: list[Parameter] = []
    cfg = load_config_file(cfg_file, runtime_mode=RuntimeMode.LIVE,
                           on_provisional_use=seen.append)
    cfg.get("scoring.weights.return_score")
    assert [p.path for p in seen] == ["scoring.weights.return_score"]
    assert seen[0].status is ParameterStatus.PROVISIONAL
    assert seen[0].source == "P1-6 待投研定案"


def test_decided_use_under_live_does_not_fire_hook(cfg_file):
    seen: list[Parameter] = []
    cfg = load_config_file(cfg_file, runtime_mode=RuntimeMode.LIVE,
                           on_provisional_use=seen.append)
    cfg.get("scoring.weights.risk_adjusted_score")
    assert seen == []


def test_backtest_records_usage_without_firing_hook(cfg_file):
    """回测允许使用，但占位标记仍须落入报告的配置章节。"""
    seen: list[Parameter] = []
    cfg = load_config_file(cfg_file, runtime_mode=RuntimeMode.BACKTEST,
                           on_provisional_use=seen.append)
    cfg.get("scoring.weights.return_score")
    assert seen == []
    assert cfg.provisional_parameters_used == ("scoring.weights.return_score",)


def test_provisional_usage_is_deduplicated_and_sorted(cfg_file):
    cfg = load_config_file(cfg_file, runtime_mode=RuntimeMode.LIVE)
    cfg.get("scoring.weights.return_score")
    cfg.get("scoring.weights.return_score")
    cfg.get("scoring.weights.risk_adjusted_score")
    assert cfg.provisional_parameters_used == ("scoring.weights.return_score",)


def test_provisional_never_blocks(cfg_file):
    """不阻断 —— 阻断会让 M1 无法端到端运行。"""
    cfg = load_config_file(cfg_file, runtime_mode=RuntimeMode.LIVE)
    assert cfg.get("scoring.weights.return_score") == 0.30
