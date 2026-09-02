# Plan-2 实现计划草稿 · Task 14–18

> 本文件是 `docs/superpowers/plans/2026-09-02-plan2-factor-and-evaluation.md`
> 的 Task 14–18 详稿，供并入主计划。上游权威顺序：
> 主计划的【跨任务接口契约】> 设计定案 `2026-09-02-plan2-factor-and-evaluation-design.md`
> > 两份 digest。本稿不发明与契约冲突的名字。

## 本稿钉定的上游接口（契约未定义，须回填进主计划的【跨任务接口契约】）

Task 14–18 消费的下列名字**在主计划的接口契约中不存在**。它们必须由 Task 7/8/9/11/12/13
产出，本稿在此逐条钉死签名；执行那些任务的实现者若采用了别的名字，
必须回来改这一节而不是各自发明。

```python
# ---- 落位：按 P2-1（撤销 D-3）留在 Plan-1 的位置 ----
#   fip.quant_engine.*        （不是 fip.libs.quant_engine）
#   fip.strategy_library.*    （不是 fip.libs.strategy_library）

# ---- Task 9 产出，Task 14 消费（契约已定义类型，此处只钉 import 路径）----
# fip.strategy_library.factor.status      : FactorStatus
# fip.strategy_library.factor.definitions : PreferenceDirection
#                                           FACTOR_IDS: tuple[str, ...]        ← 契约缺
#                                           preference_direction(fid) -> PreferenceDirection  ← 契约缺

# ---- Task 3 产出，Task 15/17 消费（契约已定义签名，此处只钉 import 路径）----
# fip.quant_engine.stats.median(xs: Sequence[Decimal]) -> Decimal

# ---- Task 13 产出，Task 14 消费：检验结论的形状 —— 契约完全没有定义 ----
#   本稿把它定义在 fip.strategy_library.score.subscore.FactorEffectiveness
#   （见 Task 14 的 Produces）。若 Task 13 另造一个类型，两边必须统一到一个。

# ---- Task 7 产出，Task 17 消费：factor schema 的 ORM 模块路径 ----
# fip.services.factor_service.models.factor
#   FactorDefinition / FactorVersion / FactorRun / FactorValue / FactorEffectivenessRow
# ---- Task 8 产出，Task 15/16/17 消费：evaluation schema 的 ORM 模块路径 ----
# fip.services.fund_service.models.evaluation
#   PeerGroupSnapshot / PeerGroupMember / FundScore / FundScoreAttribution
#   FundRanking / FundTierRow / FundUniverseSnapshot / FundUniverseMember
#   SelectionConditionResult
```

**模块路径不是风格问题**：SB-1（Task 17）的静态检查以「哪个 service 包定义了哪个 schema 的
ORM 模块」为键。若 evaluation 的 model 落在 `fip.services.data_service.models` 下，
SB-1 会在第一天就永久失真。

**Task 8 建表时必须包含的列**（Task 16 依赖，D-15 的落地形态）：
`evaluation.fund_universe_member` 上是三列版本引用而**不是**一列取值副本 ——
`share_class_id`（本就有）、`eligibility_effective_at DATE NULL`、`eligibility_version INT NULL`，
复合 FK `(share_class_id, eligibility_effective_at, eligibility_version)`
→ `fund.investment_eligibility(share_class_id, effective_at, version)` `ON DELETE RESTRICT`，
外加 `CHECK ((eligibility_effective_at IS NULL) = (eligibility_version IS NULL))`。
复用 `share_class_id` 这一列是有意的：它在结构上堵死「引用到别人那一版可投资性」。

**Task 8 建表时必须包含的另外三组列**（G-8 / G-9 / G-4 的落库形态）：
`fund_ranking` 上 `rank` / `n_effective` / `percentile` / `peer_group_size` /
`ranking_status` 五列齐备；`fund_tier` 上除两列已定案的
（`classification_status` / `n_effective`）外还须有
`percentile` / `total_score` / `peer_sharpe_median` / `peer_max_drawdown_median`；
`fund_score` 上须有 `data_completeness` 与 `weight_source`。

**MAR 不经本组任务**：P2-4 裁定 Task 10 删除 `config/policy/evaluation/v1.yaml` 里的
`mar.default`（它直接违反 G-6「必填无默认」）。因此本稿的 `EvaluationPolicy`
**不含** `mar` 字段 —— MAR 由 Task 10 的 Threshold Resolver 按三模式解析后
直接进 `FactorInput.mar`，未配置即 `None`，`F-RISK-002` / `F-RAP-002` 一律 `UNAVAILABLE`。

---

### Task 14: 五子分 + 归因 + Data Completeness

> 依赖 Task 13（因子有效性检验）。本任务全部落在 `strategy_library`，**纯函数**：
> 不碰数据库、不读配置文件、不含 `runtime_mode` 分支（SDL-1 / SDL-2）。
> Profile 与有效性结论都由调用方注入。

**Files:**
- Create: `src/fip/strategy_library/score/__init__.py`
- Create: `src/fip/strategy_library/score/attribution.py`
- Create: `src/fip/strategy_library/score/subscore.py`
- Create: `src/fip/strategy_library/score/completeness.py`
- Test: `tests/unit/test_sub_score.py`
- Test: `tests/unit/test_score_completeness.py`
- Modify: `config/strategy/factor/v1.yaml`（Profile 的因子声明与子分权重）

**Interfaces:**

- Consumes:
  - `fip.strategy_library.factor.status.FactorStatus`（Task 9）
  - `fip.strategy_library.factor.definitions.PreferenceDirection`（Task 9）
- Produces:
  ```python
  # score/attribution.py
  WEIGHT_QUANTUM: Decimal      # Decimal("0.00000001")，与 RatioNumeric(12,8) 对齐
  SCORE_QUANTUM: Decimal       # Decimal("0.00000001")
  RATIO_QUANTUM: Decimal       # Decimal("0.00000001")

  @dataclass(frozen=True, slots=True)
  class NormalizedFactor:
      factor_id: str
      window: str
      raw_value: Decimal | None
      normalized_score: Decimal | None
      status: FactorStatus
      direction: PreferenceDirection
      reason: str

  @dataclass(frozen=True, slots=True)
  class FactorAttribution:
      factor_id: str
      window: str
      raw_value: Decimal | None
      normalized_score: Decimal | None
      direction: PreferenceDirection | None
      weight: Decimal
      weighted_contribution: Decimal | None
      participated: bool
      exclusion_reason: str | None
      effectiveness_verdict: str          # "VALID" / "INVALID" / "NOT_TESTED"
      redistributed_to: tuple[str, ...]

  # score/subscore.py
  class ScoreStatus(StrEnum): COMPLETED; PARTIAL; UNAVAILABLE;
                              VALIDATION_PENDING; INSUFFICIENT_FACTORS
  class SubScoreName(StrEnum): RETURN; RISK; RISK_ADJUSTED; STABILITY;
                               RELATIVE_PERFORMANCE
  class WeightSource(StrEnum): EQUAL_WITHIN_VALID; OPTIMIZED

  @dataclass(frozen=True, slots=True)
  class FactorEffectiveness:
      factor_id: str; profile_id: str; is_valid: bool
      ic: Decimal | None; icir: Decimal | None; reason: str

  @dataclass(frozen=True, slots=True)
  class EvaluationProfile:
      profile_id: str
      declared_factors: Mapping[SubScoreName, tuple[str, ...]]
      sub_score_weights: Mapping[SubScoreName, Decimal]
      min_valid_factors_per_sub_score: int

  @dataclass(frozen=True, slots=True)
  class SubScoreResult:
      name: SubScoreName; value: Decimal | None; status: ScoreStatus
      weight_source: WeightSource; applied_weight: Decimal | None
      attributions: tuple[FactorAttribution, ...]

  @dataclass(frozen=True, slots=True)
  class FundScoreResult:
      profile_id: str; total_score: Decimal | None; status: ScoreStatus
      data_completeness: Decimal; sub_scores: tuple[SubScoreResult, ...]

  def compute_sub_score(name: SubScoreName, declared: Sequence[str],
                        factors: Mapping[str, NormalizedFactor],
                        effectiveness: Mapping[str, FactorEffectiveness],
                        min_valid_factors: int) -> SubScoreResult: ...
  def compute_fund_score(profile: EvaluationProfile,
                         factors: Mapping[str, NormalizedFactor],
                         effectiveness: Mapping[str, FactorEffectiveness]
                         ) -> FundScoreResult: ...

  # score/completeness.py
  def data_completeness(profile: EvaluationProfile,
                        sub_scores: Sequence[SubScoreResult]) -> Decimal: ...
  ```

- [ ] **Step 1: 写失败的单元测试（先证伪，G-18）**

```python
# tests/unit/test_sub_score.py
"""五子分 / 归因 / score_status 的行为锁定。

本文件锁住的是最容易被「优化」掉的四件事：
  · invalid 因子的权重恰为 0，但【仍在归因链里】并带失效原因（FS §8.4.1 规则 2）
  · 检验未产出 → VALIDATION_PENDING，【不产出总分】（FS:342/346，D-1）
  · M1 的常态是 PARTIAL（REL 子分恒 UNAVAILABLE），不是异常（D-19）
  · UNAVAILABLE 不得被任何填充值替代（G-3）
"""
from decimal import Decimal

import pytest

from fip.strategy_library.factor.definitions import PreferenceDirection
from fip.strategy_library.factor.status import FactorStatus
from fip.strategy_library.score.attribution import NormalizedFactor
from fip.strategy_library.score.subscore import (
    EvaluationProfile,
    FactorEffectiveness,
    ScoreStatus,
    SubScoreName,
    WeightSource,
    compute_fund_score,
    compute_sub_score,
)

HIGHER = PreferenceDirection.HIGHER_IS_BETTER
LOWER = PreferenceDirection.LOWER_IS_BETTER

# M1 的唯一 Profile：声明 13 个因子 —— 10 个可算 + 3 个 REL。
# REL 三个【必须声明】：data_completeness 的分母是「Profile 声明的因子数」，
# 若分母只算 10 个可算因子，M1 的 completeness 恒为 1.0，
# 「基于 4 个子分的 85 分与基于 5 个子分的 85 分必须可区分」（spec §6.2）
# 这条就被静默抹掉了。三个 REL ID 取自 D-8 点明的、从现存文档中泄露出的真实 ID。
M1_DECLARED = {
    SubScoreName.RETURN: ("F-RET-001", "F-RET-002"),
    SubScoreName.RISK: ("F-RISK-001", "F-RISK-002", "F-RISK-003"),
    SubScoreName.RISK_ADJUSTED: ("F-RAP-001", "F-RAP-002", "F-RAP-003"),
    SubScoreName.STABILITY: ("F-STAB-001", "F-STAB-002"),
    SubScoreName.RELATIVE_PERFORMANCE: ("F-REL-002", "F-REL-003", "F-REL-004"),
}
M1_SUB_WEIGHTS = {name: Decimal("0.2") for name in SubScoreName}


def profile(min_valid: int = 2) -> EvaluationProfile:
    return EvaluationProfile(
        profile_id="M1-DEFAULT",
        declared_factors=M1_DECLARED,
        sub_score_weights=M1_SUB_WEIGHTS,
        min_valid_factors_per_sub_score=min_valid,
    )


def nf(factor_id: str, score: str | None, status: FactorStatus = FactorStatus.VALID,
       direction: PreferenceDirection = HIGHER, raw: str | None = "1.0",
       reason: str = "") -> NormalizedFactor:
    return NormalizedFactor(
        factor_id=factor_id,
        window="3Y",
        raw_value=None if raw is None else Decimal(raw),
        normalized_score=None if score is None else Decimal(score),
        status=status,
        direction=direction,
        reason=reason,
    )


def eff(factor_id: str, valid: bool = True, reason: str = "") -> FactorEffectiveness:
    return FactorEffectiveness(
        factor_id=factor_id, profile_id="M1-DEFAULT", is_valid=valid,
        ic=Decimal("0.05"), icir=Decimal("0.4"), reason=reason,
    )


def all_ten_valid() -> tuple[dict, dict]:
    """10 个可算因子全部 VALID 且检验通过；3 个 REL 声明了但不可算。"""
    computable = [f for name, ids in M1_DECLARED.items() for f in ids
                  if name is not SubScoreName.RELATIVE_PERFORMANCE]
    factors = {fid: nf(fid, "60.0") for fid in computable}
    for fid in M1_DECLARED[SubScoreName.RELATIVE_PERFORMANCE]:
        factors[fid] = nf(fid, None, FactorStatus.UNAVAILABLE, raw=None,
                          reason="Benchmark 四层建模推到 M2，REL 全类不可算")
    effectiveness = {fid: eff(fid) for fid in factors}
    return factors, effectiveness


# --- 权重 -----------------------------------------------------------------

def test_weights_are_equal_within_valid_and_sum_to_exactly_one():
    """FS §8.4.1 规则 1：权重在【有效因子内】归一，和恰为 1。

    1/3 在十进制下无法精确表示，naive quantize 会给出 0.99999999。
    """
    result = compute_sub_score(
        SubScoreName.RISK_ADJUSTED,
        M1_DECLARED[SubScoreName.RISK_ADJUSTED],
        {fid: nf(fid, "60.0") for fid in M1_DECLARED[SubScoreName.RISK_ADJUSTED]},
        {fid: eff(fid) for fid in M1_DECLARED[SubScoreName.RISK_ADJUSTED]},
        min_valid_factors=2,
    )
    assert result.weight_source is WeightSource.EQUAL_WITHIN_VALID
    assert sum(a.weight for a in result.attributions) == Decimal("1")
    assert result.value == Decimal("60.00000000")


def test_invalid_factor_has_zero_weight_but_stays_in_attribution():
    """FS §8.4.1 规则 2 / §10.4：Calmar 判 invalid → 权重恰为 0，

    但【必须出现在归因链中】并标注失效原因 —— 否则无法回答
    「为什么这只基金的 Calmar 没影响分数」。
    """
    ids = M1_DECLARED[SubScoreName.RISK_ADJUSTED]  # Sharpe / Sortino / Calmar
    effectiveness = {fid: eff(fid) for fid in ids}
    effectiveness["F-RAP-003"] = eff("F-RAP-003", valid=False, reason="IC 0.004 < 0.02")

    result = compute_sub_score(
        SubScoreName.RISK_ADJUSTED, ids,
        {fid: nf(fid, "60.0") for fid in ids}, effectiveness, min_valid_factors=2,
    )
    by_id = {a.factor_id: a for a in result.attributions}
    assert set(by_id) == set(ids), "被剔除的因子从归因中消失了"
    calmar = by_id["F-RAP-003"]
    assert calmar.weight == Decimal("0")
    assert calmar.participated is False
    assert calmar.effectiveness_verdict == "INVALID"
    assert "IC 0.004" in (calmar.exclusion_reason or "")
    assert calmar.weighted_contribution is None
    assert set(calmar.redistributed_to) == {"F-RAP-001", "F-RAP-002"}
    assert by_id["F-RAP-001"].weight == Decimal("0.5")
    assert by_id["F-RAP-002"].weight == Decimal("0.5")


def test_unavailable_factor_is_never_filled():
    """G-3：UNAVAILABLE 不得被 0 / 上期 / 组内均值替代。"""
    ids = M1_DECLARED[SubScoreName.RISK]
    factors = {fid: nf(fid, "60.0") for fid in ids}
    factors["F-RISK-002"] = nf("F-RISK-002", None, FactorStatus.UNAVAILABLE,
                               LOWER, raw=None, reason="mar_policy 未配置")
    result = compute_sub_score(SubScoreName.RISK, ids, factors,
                               {fid: eff(fid) for fid in ids}, min_valid_factors=2)
    dv = next(a for a in result.attributions if a.factor_id == "F-RISK-002")
    assert dv.normalized_score is None
    assert dv.raw_value is None
    assert dv.weight == Decimal("0")
    assert dv.weighted_contribution is None
    assert "mar_policy 未配置" in (dv.exclusion_reason or "")
    # 参与的两个因子照常等权，子分【不因缺一个而变成 0 或被拉低】
    assert result.value == Decimal("60.00000000")
    assert result.status is ScoreStatus.PARTIAL


def test_single_valid_factor_yields_insufficient_factors_without_redistribution():
    """FS §9.3 已定案：子分内有效指标数 < 2 → 该子分 UNAVAILABLE，

    且【不做权重重分配】——「单一指标构成的子分等于该指标本身」。
    """
    ids = M1_DECLARED[SubScoreName.STABILITY]
    factors = {ids[0]: nf(ids[0], "70.0"),
               ids[1]: nf(ids[1], None, FactorStatus.UNAVAILABLE, raw=None,
                          reason="观测数 300 < min_obs 504")}
    result = compute_sub_score(SubScoreName.STABILITY, ids, factors,
                               {fid: eff(fid) for fid in ids}, min_valid_factors=2)
    assert result.status is ScoreStatus.INSUFFICIENT_FACTORS
    assert result.value is None
    assert all(a.weight == Decimal("0") for a in result.attributions)
    survivor = next(a for a in result.attributions if a.factor_id == ids[0])
    assert survivor.participated is False
    assert "不做权重重分配" in (survivor.exclusion_reason or "")


# --- 总分与 score_status ---------------------------------------------------

def test_validation_pending_produces_no_total_score():
    """D-1 / FS:342/346：factor_effectiveness 未产出 → 不产出总分。

    「先按等权上线、等检验出来再调」与「未经检验就拍权重」上游明定为完全等价。
    """
    factors, _ = all_ten_valid()
    result = compute_fund_score(profile(), factors, effectiveness={})
    assert result.status is ScoreStatus.VALIDATION_PENDING
    assert result.total_score is None
    assert all(s.value is None for s in result.sub_scores)
    # G-4：即使不产出总分，data_completeness 仍是必备字段
    assert result.data_completeness == Decimal("0")
    verdicts = {a.effectiveness_verdict
                for s in result.sub_scores for a in s.attributions}
    assert verdicts == {"NOT_TESTED"}


def test_m1_normal_case_is_partial_not_an_error():
    """D-19：M1 的【常态】是 PARTIAL —— REL 子分恒 UNAVAILABLE。

    这条必须被显式断言：否则「PARTIAL 是正常的」这个事实会在下游被当成
    异常处理（告警、阻断、或干脆把 PARTIAL 的分数丢弃）。
    """
    factors, effectiveness = all_ten_valid()
    result = compute_fund_score(profile(), factors, effectiveness)
    assert result.status is ScoreStatus.PARTIAL
    assert result.total_score == Decimal("60.00000000")
    rel = next(s for s in result.sub_scores
               if s.name is SubScoreName.RELATIVE_PERFORMANCE)
    assert rel.status is ScoreStatus.UNAVAILABLE
    assert rel.value is None
    assert rel.applied_weight is None            # 不参与总分，且不留残余权重
    others = [s for s in result.sub_scores if s.name is not rel.name]
    assert all(s.status is ScoreStatus.COMPLETED for s in others)
    # 四个子分重归一后各占 0.25，和恰为 1
    assert sum(s.applied_weight for s in others) == Decimal("1")


def test_completed_requires_all_five_sub_scores():
    factors, effectiveness = all_ten_valid()
    for fid in M1_DECLARED[SubScoreName.RELATIVE_PERFORMANCE]:
        factors[fid] = nf(fid, "50.0")
    result = compute_fund_score(profile(), factors, effectiveness)
    assert result.status is ScoreStatus.COMPLETED
    assert result.data_completeness == Decimal("1")


def test_unavailable_when_no_sub_score_can_be_produced():
    factors, effectiveness = all_ten_valid()
    factors = {fid: nf(fid, None, FactorStatus.UNAVAILABLE, raw=None,
                       reason="观测数不足") for fid in factors}
    result = compute_fund_score(profile(), factors, effectiveness)
    assert result.status is ScoreStatus.UNAVAILABLE
    assert result.total_score is None


def test_insufficient_factors_outranks_partial_in_fund_status():
    """状态优先级（【补齐】）：VALIDATION_PENDING > UNAVAILABLE >

    INSUFFICIENT_FACTORS > PARTIAL > COMPLETED。上游未给优先级，此处钉死。
    """
    factors, effectiveness = all_ten_valid()
    factors["F-STAB-002"] = nf("F-STAB-002", None, FactorStatus.UNAVAILABLE,
                               raw=None, reason="观测数 300 < min_obs 504")
    result = compute_fund_score(profile(), factors, effectiveness)
    assert result.status is ScoreStatus.INSUFFICIENT_FACTORS
    assert result.total_score is not None, "子分不足不等于总分不可产出"


def test_reproducible_bitwise_on_recompute():
    """G-2：同一输入重算必须一致（容差 1e-10；这里要求逐位相同）。"""
    factors, effectiveness = all_ten_valid()
    first = compute_fund_score(profile(), factors, effectiveness)
    second = compute_fund_score(profile(), dict(reversed(list(factors.items()))),
                                effectiveness)
    assert first.total_score == second.total_score
    assert abs(first.total_score - second.total_score) < Decimal("1e-10")
    assert [a.weight for s in first.sub_scores for a in s.attributions] == \
           [a.weight for s in second.sub_scores for a in s.attributions]


def test_profile_declaring_no_factor_is_rejected_not_defaulted():
    """空 Profile 不得静默产出 completeness = 1.0 —— 0/0 是配置错误，不是「完整」。"""
    from fip.strategy_library.score.completeness import data_completeness

    empty = EvaluationProfile(profile_id="EMPTY", declared_factors={},
                              sub_score_weights=M1_SUB_WEIGHTS,
                              min_valid_factors_per_sub_score=2)
    with pytest.raises(ValueError, match="声明的因子数为 0"):
        data_completeness(empty, ())
```

```python
# tests/unit/test_score_completeness.py
"""Data Completeness —— G-4 的输出必备字段。

定义（【补齐 PROVISIONAL】，设计定案 §7 缺口 2）：
    data_completeness = 实际参与评分的因子数 / 该 Profile 声明的因子数

本文件【自带】全部夹具，不从 test_sub_score.py 导入：tests/unit 下没有
__init__.py，跨测试文件的 import 依赖 rootdir 注入，是一条会在别人改
pytest 配置时静默断掉的隐式依赖。
"""
from decimal import Decimal

import pytest

from fip.strategy_library.factor.definitions import PreferenceDirection
from fip.strategy_library.factor.status import FactorStatus
from fip.strategy_library.score.attribution import NormalizedFactor
from fip.strategy_library.score.completeness import data_completeness
from fip.strategy_library.score.subscore import (
    EvaluationProfile,
    FactorEffectiveness,
    ScoreStatus,
    SubScoreName,
    compute_fund_score,
)

DECLARED = {
    SubScoreName.RETURN: ("F-RET-001", "F-RET-002"),
    SubScoreName.RISK: ("F-RISK-001", "F-RISK-002", "F-RISK-003"),
    SubScoreName.RISK_ADJUSTED: ("F-RAP-001", "F-RAP-002", "F-RAP-003"),
    SubScoreName.STABILITY: ("F-STAB-001", "F-STAB-002"),
    SubScoreName.RELATIVE_PERFORMANCE: ("F-REL-002", "F-REL-003", "F-REL-004"),
}
PROFILE = EvaluationProfile(
    profile_id="M1-DEFAULT",
    declared_factors=DECLARED,
    sub_score_weights={name: Decimal("0.2") for name in SubScoreName},
    min_valid_factors_per_sub_score=2,
)


def _factor(fid: str, score: str | None, status: FactorStatus, reason: str = ""):
    return NormalizedFactor(
        factor_id=fid, window="3Y",
        raw_value=None if score is None else Decimal("1.0"),
        normalized_score=None if score is None else Decimal(score),
        status=status, direction=PreferenceDirection.HIGHER_IS_BETTER, reason=reason,
    )


def _effectiveness(fid: str, valid: bool = True, reason: str = ""):
    return FactorEffectiveness(
        factor_id=fid, profile_id="M1-DEFAULT", is_valid=valid,
        ic=Decimal("0.05"), icir=Decimal("0.4"), reason=reason,
    )


def _baseline() -> tuple[dict, dict]:
    """10 个可算因子全部 VALID；3 个 REL 声明了但恒 UNAVAILABLE。"""
    factors = {}
    for name, ids in DECLARED.items():
        for fid in ids:
            if name is SubScoreName.RELATIVE_PERFORMANCE:
                factors[fid] = _factor(fid, None, FactorStatus.UNAVAILABLE,
                                       "Benchmark 推到 M2，REL 全类不可算")
            else:
                factors[fid] = _factor(fid, "60.0", FactorStatus.VALID)
    return factors, {fid: _effectiveness(fid) for fid in factors}


def test_m1_completeness_is_ten_over_thirteen():
    """M1 的分母含 3 个声明但不可算的 REL 因子 —— 这正是 spec §6.2 要求的

    「基于 4 个子分的 85 分与基于 5 个子分的 85 分必须可区分」的落地。
    若分母只算 10 个可算因子，completeness 恒为 1.0，该区分被静默抹掉。
    """
    factors, effectiveness = _baseline()
    result = compute_fund_score(PROFILE, factors, effectiveness)
    assert result.data_completeness == Decimal("0.76923077")
    assert result.data_completeness < Decimal("1")


def test_completeness_drops_when_a_factor_becomes_unavailable():
    factors, effectiveness = _baseline()
    factors["F-RAP-003"] = _factor(
        "F-RAP-003", None, FactorStatus.UNAVAILABLE,
        "Max Drawdown = 0，Calmar 不可算（不得填 inf）",
    )
    result = compute_fund_score(PROFILE, factors, effectiveness)
    assert result.data_completeness == Decimal("0.69230769")      # 9 / 13


def test_completeness_counts_participation_not_availability():
    """判 INVALID 的因子【有值】却不参与评分，分子里不得算它。

    分子取「有值」会让「基于 3 个指标的 85 分」看起来像
    「基于 4 个指标的 85 分」—— 而那正是本字段要防的那件事（FS:415）。
    """
    factors, effectiveness = _baseline()
    effectiveness["F-RET-002"] = _effectiveness("F-RET-002", valid=False,
                                                reason="IC 0.001 未过阈值")
    result = compute_fund_score(PROFILE, factors, effectiveness)
    # 8 / 13，不是 9 / 13：Return 子分只剩 1 个有效因子（< 2），按 FS §9.3
    # 该子分整体不产出【且不做权重重分配】，于是幸存的 F-RET-001 也不参与。
    assert result.data_completeness == Decimal("0.61538462")
    ret = next(s for s in result.sub_scores if s.name is SubScoreName.RETURN)
    assert ret.status is ScoreStatus.INSUFFICIENT_FACTORS         # 1 < 2
    assert ret.value is None


def test_zero_declared_factors_raises_instead_of_returning_one():
    empty = EvaluationProfile(
        profile_id="EMPTY", declared_factors={},
        sub_score_weights={name: Decimal("0.2") for name in SubScoreName},
        min_valid_factors_per_sub_score=2,
    )
    with pytest.raises(ValueError, match="声明的因子数为 0"):
        data_completeness(empty, ())
```

- [ ] **Step 2: 运行确认失败（G-18 先证伪）**

Run: `.venv/bin/pytest tests/unit/test_sub_score.py tests/unit/test_score_completeness.py -q`

Expected: 全部 collection error —
`ModuleNotFoundError: No module named 'fip.strategy_library.score'`。
把这段输出粘进执行报告；**没有先看到这条失败就不许往下写实现**。

- [ ] **Step 3: 实现归因数据结构**

```python
# src/fip/strategy_library/score/attribution.py
"""归因明细 —— FS §10.2 / §10.3 / §10.4。

归因链：Total Score → 五子分 + 权重 → 各 Factor 的 Normalized Score × Weight
→ Factor Raw Value + Direction + Peer Group 内分位。

FS:456：`raw_value` 不可省略 —— 只有标准化值时用户看不懂「0.83 分」从何而来。
FS §10.4：被排除的因子必须记录【为什么被排除】，而不是从归因中消失。
"""

from dataclasses import dataclass
from decimal import Decimal

from fip.strategy_library.factor.definitions import PreferenceDirection
from fip.strategy_library.factor.status import FactorStatus

# 量化步长与存储精度对齐（platform/db/types.py）：
#   权重 / 比率 → RatioNumeric = Numeric(12, 8)
#   分数        → NavNumeric   = Numeric(18, 8)
# 在纯函数里就量化，而不是等到落库时才截断：G-2 要求「同一输入重算必须一致」，
# 若纯函数返回无限精度而由 ORM 静默取整，两次重算之间只要中间量的位数不同，
# 落库值就可能不同，而单元测试完全看不见。
WEIGHT_QUANTUM = Decimal("0.00000001")
SCORE_QUANTUM = Decimal("0.00000001")
RATIO_QUANTUM = Decimal("0.00000001")


@dataclass(frozen=True, slots=True)
class NormalizedFactor:
    """一只基金、一个因子、一个窗口在 Peer Group 内标准化后的全部事实。

    normalized_score 为 None 表示【该因子在本组内没有分位】——
    可能是因子本身 UNAVAILABLE，也可能是 N == 1（percentile_rank 返回 None）。
    两种都【不得】被 0 / 50 / 组内均值替代（G-3）。
    """

    factor_id: str
    window: str
    raw_value: Decimal | None
    normalized_score: Decimal | None
    status: FactorStatus
    direction: PreferenceDirection
    reason: str


@dataclass(frozen=True, slots=True)
class FactorAttribution:
    """归因链最底层的一行。FS §10.3 的六项 + §10.4 的三类信息。

    §10.3 六项：factor_id + window / raw_value / normalized_score /
                direction / weight / weighted_contribution
    §10.4 三类：排除原因（exclusion_reason）、原权重（invalid 时恒为 0，
                见下）、重分配去向（redistributed_to）

    ⚠️「原权重」在 EQUAL_WITHIN_VALID 下【不存在】：权重是在有效因子内
    现算的 1/n，被排除的因子从来没有过一个「原本的权重」可供剥夺。
    FS §10.4 的示例格式（「原权重 X%、重分配至 Sharpe +X%」）描述的是
    第二版 OPTIMIZED 权重下的形态。此处如实记 weight = 0，并用
    redistributed_to 回答「那份权重去哪了」——即同子分内实际参与的因子集合。
    """

    factor_id: str
    window: str
    raw_value: Decimal | None
    normalized_score: Decimal | None
    direction: PreferenceDirection | None
    weight: Decimal
    weighted_contribution: Decimal | None
    participated: bool
    exclusion_reason: str | None
    effectiveness_verdict: str
    redistributed_to: tuple[str, ...]
```

- [ ] **Step 4: 实现五子分与总分**

```python
# src/fip/strategy_library/score/subscore.py
"""五子分合成 —— FS §8。

合成公式（FS:256-263，一字不差）：
    Weighted Contribution_i = Normalized Score_i × Weight_i
    Sub-Score_k             = Σ Weighted Contribution_i   (i ∈ 子分 k 的因子集合)
    Total Score             = Σ Sub-Score_k × Weight_k    (k = 五个子分)

因子层权重 = EQUAL_WITHIN_VALID（FS §8.4.1，已定案 2026-08-27）：
【有效因子内】等权，不是全体因子等权，也不是「先等权上线再调」。
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from fip.strategy_library.factor.status import FactorStatus
from fip.strategy_library.score.attribution import (
    SCORE_QUANTUM,
    WEIGHT_QUANTUM,
    FactorAttribution,
    NormalizedFactor,
)


class ScoreStatus(StrEnum):
    """D-19 裁定的五值。`NOT_AVAILABLE` 与 `UNAVAILABLE` 是同一概念的两种拼写，

    统一取 `UNAVAILABLE`（与 FactorStatus 的枚举一致）。
    同一枚举同时用于子分层与基金层，取值含义在两层上是一致的。
    """

    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    VALIDATION_PENDING = "VALIDATION_PENDING"
    INSUFFICIENT_FACTORS = "INSUFFICIENT_FACTORS"


class SubScoreName(StrEnum):
    """FS §4.1：命名固定，不得增删改。枚举的声明顺序即输出顺序（确定性）。"""

    RETURN = "Return"
    RISK = "Risk"
    RISK_ADJUSTED = "Risk-Adjusted"
    STABILITY = "Stability"
    RELATIVE_PERFORMANCE = "Relative Performance"


class WeightSource(StrEnum):
    """FS §8.4.1 规则 3：权重来源须落库，与第二版的 OPTIMIZED 区分。"""

    EQUAL_WITHIN_VALID = "EQUAL_WITHIN_VALID"
    OPTIMIZED = "OPTIMIZED"          # 第二版；本 Plan 不实现，留作落库取值域


@dataclass(frozen=True, slots=True)
class FactorEffectiveness:
    """Task 13 的判定结论。本层【只消费判定结果】，不判定阈值（FS:350）。"""

    factor_id: str
    profile_id: str
    is_valid: bool
    ic: Decimal | None
    icir: Decimal | None
    reason: str


@dataclass(frozen=True, slots=True)
class EvaluationProfile:
    """一个 Evaluation Profile 的评分结构。全部取自配置，不得硬编码。

    declared_factors 是【声明】不是【可算】：M1 的 REL 三项声明了但不可算，
    正因为声明了，data_completeness 的分母才含它们（spec §6.2）。
    """

    profile_id: str
    declared_factors: Mapping[SubScoreName, tuple[str, ...]]
    sub_score_weights: Mapping[SubScoreName, Decimal]
    min_valid_factors_per_sub_score: int


@dataclass(frozen=True, slots=True)
class SubScoreResult:
    name: SubScoreName
    value: Decimal | None
    status: ScoreStatus
    weight_source: WeightSource
    applied_weight: Decimal | None      # 在总分中实际使用的子分权重（重归一后）
    attributions: tuple[FactorAttribution, ...]


@dataclass(frozen=True, slots=True)
class FundScoreResult:
    profile_id: str
    total_score: Decimal | None
    status: ScoreStatus
    data_completeness: Decimal
    sub_scores: tuple[SubScoreResult, ...]


_PARTICIPATING_STATUSES = frozenset({FactorStatus.VALID, FactorStatus.WARNING})

# FS §7.3 消费方规则：WARNING「参与但标记须传递」——所以它在参与集合里，
# 而它的 reason 会原样落进归因行的 exclusion_reason 之外的 raw/normalized 列，
# 标记的传递由 Task 17 落库时携带 factor_status 完成。


def _equal_weights(n: int) -> list[Decimal]:
    """n 个有效因子的等权向量，Σ【恰为】1。

    1/3 在十进制下无法精确表示。直接对每一项 quantize 得到的是
    0.33333333 × 3 = 0.99999999 —— 差 1e-8，正好落在 RatioNumeric(12,8)
    能看见的一位上，于是「权重之和为 1」（FS:322）在落库后为假。
    因此最后一项吸收残差；调用方按 factor_id 升序传入，结果确定可复现。
    """
    if n <= 0:
        return []
    share = (Decimal(1) / Decimal(n)).quantize(WEIGHT_QUANTUM, rounding=ROUND_HALF_UP)
    weights = [share] * (n - 1)
    weights.append(Decimal(1) - share * (n - 1))
    return weights


def compute_sub_score(
    name: SubScoreName,
    declared: Sequence[str],
    factors: Mapping[str, NormalizedFactor],
    effectiveness: Mapping[str, FactorEffectiveness],
    min_valid_factors: int,
) -> SubScoreResult:
    """一个子分。Scoring Process 的 ②③④⑤ 步（FS §13.2）。

    排除顺序固定，且【每一步都留痕】：
      1. 无有效性检验结论  → NOT_TESTED（D-1：检验是产出的前置条件）
      2. 检验判 INVALID    → 权重 0，留在归因链里（FS §8.4.1 规则 2）
      3. 本次未产出因子值  → 声明了却没算出来，如实记录
      4. factor_status ∉ {VALID, WARNING} → 按 FS §7.3 不参与
      5. 组内分位不可得（N == 1）→ 不得填 50 或 100（D-11）
    """
    ordered = sorted(declared)
    participating: list[str] = []
    verdicts: dict[str, str] = {}
    reasons: dict[str, str | None] = {}

    for fid in ordered:
        factor = factors.get(fid)
        verdict = effectiveness.get(fid)
        if verdict is None:
            verdicts[fid] = "NOT_TESTED"
            reasons[fid] = (
                "factor_effectiveness 未产出该因子的检验结论；"
                "未经检验的因子不得参与评分（FS:346）"
            )
            continue
        verdicts[fid] = "VALID" if verdict.is_valid else "INVALID"
        if not verdict.is_valid:
            reasons[fid] = f"有效性检验判定 INVALID：{verdict.reason}"
            continue
        if factor is None:
            reasons[fid] = "Profile 声明了本因子，但本次运行未产出因子值"
            continue
        if factor.status not in _PARTICIPATING_STATUSES:
            reasons[fid] = f"factor_status={factor.status}：{factor.reason}"
            continue
        if factor.normalized_score is None:
            reasons[fid] = (
                "Peer Group 内分位不可得（N == 1）；"
                "不得以 50 / 100 / 组内均值替代（G-3）"
            )
            continue
        participating.append(fid)
        reasons[fid] = None

    produced = len(participating) >= max(min_valid_factors, 1)
    if not produced and participating:
        # FS §9.3 已定案：有效指标数 < 2 → 该子分 UNAVAILABLE，
        # 且【不做权重重分配】。留下的那一个因子也不参与。
        for fid in participating:
            reasons[fid] = (
                f"子分内有效因子数 {len(participating)} < {min_valid_factors}，"
                "按 FS §9.3 该子分不产出且不做权重重分配"
            )

    weights = _equal_weights(len(participating)) if produced else []
    weight_by_id = dict(zip(participating, weights, strict=True)) if produced else {}
    redistributed = tuple(participating) if produced else ()

    rows: list[FactorAttribution] = []
    for fid in ordered:
        factor = factors.get(fid)
        weight = weight_by_id.get(fid, Decimal("0"))
        took_part = fid in weight_by_id
        contribution = None
        if took_part and factor is not None and factor.normalized_score is not None:
            contribution = (factor.normalized_score * weight).quantize(
                SCORE_QUANTUM, rounding=ROUND_HALF_UP
            )
        rows.append(
            FactorAttribution(
                factor_id=fid,
                window=factor.window if factor else "",
                raw_value=factor.raw_value if factor else None,
                normalized_score=factor.normalized_score if factor else None,
                direction=factor.direction if factor else None,
                weight=weight,
                weighted_contribution=contribution,
                participated=took_part,
                exclusion_reason=None if took_part else reasons[fid],
                effectiveness_verdict=verdicts[fid],
                redistributed_to=() if took_part else redistributed,
            )
        )

    if not participating:
        status = ScoreStatus.UNAVAILABLE
        value = None
    elif not produced:
        status = ScoreStatus.INSUFFICIENT_FACTORS
        value = None
    else:
        status = (
            ScoreStatus.COMPLETED
            if len(participating) == len(ordered)
            else ScoreStatus.PARTIAL
        )
        value = sum(
            (r.weighted_contribution for r in rows if r.weighted_contribution is not None),
            Decimal("0"),
        ).quantize(SCORE_QUANTUM, rounding=ROUND_HALF_UP)

    return SubScoreResult(
        name=name,
        value=value,
        status=status,
        weight_source=WeightSource.EQUAL_WITHIN_VALID,
        applied_weight=None,          # 由 compute_fund_score 重归一后回填
        attributions=tuple(rows),
    )


def _renormalized(
    available: Sequence[SubScoreResult], declared: Mapping[SubScoreName, Decimal]
) -> list[Decimal]:
    """把 Profile 的子分权重在【可产出的子分内】重归一，Σ 恰为 1。

    FS:343：某子分 UNAVAILABLE → 总分「按剩余子分处理」，即
    EXCLUDE_AND_RENORMALIZE（FS §9.2 的推荐策略）。
    绝不把缺失子分按 0 分计入 —— 那是 §9.2 明令严禁的两种做法之一。
    """
    total = sum((declared[s.name] for s in available), Decimal("0"))
    if total <= 0:
        raise ValueError(f"可产出子分的权重之和为 {total}，Profile 配置有误")
    weights = [
        (declared[s.name] / total).quantize(WEIGHT_QUANTUM, rounding=ROUND_HALF_UP)
        for s in available[:-1]
    ]
    weights.append(Decimal(1) - sum(weights, Decimal("0")))
    return weights


def compute_fund_score(
    profile: EvaluationProfile,
    factors: Mapping[str, NormalizedFactor],
    effectiveness: Mapping[str, FactorEffectiveness],
) -> FundScoreResult:
    """一只基金在一个 Profile 下的总分。FS §13.2 的八步。

    ⚠️ 状态优先级是【补齐】——上游给了五个取值却没给同时成立时的优先级：
        VALIDATION_PENDING > UNAVAILABLE > INSUFFICIENT_FACTORS
                           > PARTIAL > COMPLETED
    取这个顺序的理由：越靠前的状态越是「这个分数不能按字面使用」的强信号，
    下游按最强信号处置才不会误用。
    """
    from fip.strategy_library.score.completeness import data_completeness

    declared_ids = [fid for ids in profile.declared_factors.values() for fid in ids]
    subs = [
        compute_sub_score(
            name,
            profile.declared_factors.get(name, ()),
            factors,
            effectiveness,
            profile.min_valid_factors_per_sub_score,
        )
        for name in SubScoreName
    ]

    # D-1 的前置：没有【任何一个】声明因子拿到检验结论 → 检验尚未产出。
    # 部分因子有结论时不算「未产出」——那些没有结论的因子逐个被排除即可。
    if declared_ids and not any(fid in effectiveness for fid in declared_ids):
        return FundScoreResult(
            profile_id=profile.profile_id,
            total_score=None,
            status=ScoreStatus.VALIDATION_PENDING,
            data_completeness=data_completeness(profile, subs),
            sub_scores=tuple(subs),
        )

    available = [s for s in subs if s.value is not None]
    if not available:
        return FundScoreResult(
            profile_id=profile.profile_id,
            total_score=None,
            status=ScoreStatus.UNAVAILABLE,
            data_completeness=data_completeness(profile, subs),
            sub_scores=tuple(subs),
        )

    weights = _renormalized(available, profile.sub_score_weights)
    applied = {s.name: w for s, w in zip(available, weights, strict=True)}
    total = sum(
        (s.value * applied[s.name] for s in available), Decimal("0")
    ).quantize(SCORE_QUANTUM, rounding=ROUND_HALF_UP)

    if any(s.status is ScoreStatus.INSUFFICIENT_FACTORS for s in subs):
        status = ScoreStatus.INSUFFICIENT_FACTORS
    elif len(available) < len(subs):
        status = ScoreStatus.PARTIAL
    else:
        status = ScoreStatus.COMPLETED

    resolved = tuple(
        SubScoreResult(
            name=s.name,
            value=s.value,
            status=s.status,
            weight_source=s.weight_source,
            applied_weight=applied.get(s.name),
            attributions=s.attributions,
        )
        for s in subs
    )
    return FundScoreResult(
        profile_id=profile.profile_id,
        total_score=total,
        status=status,
        data_completeness=data_completeness(profile, resolved),
        sub_scores=resolved,
    )
```

- [ ] **Step 5: 实现 Data Completeness**

```python
# src/fip/strategy_library/score/completeness.py
"""Data Completeness —— G-4 的输出必备字段。

上游只给了口径（FS:418「可用指标数 / 应有指标数」）没给确切计算式，
设计定案 §7 缺口 2 把它定义为：

    data_completeness = 实际参与评分的因子数 / 该 Profile 声明的因子数

标 PROVISIONAL：分子取「参与评分」而非「有值」是一个真正的口径选择 ——
一个算得出值但被有效性检验判 INVALID 的因子，对分数的贡献是 0，
把它算进分子会让「基于 3 个指标的 85 分」看起来像「基于 4 个指标的 85 分」，
而这正是本字段要防的那件事（FS:415）。
"""

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from fip.strategy_library.score.attribution import RATIO_QUANTUM
from fip.strategy_library.score.subscore import EvaluationProfile, SubScoreResult


def data_completeness(
    profile: EvaluationProfile, sub_scores: Sequence[SubScoreResult]
) -> Decimal:
    declared = sum(len(ids) for ids in profile.declared_factors.values())
    if declared == 0:
        # 不返回 1.0：0/0 既不是「完整」也不是「不完整」，是配置错误。
        # 静默返回 1.0 会让一个什么都没声明的 Profile 报告「数据完整」。
        raise ValueError(
            f"Profile {profile.profile_id} 声明的因子数为 0，"
            "data_completeness 无定义（分母为 0）"
        )
    used = sum(1 for s in sub_scores for a in s.attributions if a.participated)
    return (Decimal(used) / Decimal(declared)).quantize(
        RATIO_QUANTUM, rounding=ROUND_HALF_UP
    )
```

```python
# src/fip/strategy_library/score/__init__.py
"""评分层。纯函数，不含数据访问与运行模式分支（SDL-1 / SDL-2）。"""
```

- [ ] **Step 6: 落配置——Profile 的因子声明与子分权重**

```yaml
# config/strategy/factor/v1.yaml
# Factor Version v1 —— 因子清单、Factor Usage 与 Evaluation Profile 的评分结构
# Owner: factor-service（因子身份与口径）/ fund-service（Profile 的权重结构）
#
# ⚠️ 本文件【整体】是设计定案 §3 的【补齐】：因子域的八份上游文档在仓库中
# 一份都不存在（docs/04-factor/ 实为 05-fund-evaluation/ 的逐字节副本）。
# 拿到正式的因子域文档后应整体替换，而不是逐项修改。
profile:
  m1_default:
    id:
      value: M1-DEFAULT
      status: PROVISIONAL
      source: "设计定案 §7 缺口 3：M1 只实现一个 Profile，四类画像推到 M2"
    min_valid_factors_per_sub_score:
      value: 2
      status: DECIDED
      source: "FS §9.3 已定案 2026-08-27：子分内有效指标数 < 2 → 该子分 UNAVAILABLE"
    declared_factors:
      Return:
        value: ["F-RET-001", "F-RET-002"]
        status: PROVISIONAL
        source: "设计定案 D-8 因子清单；D-21 裁定 Rolling Return 归 RET"
      Risk:
        value: ["F-RISK-001", "F-RISK-002", "F-RISK-003"]
        status: PROVISIONAL
        source: "设计定案 D-8"
      Risk-Adjusted:
        value: ["F-RAP-001", "F-RAP-002", "F-RAP-003"]
        status: PROVISIONAL
        source: "设计定案 D-8"
      Stability:
        value: ["F-STAB-001", "F-STAB-002"]
        status: PROVISIONAL
        source: "设计定案 D-8"
      Relative Performance:
        # 【声明但不可算】。三个 ID 是 D-8 点明的、从现存文档中泄露出的真实 ID。
        # 为什么必须声明：data_completeness 的分母是「Profile 声明的因子数」。
        # 若分母只算 10 个可算因子，M1 的 completeness 恒为 1.0，
        # spec §6.2 要求的「基于 4 个子分的 85 分与基于 5 个子分的 85 分必须
        # 可区分」就被静默抹掉 —— 而那正是 M1 用来跑通 UNAVAILABLE 机制的
        # 唯一场景。Tracking Error 与 Benchmark 超额收益【不在此列】：
        # 它们的真实 Factor ID 未从任何现存文档泄露，凭空编号会在拿到正式
        # 文档时与真 ID 冲突，比少声明两个更难修。
        value: ["F-REL-002", "F-REL-003", "F-REL-004"]
        status: PROVISIONAL
        source: "设计定案 D-8：Benchmark 四层建模推到 M2，REL 全类恒 UNAVAILABLE"
    sub_score_weights:
      # ⚠️ 这是本 Plan 里【最需要被质疑】的一组值，如实登记其来源冲突：
      # BR:278 明确禁止「现在拍一个 25% / 25% / 25% / 25%」，FS:299 要求
      # 「不得事先拍板权重」；而 FS:301-304 只把【因子层】权重定案为
      # EQUAL_WITHIN_VALID，把【子分层】权重推给「由 Profile 定义」，
      # §8.5 又只定了个别因子在个别画像下的相对高低（费率 / MDD / Alpha /
      # TE），无一项在 M1 可算。也就是说：M1 的子分权重上游【既禁止拍板
      # 也没有给值】，而 Fund Tier 依赖总分、总分依赖子分权重（D-1 的同一
      # 条论证链）。取等权是被这条链逼出来的唯一可行值，不是判断。
      # 它与 EQUAL_WITHIN_VALID 的关键差别：因子层的等权【已定案】，
      # 子分层的等权【是占位】，因此标 PROVISIONAL —— 在 LIVE 模式下每次
      # 取用都会发出 ProvisionalParameterUsed 告警（platform/config/loader.py）。
      Return:
        value: "0.2"
        status: PROVISIONAL
        source: "设计定案 §7 缺口 3 + FS §8.4：上游禁止拍板但未给值，见本节说明"
      Risk:
        value: "0.2"
        status: PROVISIONAL
        source: "同上"
      Risk-Adjusted:
        value: "0.2"
        status: PROVISIONAL
        source: "同上"
      Stability:
        value: "0.2"
        status: PROVISIONAL
        source: "同上"
      Relative Performance:
        value: "0.2"
        status: PROVISIONAL
        source: "同上"
```

- [ ] **Step 7: 运行确认通过**

Run: `.venv/bin/pytest tests/unit/test_sub_score.py tests/unit/test_score_completeness.py -v`

Expected: 全部通过。特别核对这三条出现在 PASSED 列表里 ——
`test_m1_normal_case_is_partial_not_an_error`、
`test_validation_pending_produces_no_total_score`、
`test_invalid_factor_has_zero_weight_but_stays_in_attribution`。

Run: `.venv/bin/pytest tests/fitness -q && .venv/bin/ruff check src tests && make typecheck`

Expected: 适应度测试全绿（新包不得引入 I/O 依赖与 runtime_mode 分支）、lint 与 typecheck 通过。

- [ ] **Step 8: 提交**

```bash
git add -A
git commit -m "feat(score): 五子分、归因与 Data Completeness

因子层权重 EQUAL_WITHIN_VALID —— 有效因子内等权，不是全体等权；
invalid 因子权重恰为 0 但留在归因链中并带失效原因与重分配去向。
检验未产出 → VALIDATION_PENDING，不产出总分（D-1）。
M1 常态为 PARTIAL（REL 子分恒 UNAVAILABLE），由测试显式断言。
data_completeness 的分母含 3 个声明但不可算的 REL 因子，故 M1 恒为 10/13。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SZBJBiDWT8FHcx7NhkgcTD"
```

---

### Task 15: 排名 / 分位 / Fund Tier

> 依赖 Task 14。仍然全部落在 `strategy_library`，纯函数。
> 派生链（BR §16.1）：`Fund Score → Peer Group Ranking → Percentile → Fund Tier`，
> 「四者是同一条派生链上的不同表示，不是四个独立概念」。

**Files:**
- Create: `src/fip/strategy_library/ranking/__init__.py`
- Create: `src/fip/strategy_library/ranking/rank.py`
- Test: `tests/unit/test_ranking.py`
- Test: `tests/unit/test_fund_tier.py`
- Test: `tests/fitness/test_single_config_source.py`
- Modify: `config/policy/evaluation/v1.yaml`（`peer_group.min_sample_size` 与 Tier 阈值）

**Interfaces:**

- Consumes:
  - `fip.strategy_library.score.subscore.ScoreStatus`（Task 14）
  - `fip.quant_engine.stats.median`（Task 3，用于组内绝对水平）
- Produces:
  ```python
  # ranking/rank.py
  class TieMethod(StrEnum): COMPETITION_RANK; DENSE_RANK; ORDINAL_RANK
  class CrossSectionStatus(StrEnum): NORMAL; INSUFFICIENT_SAMPLE
  class FundTier(StrEnum): A_PLUS = "A+"; A = "A"; B = "B"; C = "C"; D = "D"

  @dataclass(frozen=True, slots=True)
  class RankingEntry:
      share_class_id: int; profile_id: str; metric_value: Decimal | None

  @dataclass(frozen=True, slots=True)
  class RankingResult:
      share_class_id: int; profile_id: str
      rank: int | None; percentile: Decimal | None
      n_effective: int; peer_group_size: int
      ranking_status: CrossSectionStatus; tie_method: TieMethod

  @dataclass(frozen=True, slots=True)
  class TierThresholds:
      a_plus: Decimal; a: Decimal; b: Decimal; c: Decimal

  @dataclass(frozen=True, slots=True)
  class PeerGroupAbsoluteLevel:
      sharpe_median: Decimal | None; max_drawdown_median: Decimal | None

  @dataclass(frozen=True, slots=True)
  class TierResult:
      share_class_id: int; profile_id: str
      tier: FundTier | None; percentile: Decimal | None
      rank: int | None; n_effective: int; total_score: Decimal | None
      classification_status: CrossSectionStatus
      peer_group_level: PeerGroupAbsoluteLevel      # 无默认值，G-9 的结构化落地

  def rank_within_peer_group(entries: Sequence[RankingEntry], *,
                             peer_group_size: int,
                             min_peer_group_size: int) -> list[RankingResult]: ...
  def assign_tier(ranking: RankingResult, *, total_score: Decimal | None,
                  thresholds: TierThresholds,
                  peer_group_level: PeerGroupAbsoluteLevel,
                  min_peer_group_size: int) -> TierResult: ...
  def peer_group_absolute_level(sharpe_values: Sequence[Decimal],
                                mdd_values: Sequence[Decimal]
                                ) -> PeerGroupAbsoluteLevel: ...
  ```

- [ ] **Step 1: 写失败的排名测试**

```python
# tests/unit/test_ranking.py
"""COMPETITION_RANK + Percentile + 小样本 —— G-7 / G-8 / G-10 / D-20。"""
from decimal import Decimal

import pytest

from fip.strategy_library.ranking.rank import (
    CrossSectionStatus,
    RankingEntry,
    TieMethod,
    rank_within_peer_group,
)


def entries(*pairs: tuple[int, str | None], profile: str = "M1-DEFAULT"):
    return [
        RankingEntry(share_class_id=i, profile_id=profile,
                     metric_value=None if v is None else Decimal(v))
        for i, v in pairs
    ]


def test_competition_rank_skips_after_ties():
    """D-20：并列同名次，后续跳号 —— 1, 2, 2, 4。

    DENSE_RANK（1,2,2,3）会让「N 只基金的最大名次 < N」，于是
    Percentile 公式 (N − Rank)/(N − 1) 的分母与实际名次范围不匹配，
    「前 10%」实际包含的基金数随并列数量漂移（FR:277-285）。
    """
    results = rank_within_peer_group(
        entries((1, "90"), (2, "85"), (3, "85"), (4, "80")),
        peer_group_size=4, min_peer_group_size=1,
    )
    assert [r.rank for r in results] == [1, 2, 2, 4]
    assert max(r.rank for r in results) == 4 == len(results)
    assert {r.tie_method for r in results} == {TieMethod.COMPETITION_RANK}


def test_percentile_endpoints_are_100_and_0():
    """FR:211-215：本项目采用 (N − Rank)/(N − 1) × 100，最优 100、最劣 0。"""
    results = rank_within_peer_group(
        entries(*[(i, str(100 - i)) for i in range(1, 6)]),
        peer_group_size=5, min_peer_group_size=1,
    )
    assert results[0].percentile == Decimal("100.00000000")
    assert results[-1].percentile == Decimal("0E-8")
    mid = results[2]
    assert mid.percentile == Decimal("50.00000000")


def test_percentile_matches_the_documented_example():
    """FR:218-220：Rank = 5，N = 120 → (120 − 5) / 119 × 100 ≈ 96.6%。"""
    results = rank_within_peer_group(
        entries(*[(i, str(1000 - i)) for i in range(1, 121)]),
        peer_group_size=120, min_peer_group_size=1,
    )
    fifth = next(r for r in results if r.rank == 5)
    assert fifth.n_effective == 120
    assert Decimal("96.63") < fifth.percentile < Decimal("96.65")


def test_rank_n_effective_and_percentile_are_all_present():
    """G-8：三者都必须落库 —— 只存 Rank 则历史分位不可还原。

    这里断言的是【纯函数就把三者一起产出】，落库测试在 Task 17。
    """
    results = rank_within_peer_group(
        entries((1, "90"), (2, "80")), peer_group_size=2, min_peer_group_size=1,
    )
    for r in results:
        assert r.rank is not None
        assert r.n_effective == 2
        assert r.percentile is not None
        assert r.peer_group_size == 2


def test_unavailable_metric_yields_no_row_and_shrinks_n_effective():
    """FR:186-197：N 是【有效参与数】不是组规模。

    指标 UNAVAILABLE 的基金不产出排名行（ERD §9.4：Ranking 基数是 0..1），
    也不得计入 N —— 更不得按 0 分参与排名（G-3）。
    """
    results = rank_within_peer_group(
        entries((1, "90"), (2, None), (3, "80")),
        peer_group_size=3, min_peer_group_size=1,
    )
    assert [r.share_class_id for r in results] == [1, 3]
    assert {r.n_effective for r in results} == {2}
    assert {r.peer_group_size for r in results} == {3}


def test_insufficient_sample_returns_rows_with_null_rank_and_percentile():
    """FR §9.3.1：n_effective < 30 → rank / percentile 为 null，

    n_effective 返回实际值，ranking_status = INSUFFICIENT_SAMPLE。
    FR:356：「n_effective 仍须返回 —— 调用方需要知道差多少」。
    FR:730：这一行【仍然落库】，不落库会让历史查询无法区分
    「当时样本不足」与「当时根本没算」。
    """
    results = rank_within_peer_group(
        entries(*[(i, str(100 - i)) for i in range(1, 18)]),
        peer_group_size=17, min_peer_group_size=30,
    )
    assert len(results) == 17
    for r in results:
        assert r.rank is None
        assert r.percentile is None
        assert r.n_effective == 17
        assert r.ranking_status is CrossSectionStatus.INSUFFICIENT_SAMPLE


def test_single_member_group_has_no_percentile():
    """FR:234-240：N = 1 → 分母为 0 → Percentile = UNAVAILABLE。

    此时【不得】返回 ranking_status = NORMAL：数据库的联动 CHECK 是
    (NORMAL AND rank NOT NULL AND percentile NOT NULL) OR
    (INSUFFICIENT_SAMPLE AND rank IS NULL AND percentile IS NULL)，
    没有第三种形态可容纳「有名次但无分位」。生产配置下 1 < 30 恒成立，
    此分支只在 min_peer_group_size 被调低时可达，这里显式钉住。
    """
    results = rank_within_peer_group(
        entries((7, "90")), peer_group_size=1, min_peer_group_size=1,
    )
    assert len(results) == 1
    assert results[0].percentile is None
    assert results[0].rank is None
    assert results[0].n_effective == 1
    assert results[0].ranking_status is CrossSectionStatus.INSUFFICIENT_SAMPLE


def test_sub_rankings_are_split_by_profile():
    """G-10：同一 Peer Group 内多个 Profile 时按 Profile 拆分子排名，

    不产出跨 Profile 统一排名。M1 只有一个 Profile，这条在生产中【空洞成立】
    —— 正因如此必须在这里用两个 Profile 把它钉住，否则 M2 加第二个 Profile
    时会静默产出一份把两个 Profile 混在一起的排名，而没有任何测试会红。
    """
    mixed = (
        entries((1, "90"), (2, "80"), profile="M1-DEFAULT")
        + entries((3, "95"), (4, "70"), profile="ACTIVE-EQUITY")
    )
    results = rank_within_peer_group(mixed, peer_group_size=4, min_peer_group_size=1)
    by_profile: dict[str, list] = {}
    for r in results:
        by_profile.setdefault(r.profile_id, []).append(r)
    assert set(by_profile) == {"M1-DEFAULT", "ACTIVE-EQUITY"}
    for rows in by_profile.values():
        assert sorted(r.rank for r in rows) == [1, 2]
        assert {r.n_effective for r in rows} == {2}      # 各自 2，不是 4


def test_output_order_is_deterministic_regardless_of_input_order():
    """FR §8.4：并列时不得依赖数据库返回顺序 —— 每次重算可能不同则违反可复现性。

    次级规则显式声明为 share_class_id 升序。
    """
    forward = entries((1, "85"), (2, "85"), (3, "85"))
    backward = list(reversed(forward))
    a = rank_within_peer_group(forward, peer_group_size=3, min_peer_group_size=1)
    b = rank_within_peer_group(backward, peer_group_size=3, min_peer_group_size=1)
    assert [(r.share_class_id, r.rank, r.percentile) for r in a] == \
           [(r.share_class_id, r.rank, r.percentile) for r in b]
    assert [r.rank for r in a] == [1, 1, 1]


def test_mixed_profile_and_unavailable_metric_do_not_interfere():
    mixed = (
        entries((1, "90"), (2, None), profile="M1-DEFAULT")
        + entries((3, "95"), (4, "70"), profile="ACTIVE-EQUITY")
    )
    results = rank_within_peer_group(mixed, peer_group_size=4, min_peer_group_size=1)
    m1 = [r for r in results if r.profile_id == "M1-DEFAULT"]
    assert len(m1) == 1
    assert m1[0].n_effective == 1
    assert m1[0].ranking_status is CrossSectionStatus.INSUFFICIENT_SAMPLE


@pytest.mark.parametrize("size", [0, -1])
def test_peer_group_size_must_be_positive(size: int):
    with pytest.raises(ValueError, match="peer_group_size"):
        rank_within_peer_group(entries((1, "90")), peer_group_size=size,
                               min_peer_group_size=1)
```

- [ ] **Step 2: 写失败的 Tier 测试**

```python
# tests/unit/test_fund_tier.py
"""Fund Tier 五档 —— 阈值 5/20/50/80、G-9 同屏、小样本不产出。"""
from decimal import Decimal

import pytest

from fip.strategy_library.ranking.rank import (
    CrossSectionStatus,
    FundTier,
    PeerGroupAbsoluteLevel,
    RankingResult,
    TierResult,
    TierThresholds,
    assign_tier,
    peer_group_absolute_level,
)

# 已定案 · 2026-08-25（P0-2）：前 5% / 5–20% / 20–50% / 50–80% / 后 20%。
# 换算到 percentile 空间即 95 / 80 / 50 / 20（FC §8.3）——
# 「这是一处极易出错的换算：『前 5%』在 Rank 语义下是小序号，
#   在 Percentile 语义下是大数值」（FC:214）。
THRESHOLDS = TierThresholds(a_plus=Decimal("95"), a=Decimal("80"),
                            b=Decimal("50"), c=Decimal("20"))
LEVEL = PeerGroupAbsoluteLevel(sharpe_median=Decimal("0.62"),
                               max_drawdown_median=Decimal("0.183"))


def ranked(percentile: str | None, n_effective: int = 120,
           status: CrossSectionStatus = CrossSectionStatus.NORMAL) -> RankingResult:
    from fip.strategy_library.ranking.rank import TieMethod

    return RankingResult(
        share_class_id=1, profile_id="M1-DEFAULT",
        rank=None if percentile is None else 5,
        percentile=None if percentile is None else Decimal(percentile),
        n_effective=n_effective, peer_group_size=n_effective,
        ranking_status=status, tie_method=TieMethod.COMPETITION_RANK,
    )


@pytest.mark.parametrize(
    ("percentile", "expected"),
    [
        ("100", FundTier.A_PLUS),
        ("95", FundTier.A_PLUS),      # 恰好等于阈值 → 归入较优档（FC §13）
        ("94.99999999", FundTier.A),
        ("80", FundTier.A),
        ("79.99999999", FundTier.B),
        ("50", FundTier.B),
        ("49.99999999", FundTier.C),
        ("20", FundTier.C),
        ("19.99999999", FundTier.D),
        ("0", FundTier.D),
    ],
)
def test_tier_boundaries_are_upper_closed(percentile: str, expected: FundTier):
    result = assign_tier(ranked(percentile), total_score=Decimal("77"),
                         thresholds=THRESHOLDS, peer_group_level=LEVEL,
                         min_peer_group_size=30)
    assert result.tier is expected
    assert result.classification_status is CrossSectionStatus.NORMAL


def test_thresholds_cover_the_whole_range_exclusively_and_monotonically():
    """FC §8.4 的三项边界校验：完备性 / 互斥性 / 单调性。

    在 [0, 100] 上以 0.5 步长扫描：每个取值必须恰好落入一个档，
    且 percentile 越高档位越优。
    """
    order = [FundTier.D, FundTier.C, FundTier.B, FundTier.A, FundTier.A_PLUS]
    previous = -1
    p = Decimal("0")
    while p <= Decimal("100"):
        tier = assign_tier(ranked(str(p)), total_score=Decimal("50"),
                           thresholds=THRESHOLDS, peer_group_level=LEVEL,
                           min_peer_group_size=30).tier
        assert tier is not None, f"percentile={p} 落在任何档之外（完备性失败）"
        index = order.index(tier)
        assert index >= previous, f"percentile={p} 处档位倒退（单调性失败）"
        previous = index
        p += Decimal("0.5")


def test_top_percent_and_percentile_thresholds_are_mutually_checkable():
    """FC:214 要求两种表述必须能互相校验：前 X% ⇔ percentile ≥ 100 − X。"""
    top_percent = {"a_plus": Decimal("5"), "a": Decimal("20"),
                   "b": Decimal("50"), "c": Decimal("80")}
    for field, top in top_percent.items():
        assert getattr(THRESHOLDS, field) == Decimal("100") - top


def test_small_sample_produces_no_tier_at_all():
    """FC §8.5 已定案 2026-08-27：n_effective < 30 → 【不产出】Tier，

    而不是「产出一个带低置信标记的 Tier」。FC:249 的理由：
    「Tier 值仍存在，下游会照常使用它……标记只在展示层可见，
      而消费 Tier 的是代码不是人」。
    """
    result = assign_tier(
        ranked(None, n_effective=17, status=CrossSectionStatus.INSUFFICIENT_SAMPLE),
        total_score=Decimal("77"), thresholds=THRESHOLDS,
        peer_group_level=LEVEL, min_peer_group_size=30,
    )
    assert result.tier is None
    assert result.classification_status is CrossSectionStatus.INSUFFICIENT_SAMPLE
    assert result.n_effective == 17          # 判定依据仍须返回
    assert result.percentile is None


def test_no_percentile_means_no_tier_not_the_lowest_tier():
    """FC §13 Edge Case：percentile = UNAVAILABLE → 无 Tier，

    【不得默认为最低档】。默认 D 会把「不知道」伪装成「很差」。
    """
    result = assign_tier(ranked(None, n_effective=120), total_score=None,
                         thresholds=THRESHOLDS, peer_group_level=LEVEL,
                         min_peer_group_size=30)
    assert result.tier is None
    assert result.classification_status is CrossSectionStatus.INSUFFICIENT_SAMPLE


def test_tier_cannot_be_constructed_without_peer_group_absolute_level():
    """G-9 的结构化落地：Tier 不得单独输出。

    上游把它写成「强制要求」而不是建议（BR:1094-1096、FC:157
    「仅展示 Tier 而不展示组内绝对水平，视为违反本条」）。
    口头要求会被违反，因此把它做成【类型上不可能】：
    peer_group_level 是 TierResult 的必填字段且无默认值 ——
    想只输出 Tier，得先造出一个 TierResult，而那需要组内绝对水平。
    """
    with pytest.raises(TypeError):
        TierResult(                                   # type: ignore[call-arg]
            share_class_id=1, profile_id="M1-DEFAULT", tier=FundTier.A_PLUS,
            percentile=Decimal("96"), rank=5, n_effective=120,
            total_score=Decimal("88"),
            classification_status=CrossSectionStatus.NORMAL,
        )


def test_absolute_level_is_unavailable_not_zero_when_group_has_no_valid_factor():
    """G-3：组内没有任何有效 Sharpe 时中位数是 UNAVAILABLE，不是 0。"""
    level = peer_group_absolute_level(sharpe_values=[], mdd_values=[])
    assert level.sharpe_median is None
    assert level.max_drawdown_median is None


def test_absolute_level_uses_median_of_valid_values_only():
    level = peer_group_absolute_level(
        sharpe_values=[Decimal("0.1"), Decimal("0.5"), Decimal("0.9")],
        mdd_values=[Decimal("0.2"), Decimal("0.4")],
    )
    assert level.sharpe_median == Decimal("0.5")
    assert level.max_drawdown_median == Decimal("0.3")


def test_thresholds_must_be_strictly_descending():
    with pytest.raises(ValueError, match="必须严格递减"):
        TierThresholds(a_plus=Decimal("80"), a=Decimal("95"),
                       b=Decimal("50"), c=Decimal("20"))
```

- [ ] **Step 3: 运行确认失败**

Run: `.venv/bin/pytest tests/unit/test_ranking.py tests/unit/test_fund_tier.py -q`

Expected: collection error —
`ModuleNotFoundError: No module named 'fip.strategy_library.ranking'`。把输出粘进报告。

- [ ] **Step 4: 实现排名、分位与 Tier**

```python
# src/fip/strategy_library/ranking/rank.py
"""Peer Group 内排名、分位与五档分层。

派生链（BR §16.1）：Fund Score → Ranking → Percentile → Fund Tier。
「四者是同一条派生链上的不同表示，不是四个独立概念。
  任一环节的输入变化会沿链传导。」（BR:1061）

本模块是纯函数：阈值、最小样本量都由调用方注入，不读配置、不碰数据库。
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from fip.quant_engine.stats import median
from fip.strategy_library.score.attribution import SCORE_QUANTUM


class TieMethod(StrEnum):
    """FR §8.1 的三种方法。D-20 裁定取 COMPETITION_RANK。

    另两个取值保留为落库取值域（ranking_policy 要能记录当时用的是哪一种），
    但本 Plan 只实现 COMPETITION_RANK —— 未实现的分支会显式抛错，
    不会静默退化成默认实现。
    """

    COMPETITION_RANK = "COMPETITION_RANK"
    DENSE_RANK = "DENSE_RANK"
    ORDINAL_RANK = "ORDINAL_RANK"


class CrossSectionStatus(StrEnum):
    """`cross_section_status_enum`（04-database-design §10.1.2 已定案）。"""

    NORMAL = "NORMAL"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"


class FundTier(StrEnum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"


@dataclass(frozen=True, slots=True)
class RankingEntry:
    share_class_id: int
    profile_id: str
    metric_value: Decimal | None


@dataclass(frozen=True, slots=True)
class RankingResult:
    share_class_id: int
    profile_id: str
    rank: int | None
    percentile: Decimal | None
    n_effective: int
    peer_group_size: int
    ranking_status: CrossSectionStatus
    tie_method: TieMethod


@dataclass(frozen=True, slots=True)
class TierThresholds:
    """分位阈值。BR:1075「阈值配置化，严禁硬编码」，因此由调用方注入。"""

    a_plus: Decimal
    a: Decimal
    b: Decimal
    c: Decimal

    def __post_init__(self) -> None:
        values = (self.a_plus, self.a, self.b, self.c)
        if not all(a > b for a, b in zip(values, values[1:], strict=False)):
            raise ValueError(f"Tier 阈值必须严格递减，收到 {values}")
        if not (Decimal("0") <= self.c and self.a_plus <= Decimal("100")):
            raise ValueError(f"Tier 阈值必须落在 [0, 100]，收到 {values}")


@dataclass(frozen=True, slots=True)
class PeerGroupAbsoluteLevel:
    """组内绝对水平。G-9 要求至少含 Sharpe 中位数与 Maximum Drawdown 中位数。

    None 表示组内没有任何有效值 —— 按 G-3 如实呈现 UNAVAILABLE，不填 0。
    """

    sharpe_median: Decimal | None
    max_drawdown_median: Decimal | None


@dataclass(frozen=True, slots=True)
class TierResult:
    """G-9 的结构化落地。

    peer_group_level 是【必填且无默认值】的字段：BR:1094-1096 把
    「Tier 必须与组内绝对水平同屏展示」写成强制要求，FC:157 更明说
    「仅展示 Tier 而不展示组内绝对水平，视为违反本条」。
    把它做成 dataclass 的必填字段，等于让「只输出 Tier」在类型层面
    构造不出来 —— 口头约定会被违反，构造函数不会。

    ⚠️ 不要给它加默认值，也不要在这里放一个「空的」PeerGroupAbsoluteLevel
    做兜底：那会让本条约束一夜之间退回口头约定。
    """

    share_class_id: int
    profile_id: str
    tier: FundTier | None
    percentile: Decimal | None
    rank: int | None
    n_effective: int
    total_score: Decimal | None
    classification_status: CrossSectionStatus
    peer_group_level: PeerGroupAbsoluteLevel


def _competition_ranks(values: Sequence[Decimal]) -> list[int]:
    """并列同名次、后续跳号：1, 2, 2, 4。输入必须已按降序排好。

    取 COMPETITION_RANK 而非 DENSE_RANK 的理由（FR:277-285）：
    DENSE_RANK 下 N 只基金的最大名次 < N，Percentile 公式
    (N − Rank)/(N − 1) 的分母与实际名次范围不匹配，
    「前 10%」实际包含的基金数会随并列数量漂移。
    """
    ranks: list[int] = []
    current = 0
    previous: Decimal | None = None
    for position, value in enumerate(values, start=1):
        if previous is None or value != previous:
            current = position
            previous = value
        ranks.append(current)
    return ranks


def _percentile(rank: int, n_effective: int) -> Decimal | None:
    """FR §7.1：Percentile = (N − Rank) / (N − 1) × 100。

    最优者 100、最劣者 0，与 Score 的 0–100 标尺方向一致，
    也使 Tier 阈值「前 5% ⇔ percentile ≥ 95」直观（FR:232）。
    N = 1 时分母为 0 → UNAVAILABLE（FR:234-240），不得返回 50 或 100。
    """
    if n_effective <= 1:
        return None
    return (
        Decimal(n_effective - rank) / Decimal(n_effective - 1) * Decimal(100)
    ).quantize(SCORE_QUANTUM, rounding=ROUND_HALF_UP)


def rank_within_peer_group(
    entries: Sequence[RankingEntry],
    *,
    peer_group_size: int,
    min_peer_group_size: int,
    tie_method: TieMethod = TieMethod.COMPETITION_RANK,
) -> list[RankingResult]:
    """一个 Peer Group 内、按 Profile 拆分的排名。

    G-10：同一 Peer Group 内多个 Evaluation Profile 时【按 Profile 拆分
    子排名】，不产出跨 Profile 统一排名 —— n_effective 因此是
    「本 Profile 内该指标的有效参与数」，不是全组的。

    metric_value 为 None 的成员【不产出排名行】（ERD §9.4：Ranking 对 Score
    的基数是 0..1，「评价合格 ≠ 排名合格」），也不计入 n_effective
    （FR:186-197：N 是有效参与数不是组规模）。它更不得按 0 参与排名（G-3）。

    n_effective < min_peer_group_size 时【仍然返回行】，只是 rank 与
    percentile 为 None、状态为 INSUFFICIENT_SAMPLE —— 「不落库会让历史查询
    无法区分『当时样本不足』与『当时根本没算』」（04-database-design:730）。
    """
    if tie_method is not TieMethod.COMPETITION_RANK:
        raise NotImplementedError(
            f"本 Plan 只实现 {TieMethod.COMPETITION_RANK}（D-20 裁定）；"
            f"收到 {tie_method}。另两个取值只是落库取值域。"
        )
    if peer_group_size <= 0:
        raise ValueError(f"peer_group_size 必须为正，收到 {peer_group_size}")

    # (metric_value, share_class_id) 的二元组：把 None 在这里就滤掉，
    # 之后的排序键里不再有 Optional —— 否则 -e.metric_value 在类型上是
    # 「可能对 None 取负」，mypy 会拦，而运行时也确实会在某天炸掉。
    by_profile: dict[str, list[tuple[Decimal, int]]] = {}
    for entry in entries:
        value = entry.metric_value
        if value is None:
            continue
        by_profile.setdefault(entry.profile_id, []).append((value, entry.share_class_id))

    results: list[RankingResult] = []
    for profile_id in sorted(by_profile):
        # 降序（越优越靠前，Rank = 1 最优，FR:201）；并列时按 share_class_id
        # 升序作为【显式声明的次级规则】，保证输出顺序确定（FR §8.4）。
        ordered = sorted(by_profile[profile_id], key=lambda pair: (-pair[0], pair[1]))
        n_effective = len(ordered)
        ranks = _competition_ranks([value for value, _ in ordered])
        insufficient = n_effective < min_peer_group_size or n_effective <= 1
        for (_, share_class_id), rank in zip(ordered, ranks, strict=True):
            percentile = None if insufficient else _percentile(rank, n_effective)
            results.append(
                RankingResult(
                    share_class_id=share_class_id,
                    profile_id=profile_id,
                    rank=None if insufficient else rank,
                    percentile=percentile,
                    n_effective=n_effective,
                    peer_group_size=peer_group_size,
                    ranking_status=(
                        CrossSectionStatus.INSUFFICIENT_SAMPLE
                        if insufficient
                        else CrossSectionStatus.NORMAL
                    ),
                    tie_method=tie_method,
                )
            )
    return results


def peer_group_absolute_level(
    sharpe_values: Sequence[Decimal], mdd_values: Sequence[Decimal]
) -> PeerGroupAbsoluteLevel:
    """组内绝对水平。调用方只传【有效】值，空序列 → None（不是 0）。"""
    return PeerGroupAbsoluteLevel(
        sharpe_median=median(sharpe_values) if sharpe_values else None,
        max_drawdown_median=median(mdd_values) if mdd_values else None,
    )


def assign_tier(
    ranking: RankingResult,
    *,
    total_score: Decimal | None,
    thresholds: TierThresholds,
    peer_group_level: PeerGroupAbsoluteLevel,
    min_peer_group_size: int,
) -> TierResult:
    """FC §12.1 的六步处理流程。

    ② percentile = UNAVAILABLE → 无 Tier（【不得默认为最低档】，FC §13）
    ③ n_effective < min → 不产出 Tier（FC §8.5 已定案，不是「低置信标记」）
    ④ 按分位区间判定，边界【上闭下开】：percentile >= 阈值归入较优档
    """
    insufficient = (
        ranking.percentile is None
        or ranking.n_effective < min_peer_group_size
        or ranking.ranking_status is CrossSectionStatus.INSUFFICIENT_SAMPLE
    )
    if insufficient:
        tier = None
        status = CrossSectionStatus.INSUFFICIENT_SAMPLE
    else:
        percentile = ranking.percentile
        assert percentile is not None       # 已由 insufficient 分支排除
        if percentile >= thresholds.a_plus:
            tier = FundTier.A_PLUS
        elif percentile >= thresholds.a:
            tier = FundTier.A
        elif percentile >= thresholds.b:
            tier = FundTier.B
        elif percentile >= thresholds.c:
            tier = FundTier.C
        else:
            tier = FundTier.D
        status = CrossSectionStatus.NORMAL

    return TierResult(
        share_class_id=ranking.share_class_id,
        profile_id=ranking.profile_id,
        tier=tier,
        percentile=ranking.percentile,
        rank=ranking.rank,
        n_effective=ranking.n_effective,
        total_score=total_score,
        classification_status=status,
        peer_group_level=peer_group_level,
    )
```

```python
# src/fip/strategy_library/ranking/__init__.py
"""排名 / 分位 / 分层。纯函数，阈值由调用方注入（BR:1075 严禁硬编码）。"""
```

- [ ] **Step 5: 落配置——三处共用同一配置源（G-7）**

```yaml
# config/policy/evaluation/v1.yaml —— 追加以下两节（保留既有的 mar / risk_free_rate）
peer_group:
  classification_level:
    value: L1
    status: PROVISIONAL
    source: "设计定案 D-7：IMP-TBD-2 的补齐，L2 分组会大量触发 INSUFFICIENT_SAMPLE"
  min_sample_size:
    # ⚠️ G-7：判定基数是 n_effective【不是】组规模，且标准化 / 排名 / 分层
    # 三处必须读【同一个】配置路径。三处各写一个 30 会在调参那天分叉，
    # 而分叉后的症状是「分位算出来了但 Tier 没产出」这种极难定位的不一致。
    # tests/fitness/test_single_config_source.py 断言全仓只有一处字面量。
    value: 30
    status: DECIDED
    source: "FR:340 已定案 2026-08-27：MIN_PEER_GROUP_SIZE = 30"
classification:
  tier_percentile_thresholds:
    # 已定案 · 2026-08-25（P0-2），FC §8.2 给出 >= / < 的明确边界。
    # 存的是 percentile 空间的阈值（95/80/50/20），不是「前 X%」（5/20/50/80）——
    # 两种表述互为补数，FC:214 称其为「一处极易出错的换算」，
    # tests/unit/test_fund_tier.py::test_top_percent_and_percentile_thresholds_
    # are_mutually_checkable 对这条换算做双向校验。
    a_plus:
      value: "95"
      status: DECIDED
      source: "BR:1084-1090 §16.3.1 已定案 2026-08-25；FC §8.2 边界 percentile >= 95"
    a:
      value: "80"
      status: DECIDED
      source: "同上：80 <= percentile < 95"
    b:
      value: "50"
      status: DECIDED
      source: "同上：50 <= percentile < 80"
    c:
      value: "20"
      status: DECIDED
      source: "同上：20 <= percentile < 50；percentile < 20 为 D"
```

```python
# tests/fitness/test_single_config_source.py
"""G-7：MIN_PEER_GROUP_SIZE 三处（标准化 / 排名 / 分层）必须同一配置源。

一条纯静态的检查：策略库里【不得】出现字面量 30 作为样本量阈值，
配置路径字符串在 src 中【只允许出现一次】（在 service 层解析配置的那一处）。
"""

import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "fip"
CONFIG_PATH_LITERAL = "peer_group.min_sample_size"


def test_min_sample_size_config_path_appears_exactly_once():
    hits = [
        f.relative_to(SRC)
        for f in SRC.rglob("*.py")
        if CONFIG_PATH_LITERAL in f.read_text(encoding="utf-8")
    ]
    assert len(hits) == 1, (
        f"配置路径 {CONFIG_PATH_LITERAL!r} 出现在 {hits} —— "
        "标准化 / 排名 / 分层三处必须经同一个解析点取值（G-7），"
        "各自 get 一次就是三个配置源，调参那天会分叉。"
    )


def test_strategy_library_contains_no_hardcoded_sample_threshold():
    """策略库是纯函数层：阈值只能【被注入】，不能自己知道。"""
    offenders = []
    for f in (SRC / "strategy_library").rglob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == 30:
                offenders.append((f.relative_to(SRC), node.lineno))
    assert not offenders, (
        f"strategy_library 出现字面量 30：{offenders}。"
        "MIN_PEER_GROUP_SIZE 必须由调用方从配置注入（BR:1075 严禁硬编码）。"
    )
```

- [ ] **Step 6: 运行确认通过**

Run: `.venv/bin/pytest tests/unit/test_ranking.py tests/unit/test_fund_tier.py tests/fitness -q`

Expected: 全部通过。`test_sub_rankings_are_split_by_profile`（G-10 的空洞成立锁）
与 `test_tier_cannot_be_constructed_without_peer_group_absolute_level`（G-9）必须在
PASSED 列表里。

Run: `.venv/bin/ruff check src tests && make typecheck`

Expected: 通过。

- [ ] **Step 7: 提交**

```bash
git add -A
git commit -m "feat(ranking): COMPETITION_RANK、分位与 Fund Tier 五档

Rank / n_effective / Percentile 三者一并产出（G-8）；n_effective 是有效参与数
不是组规模，指标 UNAVAILABLE 的成员不产出排名行也不计入 N。
样本不足仍落行但 rank/percentile 为 null（INSUFFICIENT_SAMPLE）。
Tier 阈值 95/80/50/20 上闭下开、由配置注入；n_effective < 30 不产出 Tier
而非给低置信标记。G-9 做成类型约束：TierResult 的组内绝对水平字段无默认值。
G-10 按 Profile 拆分子排名 —— M1 空洞成立，用双 Profile 测试锁住。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SZBJBiDWT8FHcx7NhkgcTD"
```

---

### Task 16: Eligibility Rules + B2 候选池快照（含 REJECTED）

> 依赖 Task 15。分两层：规则求值是纯函数（`strategy_library/universe`），
> B2 原子写入是编排（`services/fund_service`）。C-11：service 层只做编排与持久化，
> **不含投资策略规则** —— 条件怎么算、四种可投资性各自怎么处置，全在策略库里。

**Files:**
- Create: `src/fip/strategy_library/universe/__init__.py`
- Create: `src/fip/strategy_library/universe/rules.py`
- Create: `src/fip/services/fund_service/universe.py`
- Test: `tests/unit/test_eligibility_rules.py`
- Test: `tests/integration/test_universe_snapshot.py`
- Modify: `config/policy/evaluation/v1.yaml`（Selection Policy 的条件集与处理表）

**Interfaces:**

- Consumes:
  - `fip.strategy_library.score.subscore.ScoreStatus`（Task 14）
  - `fip.strategy_library.ranking.rank.FundTier`（Task 15）
  - `fip.services.fund_service.models.evaluation.{FundUniverseSnapshot, FundUniverseMember, SelectionConditionResult, PeerGroupSnapshot}`（Task 8）
  - `fip.services.data_service.eligibility.EligibilityStatus`（Plan-1；**只在 service 层消费**，策略库侧一律用 `str`，见 Step 4 说明）
- Produces:
  ```python
  # universe/rules.py
  class SelectionStatus(StrEnum): SELECTED; REJECTED
  class ConditionStatus(StrEnum): PASS; FAIL; UNAVAILABLE
  class Operator(StrEnum): GTE; LTE; IN; NOT_IN
  class EligibilityAction(StrEnum): ADMIT; ADMIT_WITH_CONSTRAINT; EXCLUDE

  SELECTABLE_FIELDS: frozenset[str]

  @dataclass(frozen=True, slots=True)
  class Condition:
      condition_id: str; field: str; operator: Operator
      threshold: Decimal | tuple[str, ...]

  @dataclass(frozen=True, slots=True)
  class CandidateFacts:
      share_class_id: int
      investment_eligibility: str | None
      evaluation_status: str | None
      data_completeness: Decimal | None
      total_score: Decimal | None
      percentile: Decimal | None
      fund_tier: str | None
      def value_of(self, field: str) -> object | None: ...

  @dataclass(frozen=True, slots=True)
  class ConditionResult:
      condition_id: str; condition_version: str; status: ConditionStatus
      actual_value: str | None; gap: Decimal | None

  @dataclass(frozen=True, slots=True)
  class SelectionOutcome:
      share_class_id: int; selection_status: SelectionStatus
      condition_results: tuple[ConditionResult, ...]
      constraint_note: str | None

  def evaluate_condition(condition: Condition, facts: CandidateFacts,
                         condition_version: str) -> ConditionResult: ...
  def evaluate_all(conditions: Sequence[Condition], facts: CandidateFacts,
                   condition_version: str) -> tuple[ConditionResult, ...]: ...
  def select(facts: CandidateFacts, conditions: Sequence[Condition],
             condition_version: str,
             eligibility_handling: Mapping[str, EligibilityAction]
             ) -> SelectionOutcome: ...

  # services/fund_service/universe.py
  class PeerGroupSnapshotMissing(RuntimeError): ...
  class UniverseSnapshotWriter:
      def __init__(self, session: Session) -> None: ...
      def write(self, *, decision_at: dt.date, peer_group_snapshot_id: int,
                selection_policy_version: str, condition_version: str,
                min_universe_size: int,
                outcomes: Sequence[SelectionOutcome],
                eligibility_refs: Mapping[int, tuple[dt.date, int] | None]
                ) -> int: ...
  ```

- [ ] **Step 1: 写失败的规则单元测试**

```python
# tests/unit/test_eligibility_rules.py
"""Eligibility Rules 求值 —— D-17 / G-11 的核心：【不得短路】。"""
from decimal import Decimal

import pytest

from fip.strategy_library.universe import rules
from fip.strategy_library.universe.rules import (
    CandidateFacts,
    Condition,
    ConditionStatus,
    EligibilityAction,
    Operator,
    SelectionStatus,
    evaluate_all,
    select,
)

CONDITIONS = (
    Condition("COND-ELIGIBILITY", "investment_eligibility", Operator.NOT_IN,
              ("EXIT_ONLY", "NOT_TRADABLE")),
    Condition("COND-EVAL-STATUS", "evaluation_status", Operator.IN,
              ("COMPLETED", "PARTIAL")),
    Condition("COND-COMPLETENESS", "data_completeness", Operator.GTE, Decimal("0.8")),
    Condition("COND-SCORE", "total_score", Operator.GTE, Decimal("60")),
)
HANDLING = {
    "FULLY_ELIGIBLE": EligibilityAction.ADMIT,
    "HOLD_ONLY": EligibilityAction.ADMIT_WITH_CONSTRAINT,
    "LIMITED": EligibilityAction.ADMIT_WITH_CONSTRAINT,
    "EXIT_ONLY": EligibilityAction.EXCLUDE,
    "NOT_TRADABLE": EligibilityAction.EXCLUDE,
}


def facts(**overrides) -> CandidateFacts:
    base = dict(
        share_class_id=1, investment_eligibility="FULLY_ELIGIBLE",
        evaluation_status="PARTIAL", data_completeness=Decimal("0.9"),
        total_score=Decimal("77"), percentile=Decimal("81"), fund_tier="A",
    )
    base.update(overrides)
    return CandidateFacts(**base)


# --- 不得短路 --------------------------------------------------------------

def test_all_conditions_are_evaluated_even_after_the_first_failure():
    """§14.4：短路求值会丢失信息 —— 无法回答「放宽某条件能新增多少基金」。

    第一个条件（可投资性）不通过时，其余三个【仍须求值】。
    """
    result = evaluate_all(
        CONDITIONS,
        facts(investment_eligibility="NOT_TRADABLE", total_score=Decimal("40")),
        condition_version="v1",
    )
    assert len(result) == len(CONDITIONS)
    by_id = {r.condition_id: r for r in result}
    assert by_id["COND-ELIGIBILITY"].status is ConditionStatus.FAIL
    # 后续条件不是占位符：它们各自反映了真实事实（两通过、一未通过）
    assert by_id["COND-EVAL-STATUS"].status is ConditionStatus.PASS
    assert by_id["COND-COMPLETENESS"].status is ConditionStatus.PASS
    assert by_id["COND-SCORE"].status is ConditionStatus.FAIL
    assert all(r.actual_value is not None for r in result)


def test_every_condition_is_actually_invoked_not_padded(monkeypatch):
    """比「结果条数对得上」更强的一条：证明每个条件都【真的被求值过】。

    只断言条数，一个「先短路、再用占位符补齐 K 行」的实现照样能通过。
    这里用 spy 记录实际调用序列。
    """
    calls: list[str] = []
    original = rules.evaluate_condition

    def spy(condition, facts_, condition_version):
        calls.append(condition.condition_id)
        return original(condition, facts_, condition_version)

    monkeypatch.setattr(rules, "evaluate_condition", spy)
    rules.evaluate_all(CONDITIONS, facts(investment_eligibility="NOT_TRADABLE"),
                       condition_version="v1")
    assert calls == [c.condition_id for c in CONDITIONS]


def test_gap_is_recorded_for_numeric_failures():
    """§14.2：不得只保存布尔值 —— 未通过时要记「实际值」与「差多少」。"""
    result = evaluate_all(CONDITIONS, facts(total_score=Decimal("52.5")),
                          condition_version="v1")
    score = next(r for r in result if r.condition_id == "COND-SCORE")
    assert score.status is ConditionStatus.FAIL
    assert score.actual_value == "52.5"
    assert score.gap == Decimal("7.5")


def test_missing_input_is_unavailable_not_a_silent_failure():
    """G-3：输入不可得 ≠ 输入为 0。两者必须在落库上可区分。"""
    result = evaluate_all(CONDITIONS, facts(total_score=None),
                          condition_version="v1")
    score = next(r for r in result if r.condition_id == "COND-SCORE")
    assert score.status is ConditionStatus.UNAVAILABLE
    assert score.actual_value is None
    assert score.gap is None


def test_unknown_field_raises_instead_of_evaluating_to_false():
    bad = (Condition("COND-X", "fund_size", Operator.GTE, Decimal("1")),)
    with pytest.raises(KeyError, match="fund_size"):
        evaluate_all(bad, facts(), condition_version="v1")


# --- 四种可投资性的四种动作 -------------------------------------------------

def test_fully_eligible_is_admitted_without_constraint():
    outcome = select(facts(), CONDITIONS, "v1", HANDLING)
    assert outcome.selection_status is SelectionStatus.SELECTED
    assert outcome.constraint_note is None


@pytest.mark.parametrize("status", ["HOLD_ONLY", "LIMITED"])
def test_hold_only_and_limited_are_admitted_with_a_constraint_note(status: str):
    """§9.2：不可建仓 ≠ 移出 Universe。

    直接移出会让组合中已持有的该基金被优化器判定为「不在可选集合」，
    可能导致被强制清仓。正确做法是保留在池内并标注不可建仓。
    """
    outcome = select(facts(investment_eligibility=status), CONDITIONS, "v1", HANDLING)
    assert outcome.selection_status is SelectionStatus.SELECTED
    assert outcome.constraint_note is not None
    assert status in outcome.constraint_note


def test_exit_only_does_not_enter_the_pool():
    """§9.3 定案 2026-08-27 推翻了原表格：EXIT_ONLY 基金【不入池】，

    但已持仓的不强制卖出（那是 portfolio 域的事，不在这里表达）。
    """
    outcome = select(facts(investment_eligibility="EXIT_ONLY"),
                     CONDITIONS, "v1", HANDLING)
    assert outcome.selection_status is SelectionStatus.REJECTED
    assert len(outcome.condition_results) == len(CONDITIONS)


def test_not_tradable_is_excluded_but_leaves_a_trace():
    """§19 Edge Case：高分基金 NOT_TRADABLE → 排除，但【在被拒清单中记录】，

    「避免消失得无声无息」。
    """
    outcome = select(facts(investment_eligibility="NOT_TRADABLE",
                           total_score=Decimal("99")),
                     CONDITIONS, "v1", HANDLING)
    assert outcome.selection_status is SelectionStatus.REJECTED
    reason = next(r for r in outcome.condition_results
                  if r.condition_id == "COND-ELIGIBILITY")
    assert reason.status is ConditionStatus.FAIL
    assert reason.actual_value == "NOT_TRADABLE"


def test_unknown_eligibility_value_raises_rather_than_defaulting_to_admit():
    """处理表缺一个取值时必须炸，不得默认放行。

    默认放行会让一个新增的可投资性状态静默地全部入池。
    """
    with pytest.raises(KeyError, match="SUSPENDED"):
        select(facts(investment_eligibility="SUSPENDED"), CONDITIONS, "v1", HANDLING)


def test_missing_eligibility_row_is_rejected_and_recorded():
    """PIT 下 available_at <= decision_at 取不到任何一版可投资性时。"""
    outcome = select(facts(investment_eligibility=None), CONDITIONS, "v1", HANDLING)
    assert outcome.selection_status is SelectionStatus.REJECTED
    reason = next(r for r in outcome.condition_results
                  if r.condition_id == "COND-ELIGIBILITY")
    assert reason.status is ConditionStatus.UNAVAILABLE
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/pytest tests/unit/test_eligibility_rules.py -q`

Expected: `ModuleNotFoundError: No module named 'fip.strategy_library.universe'`。

- [ ] **Step 3: 实现规则求值（纯函数）**

```python
# src/fip/strategy_library/universe/rules.py
"""Eligibility Rules 求值。

⚠️ 与 `Investment Eligibility` 严格区分（03-data/02 §14 用「严格分离」四个字点名）：
  · `Investment Eligibility` 是【数据域的客观事实】——这只份额此刻能不能建仓，
    由 data-service 从 Lifecycle + 申赎 + 流动性派生，不含任何策略配置。
  · `Eligibility Rules` 是【版本化的策略配置】，属 Strategy Version 第 3 项。
  前者是后者【七个筛选维度之一】，不是它的同义词。

本模块只做后者，且【不 import 前者的枚举】：EligibilityStatus 定义在
fip.services.data_service.eligibility 里，而依赖方向是 services → strategy_library
单向，反向 import 是设计错误。因此这里一律用 str，取值域由调用方给的
eligibility_handling 映射表钉住（缺键即抛 KeyError，不默认放行），
并由 Task 17 的一条 service 层测试断言该映射的键集恰好等于 EligibilityStatus
的全部取值 —— 枚举与配置的漂移在【允许 import 枚举的那一层】被抓住。
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class SelectionStatus(StrEnum):
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"


class ConditionStatus(StrEnum):
    """PASS / FAIL 之外必须有第三个值。

    只有 PASS / FAIL 就无法区分「评估了，不通过」与「根本没法评估」——
    后者在输入缺失（如策略 A 下没有 total_score）时大量出现，
    把它记成 FAIL 等于宣称「我们量过了，它不达标」，那是编造证据。
    UNAVAILABLE 【不算通过】（无法证实达标就不得入池），但如实留痕。
    """

    PASS = "PASS"
    FAIL = "FAIL"
    UNAVAILABLE = "UNAVAILABLE"


class Operator(StrEnum):
    GTE = "GTE"
    LTE = "LTE"
    IN = "IN"
    NOT_IN = "NOT_IN"


class EligibilityAction(StrEnum):
    ADMIT = "ADMIT"
    ADMIT_WITH_CONSTRAINT = "ADMIT_WITH_CONSTRAINT"
    EXCLUDE = "EXCLUDE"


# 可作为条件左值的字段白名单。不用裸 getattr：配置里写错一个字段名会
# 悄悄取到方法对象或抛 AttributeError，而这里要的是一条明确的错误。
SELECTABLE_FIELDS = frozenset({
    "investment_eligibility",
    "evaluation_status",
    "data_completeness",
    "total_score",
    "percentile",
    "fund_tier",
})


@dataclass(frozen=True, slots=True)
class Condition:
    condition_id: str
    field: str
    operator: Operator
    threshold: Decimal | tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandidateFacts:
    """一只候选份额在 decision_at 的全部可筛字段。None 一律表示【不可得】。"""

    share_class_id: int
    investment_eligibility: str | None
    evaluation_status: str | None
    data_completeness: Decimal | None
    total_score: Decimal | None
    percentile: Decimal | None
    fund_tier: str | None

    def value_of(self, field: str) -> object | None:
        if field not in SELECTABLE_FIELDS:
            raise KeyError(
                f"条件引用了不可筛字段 {field!r}；可用字段：{sorted(SELECTABLE_FIELDS)}"
            )
        return getattr(self, field)


@dataclass(frozen=True, slots=True)
class ConditionResult:
    """§14.2：不得只保存布尔值。至少要有条件标识 + 通过与否 + 实际值 +

    （未通过时）差距。condition_version 一并存 —— 条件集本身会变更，
    不记录版本则历史结果无法解释（04-database-design:801）。
    """

    condition_id: str
    condition_version: str
    status: ConditionStatus
    actual_value: str | None
    gap: Decimal | None


@dataclass(frozen=True, slots=True)
class SelectionOutcome:
    share_class_id: int
    selection_status: SelectionStatus
    condition_results: tuple[ConditionResult, ...]
    constraint_note: str | None


def evaluate_condition(
    condition: Condition, facts: CandidateFacts, condition_version: str
) -> ConditionResult:
    """单个条件。输入不可得 → UNAVAILABLE（不是 FAIL，也不是 PASS）。"""
    value = facts.value_of(condition.field)
    if value is None:
        return ConditionResult(condition.condition_id, condition_version,
                               ConditionStatus.UNAVAILABLE, None, None)

    if condition.operator in (Operator.IN, Operator.NOT_IN):
        if not isinstance(condition.threshold, tuple):
            raise TypeError(
                f"{condition.condition_id}：{condition.operator} 的阈值必须是取值元组"
            )
        member = str(value) in condition.threshold
        ok = member if condition.operator is Operator.IN else not member
        return ConditionResult(condition.condition_id, condition_version,
                               ConditionStatus.PASS if ok else ConditionStatus.FAIL,
                               str(value), None)

    if not isinstance(value, Decimal) or not isinstance(condition.threshold, Decimal):
        raise TypeError(
            f"{condition.condition_id}：{condition.operator} 要求 Decimal 左值与阈值，"
            f"收到 {type(value).__name__} / {type(condition.threshold).__name__}"
        )
    ok = (
        value >= condition.threshold
        if condition.operator is Operator.GTE
        else value <= condition.threshold
    )
    gap = None if ok else abs(condition.threshold - value)
    return ConditionResult(condition.condition_id, condition_version,
                           ConditionStatus.PASS if ok else ConditionStatus.FAIL,
                           str(value), gap)


def evaluate_all(
    conditions: Sequence[Condition], facts: CandidateFacts, condition_version: str
) -> tuple[ConditionResult, ...]:
    """全部条件【一律求值】，不得短路（D-17 / G-11 / §14.4）。

    ⚠️ 这是本 Plan 最容易被「优化」掉的一处：加一行
    `if result.status is ConditionStatus.FAIL: break` 能省下几次比较，
    代价是永远无法回答「放宽某条件能新增多少基金」，且无法区分
    「通过了」与「根本没评估」——后者会在条件集变更时大量出现。
    这里刻意写成对全集的推导式，不留插入 break 的位置；
    tests/unit/test_eligibility_rules.py 用 spy 断言每个条件都真的被调用过。

    通过模块级函数 evaluate_condition 调用（而不是内联），是为了让那条
    spy 测试能挂上去 —— 这不是多余的间接层，它是可测性的一部分。
    """
    return tuple(
        evaluate_condition(condition, facts, condition_version)
        for condition in conditions
    )


def select(
    facts: CandidateFacts,
    conditions: Sequence[Condition],
    condition_version: str,
    eligibility_handling: Mapping[str, EligibilityAction],
) -> SelectionOutcome:
    """一只候选的入池判定。§18.1 的 ③⑤ 两步。

    可投资性【本身就是一个条件】（§8.1 七个 Hard Filter 维度的最后一行），
    因此它走与其他条件相同的求值路径、留同样的痕；处理表只额外决定
    「入池的那些要不要带约束标注」。这样 EXIT_ONLY / NOT_TRADABLE
    的排除原因会出现在 selection_condition_result 里，而不是变成一个
    没有条件行支撑的、凭空的 REJECTED。
    """
    results = evaluate_all(conditions, facts, condition_version)
    passed = all(r.status is ConditionStatus.PASS for r in results)

    note: str | None = None
    status = facts.investment_eligibility
    if status is not None:
        try:
            action = eligibility_handling[status]
        except KeyError:
            raise KeyError(
                f"investment_eligibility={status!r} 不在处理表中："
                f"{sorted(eligibility_handling)}。新增取值必须显式登记处理方式，"
                "默认放行会让它静默全部入池。"
            ) from None
        if action is EligibilityAction.ADMIT_WITH_CONSTRAINT:
            note = f"{status}：入池并标注约束，建仓/加仓限制由 portfolio 域施加"

    return SelectionOutcome(
        share_class_id=facts.share_class_id,
        selection_status=SelectionStatus.SELECTED if passed else SelectionStatus.REJECTED,
        condition_results=results,
        constraint_note=note if passed else None,
    )
```

```python
# src/fip/strategy_library/universe/__init__.py
"""候选池准入规则。纯函数：不读配置、不碰数据库、不 import services。"""
```

- [ ] **Step 4: 写失败的 B2 原子性集成测试**

```python
# tests/integration/test_universe_snapshot.py
"""B2 快照原子写入 —— D-18 / D-17 / D-15。"""
import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import func, select as sa_select

from fip.strategy_library.universe.rules import (
    ConditionResult,
    ConditionStatus,
    SelectionOutcome,
    SelectionStatus,
)
from fip.services.fund_service.models.evaluation import (
    FundUniverseMember,
    FundUniverseSnapshot,
    SelectionConditionResult,
)
from fip.services.fund_service.universe import (
    PeerGroupSnapshotMissing,
    UniverseSnapshotWriter,
)

pytestmark = pytest.mark.integration

DECISION_AT = dt.date(2026, 8, 31)
CONDITION_IDS = ("COND-ELIGIBILITY", "COND-EVAL-STATUS", "COND-COMPLETENESS",
                 "COND-SCORE")


def outcome(share_class_id: int, status: SelectionStatus) -> SelectionOutcome:
    """每只候选【一律】带全部 4 个条件结果，含被拒的那些。"""
    return SelectionOutcome(
        share_class_id=share_class_id,
        selection_status=status,
        condition_results=tuple(
            ConditionResult(
                condition_id=cid, condition_version="v1",
                status=(ConditionStatus.FAIL
                        if status is SelectionStatus.REJECTED and cid == CONDITION_IDS[0]
                        else ConditionStatus.PASS),
                actual_value="X", gap=None,
            )
            for cid in CONDITION_IDS
        ),
        constraint_note=None,
    )


def test_rejected_members_and_all_conditions_are_persisted(
    db_session, committed_peer_group_snapshot, share_class_ids
):
    """D-17：REJECTED 成员与【全部】条件结果落库。

    「若只存入池成员 → 无法验证是否有基金被错误排除 →
      而错误排除正是幸存者偏差的表现形式」（03-erd §9.2）。
    """
    selected, rejected = share_class_ids[0], share_class_ids[1]
    writer = UniverseSnapshotWriter(db_session)
    snapshot_id = writer.write(
        decision_at=DECISION_AT,
        peer_group_snapshot_id=committed_peer_group_snapshot,
        selection_policy_version="sel-v1", condition_version="v1",
        min_universe_size=1,
        outcomes=[outcome(selected, SelectionStatus.SELECTED),
                  outcome(rejected, SelectionStatus.REJECTED)],
        eligibility_refs={selected: None, rejected: None},
    )
    members = db_session.execute(
        sa_select(FundUniverseMember).where(
            FundUniverseMember.fund_universe_snapshot_id == snapshot_id)
    ).scalars().all()
    assert {m.selection_status for m in members} == {"SELECTED", "REJECTED"}

    per_member = db_session.execute(
        sa_select(SelectionConditionResult.fund_universe_member_id,
                  func.count()).group_by(SelectionConditionResult.fund_universe_member_id)
    ).all()
    assert {count for _, count in per_member} == {len(CONDITION_IDS)}, (
        "有成员的条件结果行数不等于条件集大小 —— 求值被短路，或只存了未通过项"
    )


def test_b2_is_atomic_nothing_survives_a_partial_write(
    db_session, committed_peer_group_snapshot, share_class_ids, monkeypatch
):
    """D-18 / spec §3.2：B2 写入不完整 → 整体回滚，本次决策视为未产生。"""
    from fip.services.fund_service import universe as universe_module

    original = universe_module.UniverseSnapshotWriter._write_condition_results
    calls = {"n": 0}

    def explode(self, member_id, results):
        calls["n"] += 1
        if calls["n"] == 2:                      # 第二个成员写到一半炸
            raise RuntimeError("模拟写入中断")
        return original(self, member_id, results)

    monkeypatch.setattr(
        universe_module.UniverseSnapshotWriter, "_write_condition_results", explode
    )
    writer = UniverseSnapshotWriter(db_session)
    with pytest.raises(RuntimeError, match="模拟写入中断"):
        writer.write(
            decision_at=DECISION_AT,
            peer_group_snapshot_id=committed_peer_group_snapshot,
            selection_policy_version="sel-v1", condition_version="v1",
            min_universe_size=1,
            outcomes=[outcome(share_class_ids[0], SelectionStatus.SELECTED),
                      outcome(share_class_ids[1], SelectionStatus.REJECTED)],
            eligibility_refs={i: None for i in share_class_ids[:2]},
        )
    assert db_session.execute(
        sa_select(func.count()).select_from(FundUniverseSnapshot)
    ).scalar_one() == 0
    assert db_session.execute(
        sa_select(func.count()).select_from(FundUniverseMember)
    ).scalar_one() == 0
    assert db_session.execute(
        sa_select(func.count()).select_from(SelectionConditionResult)
    ).scalar_one() == 0


def test_b2_requires_a_committed_b1_snapshot_id(db_session, share_class_ids):
    """B1 → B2 的顺序依赖：B2 只能引用一个【已提交的】 B1 快照 ID。

    「三个边界各自原子，且按顺序依赖。任一边界写入失败，
      其下游边界不会产生」（01-system-architecture:855）。
    """
    writer = UniverseSnapshotWriter(db_session)
    with pytest.raises(PeerGroupSnapshotMissing):
        writer.write(
            decision_at=DECISION_AT, peer_group_snapshot_id=987654321,
            selection_policy_version="sel-v1", condition_version="v1",
            min_universe_size=1,
            outcomes=[outcome(share_class_ids[0], SelectionStatus.SELECTED)],
            eligibility_refs={share_class_ids[0]: None},
        )
    assert db_session.execute(
        sa_select(func.count()).select_from(FundUniverseSnapshot)
    ).scalar_one() == 0


def test_member_stores_a_version_reference_not_a_value_copy():
    """D-15：fund_universe_member.investment_eligibility 存【版本引用】。

    存取值副本会引入第二份真值，两者一旦分叉无法判定谁对 ——
    这正是 Plan-1 在 adjusted_nav 标量列上花三轮才想明白的教训。
    本测试对着表结构断言，因此它在任何实现改动下都不会失真。
    """
    columns = set(FundUniverseMember.__table__.columns.keys())
    assert "investment_eligibility" not in columns, (
        "出现了取值副本列。可投资性必须以 "
        "(share_class_id, eligibility_effective_at, eligibility_version) "
        "三元组引用 fund.investment_eligibility（D-15）"
    )
    assert {"eligibility_effective_at", "eligibility_version"} <= columns


def test_undersized_universe_is_recorded_then_blocked(
    db_session, committed_peer_group_snapshot, share_class_ids
):
    """规模不足：快照【照常留痕】并标 INSUFFICIENT_UNIVERSE，由调用方阻断。

    与 fund_ranking 的 INSUFFICIENT_SAMPLE 同理 ——「当时池子太小」
    本身是需要留存的事实；不落库会让历史查询无法区分它与「当时没跑」。
    但它【不得】被当作一个可用的 Universe 继续下发（§19：显式失败并阻断）。
    """
    writer = UniverseSnapshotWriter(db_session)
    snapshot_id = writer.write(
        decision_at=DECISION_AT,
        peer_group_snapshot_id=committed_peer_group_snapshot,
        selection_policy_version="sel-v1", condition_version="v1",
        min_universe_size=30,
        outcomes=[outcome(share_class_ids[0], SelectionStatus.SELECTED)],
        eligibility_refs={share_class_ids[0]: None},
    )
    snapshot = db_session.get(FundUniverseSnapshot, snapshot_id)
    assert snapshot.universe_status == "INSUFFICIENT_UNIVERSE"
    assert snapshot.selected_count == 1
```

```python
# tests/integration/conftest.py —— 追加两个夹具（本任务新增）
import datetime as dt

import pytest

from fip.services.data_service.models.fund import Fund, FundShareClass


@pytest.fixture()
def share_class_ids(db_session) -> list[int]:
    """三只可引用的份额类别。FK 目标必须真实存在，不能用假 id。"""
    fund = Fund(product_name="测试产品")
    db_session.add(fund)
    db_session.flush()
    ids = []
    for code in ("A", "C", "E"):
        share_class = FundShareClass(fund_id=fund.id, share_class_code=code,
                                     display_name=f"测试产品{code}")
        db_session.add(share_class)
        db_session.flush()
        ids.append(share_class.id)
    return ids


@pytest.fixture()
def committed_peer_group_snapshot(db_session) -> int:
    """一个【已提交】的 B1 快照 id。

    db_session 以 join_transaction_mode="create_savepoint" 运行，
    这里的 commit 只释放/重开一个 SAVEPOINT，外层事务仍由 fixture 兜底回滚
    （见 tests/conftest.py 的说明）—— 因此对被测代码而言它是「已提交的」，
    而测试之间仍互不污染。
    """
    from fip.services.fund_service.models.evaluation import PeerGroupSnapshot

    snapshot = PeerGroupSnapshot(
        classification_scheme="AKSHARE_FUND_TYPE", classification_code="混合型",
        base_currency="CNY", effective_at=dt.date(2026, 8, 31), version=1,
        member_count=3, classification_policy_version="cls-v1",
    )
    db_session.add(snapshot)
    db_session.commit()
    return snapshot.id
```

- [ ] **Step 5: 运行确认失败**

Run: `.venv/bin/pytest tests/integration/test_universe_snapshot.py -q -m integration`

Expected: `ModuleNotFoundError: No module named 'fip.services.fund_service.universe'`。
若 Task 8 的建表已完成而 `fund_universe_member` 上没有
`eligibility_effective_at` / `eligibility_version` 两列，
`test_member_stores_a_version_reference_not_a_value_copy` 会以 AssertionError 失败 ——
那说明 Task 8 漏了 D-15 的落地形态，回去补迁移，**不要在这里改测试**。

- [ ] **Step 6: 实现 B2 原子写入**

```python
# src/fip/services/fund_service/universe.py
"""B2 · Universe Snapshot 的原子写入。

一致性边界（01-system-architecture §10.3）：
    B1 (Peer Group Snapshot)  ← 原子写入，产生快照 ID
            ↓ 被引用
    B2 (Universe Snapshot)    ← 原子写入，引用【已提交的】 B1 快照 ID

B1 与 B2 【不要求同一事务】——文档说的是「三个边界各自原子，且按顺序依赖」。
B2 只需在自己的事务内引用一个已提交的 B1 快照 ID。

本模块只做编排与持久化：入池与否、条件怎么算，全部在
strategy_library/universe/rules.py 里（C-11）。
"""

import datetime as dt
from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.strategy_library.universe.rules import (
    ConditionResult,
    SelectionOutcome,
    SelectionStatus,
)
from fip.services.fund_service.models.evaluation import (
    FundUniverseMember,
    FundUniverseSnapshot,
    PeerGroupSnapshot,
    SelectionConditionResult,
)


class PeerGroupSnapshotMissing(RuntimeError):
    """引用了一个不存在的 B1 快照 ID。

    响亮失败而不是建一个悬空引用：FR-PEER-002 要求「未留存快照的时点，
    系统必须拒绝提供推算结果」，一个引用不到 B1 的 B2 正是那种时点。
    """


class UniverseSnapshotWriter:
    def __init__(self, session: Session) -> None:
        self._session = session

    def write(
        self,
        *,
        decision_at: dt.date,
        peer_group_snapshot_id: int,
        selection_policy_version: str,
        condition_version: str,
        min_universe_size: int,
        outcomes: Sequence[SelectionOutcome],
        eligibility_refs: Mapping[int, tuple[dt.date, int] | None],
    ) -> int:
        """写一次 B2。返回快照 id。

        事务范围（digest §4.3）：`fund_universe_snapshot` 1 行
        + `fund_universe_member` M 行（【含 REJECTED】，M ≈ 候选集规模而非入池数）
        + `selection_condition_result` M × K 行（K = 条件数，【存全部条件】），
        一并提交。任一步失败则整体回滚，本次决策视为未产生。

        eligibility_refs 传的是【版本引用】而不是取值副本（D-15）：
        (effective_at, version) 二元组，与成员自己的 share_class_id 组成
        指向 fund.investment_eligibility 的复合外键。None 表示该时点
        按 available_at <= decision_at 取不到任何一版 —— 如实留空，
        不得回填一个「最近的」版本（那是前视偏差）。
        """
        if self._session.execute(
            select(PeerGroupSnapshot.id).where(
                PeerGroupSnapshot.id == peer_group_snapshot_id)
        ).scalar_one_or_none() is None:
            raise PeerGroupSnapshotMissing(
                f"B1 快照 id={peer_group_snapshot_id} 不存在或尚未提交；"
                "B2 必须引用一个已提交的 B1 快照（01-system-architecture §10.3）"
            )

        selected = sum(
            1 for o in outcomes if o.selection_status is SelectionStatus.SELECTED
        )
        with self._session.begin_nested():
            snapshot = FundUniverseSnapshot(
                decision_at=decision_at,
                peer_group_snapshot_id=peer_group_snapshot_id,
                selection_policy_version=selection_policy_version,
                condition_version=condition_version,
                candidate_count=len(outcomes),
                selected_count=selected,
                universe_status=(
                    "NORMAL" if selected >= min_universe_size
                    else "INSUFFICIENT_UNIVERSE"
                ),
            )
            self._session.add(snapshot)
            self._session.flush()

            # 排序钉死写入顺序：同一批 outcomes 无论以什么顺序传进来，
            # 落库的行顺序都相同，便于逐行比对两次运行的结果（G-2）。
            for outcome in sorted(outcomes, key=lambda o: o.share_class_id):
                ref = eligibility_refs.get(outcome.share_class_id)
                member = FundUniverseMember(
                    fund_universe_snapshot_id=snapshot.id,
                    share_class_id=outcome.share_class_id,
                    selection_status=outcome.selection_status.value,
                    constraint_note=outcome.constraint_note,
                    eligibility_effective_at=None if ref is None else ref[0],
                    eligibility_version=None if ref is None else ref[1],
                )
                self._session.add(member)
                self._session.flush()
                self._write_condition_results(member.id, outcome.condition_results)
        return snapshot.id

    def _write_condition_results(
        self, member_id: int, results: Sequence[ConditionResult]
    ) -> None:
        """逐条件明细。【全部条件】都写，不只写未通过项（D-17）。

        「只存未通过项 → 无法回答『这只基金通过了哪些条件』，
          也无法区分『通过了』与『根本没评估』，
          而后者会在条件集变更时大量出现」（04-database-design §10.3.1）。
        """
        for result in results:
            self._session.add(
                SelectionConditionResult(
                    fund_universe_member_id=member_id,
                    condition_id=result.condition_id,
                    condition_version=result.condition_version,
                    condition_status=result.status.value,
                    actual_value=result.actual_value,
                    gap=result.gap,
                )
            )
        self._session.flush()
```

- [ ] **Step 7: 落 Selection Policy 配置**

```yaml
# config/policy/evaluation/v1.yaml —— 继续追加
selection:
  universe_strategy:
    # digest §2.6：spec 说了「三种构成策略」推到 M2，但【全仓没有一处写下
    # 「策略 A」三个字】。M1 做的是「仅 Eligibility Rules」= 策略 A，
    # 这是推断不是引用，故标 PROVISIONAL。策略 A 下评分字段为空是正常情况，
    # 不构成留痕缺失（05-fund-selection:147）。
    value: A
    status: PROVISIONAL
    source: "digest §2.6 / BLOCK-3：spec 未点名 M1 用哪种构成策略"
  min_universe_size:
    value: 30
    status: PROVISIONAL
    source: "05-fund-selection §11.1 推荐默认（与 MIN_PEER_GROUP_SIZE 同值），业务方可改"
  data_completeness_floor:
    value: "0.8"
    status: DECIDED
    source: "05-fund-selection:121 已定案：沿用 03-data/03-data-quality DQ-2 的 0.8，本域不单独设值"
  investment_eligibility_handling:
    FULLY_ELIGIBLE:
      value: ADMIT
      status: DECIDED
      source: "05-fund-selection §9.3"
    HOLD_ONLY:
      value: ADMIT_WITH_CONSTRAINT
      status: DECIDED
      source: "§9.2：不可建仓 ≠ 移出 Universe，否则已持仓可能被优化器强制清仓"
    LIMITED:
      value: ADMIT_WITH_CONSTRAINT
      status: DECIDED
      source: "§9.3"
    EXIT_ONLY:
      value: EXCLUDE
      status: DECIDED
      source: "§9.3 已定案 2026-08-27：EXIT_ONLY 不入池（推翻了 §9.3 表格原值）"
    NOT_TRADABLE:
      value: EXCLUDE
      status: DECIDED
      source: "§9.3；§19 Edge Case 要求排除但在被拒清单留痕"
```

- [ ] **Step 8: 运行确认通过**

Run: `.venv/bin/pytest tests/unit/test_eligibility_rules.py tests/integration/test_universe_snapshot.py -v -m "integration or not integration"`

Expected: 全部通过。特别核对
`test_every_condition_is_actually_invoked_not_padded`（不短路的强证据）与
`test_b2_is_atomic_nothing_survives_a_partial_write`（D-18）在 PASSED 列表里。

Run: `.venv/bin/alembic -x db=dev revision --autogenerate -m "probe" --sql | head -40`

Expected: 报告零操作（G-16）。本任务不建表，若这里出现任何 ADD/DROP，
说明 Task 8 的 ORM 与迁移不一致，回 Task 8 修，**不要在本任务加迁移**。
探针产生的临时 revision 文件用完即删。

- [ ] **Step 9: 提交**

```bash
git add -A
git commit -m "feat(universe): Eligibility Rules 求值与 B2 候选池快照

条件求值不得短路：全部条件一律求值并落库，含 REJECTED 成员（D-17/G-11），
由 spy 测试证明每个条件都真的被调用过，而不是短路后补齐占位行。
四种可投资性四种动作：FULLY_ELIGIBLE 入池、HOLD_ONLY/LIMITED 入池并标注约束、
EXIT_ONLY 不入池、NOT_TRADABLE 排除但在被拒清单留痕。
投资性以 (share_class_id, effective_at, version) 版本引用而非取值副本（D-15）。
B2 原子写入并引用已提交的 B1 快照 ID，写入不完整整体回滚（D-18）。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SZBJBiDWT8FHcx7NhkgcTD"
```

---

### Task 17: `factor_service` / `fund_service` 装配 + SB-1 适应度测试

> 依赖 Task 16。本任务把 Task 9–16 的纯函数接到 Plan-1 的 PIT 端口与数据库上，
> 并补上 Plan-1 最终评审点名「静默缺席」的 SB-1。
>
> **SB-1 在 M1 是空洞的**：只有一个写入方（`IngestService`）时，「每个 schema
> 写入权唯一」永远成立。Plan-2 引入 `factor_service`（写 `factor`）与
> `fund_service`（写 `evaluation`）之后，它**第一次有真实约束力** ——
> 而恰恰在这一刻，最省事的写法（fund_service 顺手把因子值补写一行）
> 会永久地把两个 schema 的写入权搅在一起。

**Files:**
- Create: `src/fip/platform/config/evaluation_policy.py`
- Create: `src/fip/services/factor_service/compute.py`
- Create: `src/fip/services/factor_service/repositories/__init__.py`
- Create: `src/fip/services/factor_service/repositories/factor_value.py`
- Create: `src/fip/services/fund_service/evaluate.py`
- Test: `tests/fitness/test_schema_write_ownership.py`
- Test: `tests/integration/test_schema_write_ownership.py`
- Test: `tests/integration/test_evaluation_pipeline.py`

**Interfaces:**

- Consumes:
  - `fip.platform.decision_data.pit.PitDataContext`、`fip.platform.decision_data.context.DecisionExecutionContext`（Plan-1）
  - `fip.platform.config.loader.load_config_file` / `ConfigSet`（Plan-1）
  - `fip.strategy_library.factor.compute.compute_factor`、`FactorInput`、`FactorResult`（Task 9）
  - `fip.strategy_library.factor.normalize.percentile_rank`（Task 12）
  - `fip.strategy_library.score.subscore.*`（Task 14）
  - `fip.strategy_library.ranking.rank.*`（Task 15）
  - `fip.strategy_library.universe.rules.*`、`fip.services.fund_service.universe.UniverseSnapshotWriter`（Task 16）
  - `fip.services.data_service.eligibility.EligibilityStatus`（Plan-1，仅用于配置校验）
- Produces:
  ```python
  # platform/config/evaluation_policy.py
  @dataclass(frozen=True, slots=True)
  class EvaluationPolicy:
      min_peer_group_size: int
      classification_level: str
      tier_thresholds: TierThresholds
      min_universe_size: int
      data_completeness_floor: Decimal
      investment_eligibility_handling: Mapping[str, EligibilityAction]
      provisional_used: tuple[str, ...]
      @classmethod
      def load(cls, config: ConfigSet) -> "EvaluationPolicy": ...

  # services/factor_service/compute.py
  WRITES_SCHEMAS: frozenset[str]          # frozenset({"factor"})
  @dataclass(frozen=True, slots=True)
  class FactorRunResult:
      run_id: int; computed: int; unavailable: int
  class FactorComputeService:
      def __init__(self, session: Session, policy: EvaluationPolicy) -> None: ...
      def run(self, context: DecisionExecutionContext,
              peer_group_snapshot_id: int, window: str) -> FactorRunResult: ...

  # services/factor_service/repositories/factor_value.py
  class FactorValueReader:
      def __init__(self, session: Session) -> None: ...
      def normalized_factors(self, run_id: int
                             ) -> dict[int, dict[str, NormalizedFactor]]: ...

  # services/fund_service/evaluate.py
  WRITES_SCHEMAS: frozenset[str]          # frozenset({"evaluation"})
  @dataclass(frozen=True, slots=True)
  class EvaluationRunResult:
      scored: int; ranked: int; tiered: int; universe_snapshot_id: int | None
  class FundEvaluationService:
      def __init__(self, session: Session, policy: EvaluationPolicy,
                   profile: EvaluationProfile) -> None: ...
      def run(self, context: DecisionExecutionContext, factor_run_id: int,
              peer_group_snapshot_id: int) -> EvaluationRunResult: ...
  ```

- [ ] **Step 1: 写失败的 SB-1 静态适应度测试**

```python
# tests/fitness/test_schema_write_ownership.py
"""SB-1：每个 schema 的写入权唯一。

Plan-1 的最终评审点名这条约束「既没有实现，也没有出现在『明确不覆盖』
清单里 —— 它是静默缺席的」。M1 只有一个写入方时它空洞；Plan-2 引入
factor_service 与 fund_service 之后第一次有真实约束力。

本文件是【静态】那一半：谁定义了哪个 schema 的 ORM 模型。
【动态】那一半在 tests/integration/test_schema_write_ownership.py ——
它挂 before_flush 事件监听器，记录每个 service 实际 flush 了哪些 schema
的对象。两条缺一不可：静态检查抓不到「fund_service import 了
factor 的 model 并往里写」，动态检查抓不到「今天没走到那条代码路径」。
"""

import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "fip"
SERVICES = SRC / "services"

# spec §2.3 / G-13 的写入权分配。左边是 schema，右边是【唯一】写入方。
EXPECTED_OWNERS = {
    "raw": "data_service",
    "fund": "data_service",
    "market": "data_service",
    "governance": "data_service",
    "factor": "factor_service",
    "evaluation": "fund_service",
}


def _declared_schemas(path: pathlib.Path) -> set[str]:
    """从模块里所有 __table_args__ 的 {"schema": "..."} 字面量取 schema 名。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    schemas: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values, strict=True):
            if (
                isinstance(key, ast.Constant)
                and key.value == "schema"
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
            ):
                schemas.add(value.value)
    return schemas


def _owners() -> dict[str, set[str]]:
    owners: dict[str, set[str]] = {}
    for service_dir in sorted(p for p in SERVICES.iterdir() if p.is_dir()):
        for module in service_dir.rglob("*.py"):
            for schema in _declared_schemas(module):
                owners.setdefault(schema, set()).add(service_dir.name)
    return owners


def test_each_schema_has_exactly_one_declaring_service():
    shared = {s: sorted(o) for s, o in _owners().items() if len(o) > 1}
    assert not shared, (
        f"以下 schema 的 ORM 模型分散在多个 service 包中：{shared}。"
        "SB-1 要求每个 schema 的写入权唯一（G-13）。"
    )


def test_schema_owners_match_the_architecture():
    actual = {s: next(iter(o)) for s, o in _owners().items() if len(o) == 1}
    for schema, owner in EXPECTED_OWNERS.items():
        assert actual.get(schema) == owner, (
            f"schema {schema!r} 的模型定义在 {actual.get(schema)!r}，"
            f"按 spec §2.3 应属 {owner!r}"
        )


def test_expected_owner_table_is_not_stale():
    """守卫：新增 schema 却忘了登记写入权时，本条会红。

    没有它，一个新 schema 可以在两个 service 里各定义一半而两条检查全绿
    （第一条只看「是否分散」，第二条只遍历表里已有的键）。
    """
    declared = set(_owners())
    unregistered = declared - set(EXPECTED_OWNERS)
    assert not unregistered, (
        f"schema {sorted(unregistered)} 出现了 ORM 模型但未在 EXPECTED_OWNERS "
        "中登记写入权。新增 schema 必须先决定它归谁写。"
    )
```

- [ ] **Step 2: 写失败的 SB-1 运行时测试与流水线集成测试**

```python
# tests/integration/test_schema_write_ownership.py
"""SB-1 的【动态】一半：每个 service 实际写了哪些 schema。

静态检查只能证明「模型定义在哪」，证明不了「谁往里写」——
fund_service 完全可以 import factor 的 model 再 add() 一行，
静态检查对此全绿。这里挂 before_flush 监听器，记录真实的写入面。
"""
import datetime as dt
from contextlib import contextmanager

import pytest
from sqlalchemy import event

pytestmark = pytest.mark.integration


@contextmanager
def recording_written_schemas(session):
    """记录本 session 在 flush 时触碰到的全部 schema。"""
    written: set[str] = set()

    def _before_flush(sess, flush_context, instances):
        for obj in list(sess.new) + list(sess.dirty) + list(sess.deleted):
            table = getattr(type(obj), "__table__", None)
            if table is not None:
                written.add(table.schema or "public")

    event.listen(session, "before_flush", _before_flush)
    try:
        yield written
    finally:
        event.remove(session, "before_flush", _before_flush)


def test_factor_service_writes_only_the_factor_schema(
    db_session, evaluation_context, seeded_peer_group
):
    from fip.services.factor_service.compute import FactorComputeService

    with recording_written_schemas(db_session) as written:
        FactorComputeService(db_session, seeded_peer_group.policy).run(
            evaluation_context, seeded_peer_group.snapshot_id, window="3Y"
        )
    assert written == {"factor"}, (
        f"factor_service 写入了 {sorted(written)}；SB-1 要求它只写 factor schema"
    )


def test_fund_service_writes_only_the_evaluation_schema(
    db_session, evaluation_context, seeded_peer_group, factor_run_id
):
    from fip.services.fund_service.evaluate import FundEvaluationService

    with recording_written_schemas(db_session) as written:
        FundEvaluationService(
            db_session, seeded_peer_group.policy, seeded_peer_group.profile
        ).run(evaluation_context, factor_run_id, seeded_peer_group.snapshot_id)
    assert written == {"evaluation"}, (
        f"fund_service 写入了 {sorted(written)}；SB-1 要求它只写 evaluation schema。"
        "读 factor / fund / market 是允许的，写不是。"
    )


def test_the_listener_would_actually_catch_a_violation(db_session):
    """守卫：证明监听器【看得见】违规，而不是永远返回空集合。

    一条永远为空的记录器会让上面两条测试永久为真 —— 那正是 SB-1
    在 Plan-1 里「静默缺席」的同一种失败方式，只是换了个形态。
    """
    from fip.services.data_service.models.fund import Fund

    with recording_written_schemas(db_session) as written:
        db_session.add(Fund(product_name="监听器自检"))
        db_session.flush()
    assert written == {"fund"}
```

```python
# tests/integration/test_evaluation_pipeline.py
"""因子 → 标准化 → 评分 → 排名 → 分层 → 候选池 的端到端落库。"""
import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from fip.services.fund_service.models.evaluation import (
    FundRanking,
    FundScore,
    FundScoreAttribution,
    FundTierRow,
)

pytestmark = pytest.mark.integration


def test_pipeline_persists_score_attribution_ranking_and_tier(
    db_session, evaluation_context, seeded_peer_group, factor_run_id
):
    from fip.services.fund_service.evaluate import FundEvaluationService

    result = FundEvaluationService(
        db_session, seeded_peer_group.policy, seeded_peer_group.profile
    ).run(evaluation_context, factor_run_id, seeded_peer_group.snapshot_id)
    assert result.scored > 0

    scores = db_session.execute(select(FundScore)).scalars().all()
    # D-19：M1 的常态是 PARTIAL（REL 子分恒 UNAVAILABLE）——
    # 落库之后这一点仍须成立，否则下游会把 PARTIAL 当异常处理。
    assert {s.score_status for s in scores} == {"PARTIAL"}
    assert all(s.relative_performance_score is None for s in scores)
    assert all(s.data_completeness == Decimal("0.76923077") for s in scores)


def test_excluded_factors_are_persisted_in_attribution_with_zero_weight(
    db_session, evaluation_context, seeded_peer_group, factor_run_id
):
    """G-3 + FS §10.4：被排除的因子不得从归因中消失。"""
    from fip.services.fund_service.evaluate import FundEvaluationService

    FundEvaluationService(
        db_session, seeded_peer_group.policy, seeded_peer_group.profile
    ).run(evaluation_context, factor_run_id, seeded_peer_group.snapshot_id)

    rel_rows = db_session.execute(
        select(FundScoreAttribution).where(
            FundScoreAttribution.factor_id.like("F-REL-%"))
    ).scalars().all()
    assert rel_rows, "声明但不可算的 REL 因子在归因里消失了"
    for row in rel_rows:
        assert row.weight == Decimal("0")
        assert row.normalized_score is None
        assert row.weighted_contribution is None
        assert row.exclusion_reason


def test_ranking_persists_rank_n_effective_and_percentile_together(
    db_session, evaluation_context, seeded_peer_group, factor_run_id
):
    """G-8：三者都必须落库 —— 只存 Rank 则历史分位不可还原。"""
    from fip.services.fund_service.evaluate import FundEvaluationService

    FundEvaluationService(
        db_session, seeded_peer_group.policy, seeded_peer_group.profile
    ).run(evaluation_context, factor_run_id, seeded_peer_group.snapshot_id)

    rows = db_session.execute(select(FundRanking)).scalars().all()
    assert rows
    for row in rows:
        assert row.n_effective is not None
        assert row.peer_group_size is not None
        if row.ranking_status == "NORMAL":
            assert row.rank is not None and row.percentile is not None
        else:
            assert row.rank is None and row.percentile is None


def test_tier_row_carries_the_peer_group_absolute_level(
    db_session, evaluation_context, seeded_peer_group, factor_run_id
):
    """G-9：Tier 不得单独输出 —— 落库时就必须带组内 Sharpe / MDD 中位数。

    在纯函数层它是 TierResult 的必填字段；这里断言那两列真的到了库里，
    否则 API 仍然可以只查出一个孤零零的 "A+"。
    """
    from fip.services.fund_service.evaluate import FundEvaluationService

    FundEvaluationService(
        db_session, seeded_peer_group.policy, seeded_peer_group.profile
    ).run(evaluation_context, factor_run_id, seeded_peer_group.snapshot_id)

    columns = set(FundTierRow.__table__.columns.keys())
    assert {"peer_sharpe_median", "peer_max_drawdown_median",
            "percentile", "total_score", "n_effective"} <= columns


def test_pipeline_is_reproducible_within_tolerance(
    db_session, evaluation_context, seeded_peer_group, factor_run_id
):
    """G-2：同一输入重算必须一致，容差 1e-10。"""
    from fip.services.fund_service.evaluate import FundEvaluationService

    service = FundEvaluationService(
        db_session, seeded_peer_group.policy, seeded_peer_group.profile
    )
    service.run(evaluation_context, factor_run_id, seeded_peer_group.snapshot_id)
    first = {s.share_class_id: s.total_score
             for s in db_session.execute(select(FundScore)).scalars()}
    db_session.execute(FundScore.__table__.delete())
    service.run(evaluation_context, factor_run_id, seeded_peer_group.snapshot_id)
    second = {s.share_class_id: s.total_score
              for s in db_session.execute(select(FundScore)).scalars()}
    assert set(first) == set(second)
    for key in first:
        assert abs(first[key] - second[key]) < Decimal("1e-10")


def test_eligibility_handling_config_covers_every_enum_value(seeded_peer_group):
    """配置与枚举的漂移检查。

    策略库侧刻意用 str 表达可投资性（依赖方向单向，不得 import services），
    所以「处理表是否覆盖了全部取值」只能在【允许 import 枚举的这一层】断言。
    少一个取值不会在策略库里报错，只会在运行到那只基金时抛 KeyError ——
    那时已经是生产。
    """
    from fip.services.data_service.eligibility import EligibilityStatus

    handled = set(seeded_peer_group.policy.investment_eligibility_handling)
    assert handled == {s.value for s in EligibilityStatus}
```

- [ ] **Step 3: 运行确认失败**

Run: `.venv/bin/pytest tests/fitness/test_schema_write_ownership.py tests/integration/test_schema_write_ownership.py tests/integration/test_evaluation_pipeline.py -q`

Expected: 静态那一条以 AssertionError 失败（`factor` / `evaluation` 尚无 ORM 模型或
未落在对应 service 包下），另两个文件以 `ModuleNotFoundError` 失败。
两类失败都要粘进报告 —— 静态测试的失败信息尤其重要，它直接告诉你
Task 7/8 的模型放对位置了没有。

- [ ] **Step 4: 实现单一配置源**

```python
# src/fip/platform/config/evaluation_policy.py
"""Evaluation Policy 的解析点 —— G-7 的「同一配置源」就是这一个类。

标准化（Task 12）、排名（Task 15）、分层（Task 15）三处都需要
MIN_PEER_GROUP_SIZE。若三处各自 config.get("peer_group.min_sample_size")，
那就是三个配置源：调参那天只要漏改一处就会分叉，而分叉后的症状
（分位算出来了但 Tier 没产出）极难定位。因此配置路径字符串在全仓
【只出现在本文件】，tests/fitness/test_single_config_source.py 对此断言。

本模块住在 platform 层而不是某个 service 里：两个 service 都要用它，
放进任一个都会制造出一条 service → service 的依赖。
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from fip.strategy_library.ranking.rank import TierThresholds
from fip.strategy_library.universe.rules import EligibilityAction
from fip.platform.config.loader import ConfigSet

_ELIGIBILITY_STATUSES = (
    "FULLY_ELIGIBLE", "HOLD_ONLY", "LIMITED", "EXIT_ONLY", "NOT_TRADABLE",
)


@dataclass(frozen=True, slots=True)
class EvaluationPolicy:
    """⚠️ 这里【没有】mar 字段。

    P2-4：`config/policy/evaluation/v1.yaml` 里原有的 `mar.default: 0.0`
    直接违反 G-6（「mar_policy 必填无默认」「不得给 MAR 设兜底值」），
    由 Task 10 删除。MAR 改由 Task 10 的 Threshold Resolver 按三模式解析，
    未配置即 None —— 于是 F-RISK-002 / F-RAP-002 一律 UNAVAILABLE。
    在这里加一个 `mar: Decimal | None = Decimal("0")` 之类的兜底，
    等于把那条已经拆掉的地雷重新埋回去：「两者数值相同但含义相反，
    设默认会让配置遗漏静默产出看起来正常的 Sortino」（FE:472-481）。
    """

    min_peer_group_size: int
    classification_level: str
    tier_thresholds: TierThresholds
    min_universe_size: int
    data_completeness_floor: Decimal
    investment_eligibility_handling: Mapping[str, EligibilityAction]
    provisional_used: tuple[str, ...]

    @classmethod
    def load(cls, config: ConfigSet) -> "EvaluationPolicy":
        thresholds = TierThresholds(
            a_plus=Decimal(config.get("classification.tier_percentile_thresholds.a_plus")),
            a=Decimal(config.get("classification.tier_percentile_thresholds.a")),
            b=Decimal(config.get("classification.tier_percentile_thresholds.b")),
            c=Decimal(config.get("classification.tier_percentile_thresholds.c")),
        )
        handling = {
            status: EligibilityAction(
                config.get(f"selection.investment_eligibility_handling.{status}")
            )
            for status in _ELIGIBILITY_STATUSES
        }
        return cls(
            min_peer_group_size=int(config.get("peer_group.min_sample_size")),
            classification_level=str(config.get("peer_group.classification_level")),
            tier_thresholds=thresholds,
            min_universe_size=int(config.get("selection.min_universe_size")),
            data_completeness_floor=Decimal(
                config.get("selection.data_completeness_floor")
            ),
            investment_eligibility_handling=handling,
            # 本次装载消费到的 PROVISIONAL 参数清单，随决策快照落库
            # （spec §5.3：两种运行模式下都不阻断，但都不静默）。
            provisional_used=config.provisional_parameters_used,
        )
```

- [ ] **Step 5: 实现 factor_service（只写 factor schema）**

```python
# src/fip/services/factor_service/compute.py
"""因子计算与 Peer Group 内标准化的编排。

SB-1：本 service 是 `factor` schema 的【唯一】写入方。
它【读】fund / market（经 Plan-1 的 PIT 端口）与 evaluation.peer_group_member，
但一行都不往那些 schema 里写 —— tests/integration/test_schema_write_ownership.py
的 before_flush 监听器对此断言。

C-11：本模块只做编排与持久化。因子公式在 strategy_library/factor/compute.py，
分位公式在 factor/normalize.py，阈值判定在 factor/effectiveness.py。
"""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.strategy_library.factor.compute import compute_factor
from fip.strategy_library.factor.definitions import (
    FACTOR_IDS,
    preference_direction,
)
from fip.strategy_library.factor.normalize import percentile_rank
from fip.strategy_library.factor.status import FactorStatus
from fip.platform.config.evaluation_policy import EvaluationPolicy
from fip.platform.decision_data.context import DecisionExecutionContext
from fip.platform.decision_data.pit import PitDataContext
from fip.services.factor_service.models.factor import FactorRun, FactorValue

WRITES_SCHEMAS = frozenset({"factor"})


@dataclass(frozen=True, slots=True)
class FactorRunResult:
    run_id: int
    computed: int
    unavailable: int


class FactorComputeService:
    def __init__(self, session: Session, policy: EvaluationPolicy) -> None:
        self._session = session
        self._policy = policy

    def run(
        self,
        context: DecisionExecutionContext,
        peer_group_snapshot_id: int,
        window: str,
    ) -> FactorRunResult:
        """一次因子批次：逐成员算 10 个因子，再在组内做分位标准化。

        window（评价周期，如 "3Y"）是显式参数而不是从 context 里取：
        DecisionExecutionContext（Plan-1 Task 4）没有这个字段，
        而排名必须显式声明周期（FR §4.1「一次排名必须完整声明五项，
        缺一则结果无法解释」）。窗口不进 Factor ID，所以它必须进
        factor_value 的唯一键（D-13）—— 由调用方显式传入是最不容易漏的形式。

        标准化必须在 Peer Group 内进行且 Peer Group 独立于 Score 产生
        （FS §7.2 规则 1 / C-4）—— 因此这里读的是【已提交的 B1 快照成员】，
        而不是现场重新分组。
        """
        run = FactorRun(
            decision_at=context.decision_at,
            code_version=context.code_version,
            evaluation_policy_version=context.policy_version,
            peer_group_snapshot_id=peer_group_snapshot_id,
            window=window,
            status="RUNNING",
        )
        self._session.add(run)
        self._session.flush()

        members = self._members(peer_group_snapshot_id)
        pit = PitDataContext(context=context, session=self._session)

        results: dict[int, dict[str, object]] = {}
        for share_class_id in members:
            inp = self._factor_input(pit, share_class_id, context)
            results[share_class_id] = {
                factor_id: compute_factor(factor_id, inp) for factor_id in FACTOR_IDS
            }

        computed = 0
        unavailable = 0
        for factor_id in FACTOR_IDS:
            # 分位在【每个因子内】跨成员计算。UNAVAILABLE / INVALID 的成员
            # 不参与分位计算（FS §7.4），且不得以任何值补位（G-3）。
            participants = [
                (share_class_id, per_factor[factor_id])
                for share_class_id, per_factor in sorted(results.items())
                if per_factor[factor_id].status
                in (FactorStatus.VALID, FactorStatus.WARNING)
                and per_factor[factor_id].value is not None
            ]
            percentiles = percentile_rank(
                [result.value for _, result in participants],
                preference_direction(factor_id),
            )
            scored = dict(
                zip(
                    (share_class_id for share_class_id, _ in participants),
                    percentiles,
                    strict=True,
                )
            )
            for share_class_id, per_factor in sorted(results.items()):
                result = per_factor[factor_id]
                self._session.add(
                    FactorValue(
                        factor_run_id=run.id,
                        share_class_id=share_class_id,
                        factor_id=factor_id,
                        window=window,
                        effective_at=context.decision_at,
                        version=1,
                        raw_value=result.value,
                        normalized_score=scored.get(share_class_id),
                        factor_status=result.status.value,
                        status_reason=result.reason,
                        observation_count=result.observation_count,
                        peer_group_snapshot_id=peer_group_snapshot_id,
                        evaluation_policy_version=context.policy_version,
                        available_at=self._available_at(context),
                        availability_quality="DERIVED",
                        ingested_at=self._now(),
                    )
                )
                if result.status is FactorStatus.VALID:
                    computed += 1
                else:
                    unavailable += 1

        run.status = "COMPLETED"
        self._session.flush()
        return FactorRunResult(run_id=run.id, computed=computed, unavailable=unavailable)
```

> 上面的 `_members` / `_factor_input` / `_available_at` / `_now` 四个私有方法
> 属于 Task 9–12 已定的读取路径（`peer_group_member` 读取、`NavPoint` → `FactorInput`
> 组装、派生时点的 `available_at`）。它们不在本任务新增语义，实现时照
> Task 11 / Task 2 的产出直接调用；若那两个任务的签名与此处不符，
> 以那两个任务为准并回改本节，**不得在这里另造一份读取逻辑**。

- [ ] **Step 6: 实现 fund_service（只写 evaluation schema）**

```python
# src/fip/services/fund_service/evaluate.py
"""评分 → 排名 → 分层 → 候选池的编排。

SB-1：本 service 是 `evaluation` schema 的【唯一】写入方。
它经 FactorValueReader 【读】factor schema —— 读是允许的，写不是。
两者的区别由 tests/integration/test_schema_write_ownership.py 的
before_flush 监听器在运行时裁定，而不是靠 code review 记得。
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from fip.quant_engine.stats import median
from fip.strategy_library.ranking.rank import (
    RankingEntry,
    assign_tier,
    peer_group_absolute_level,
    rank_within_peer_group,
)
from fip.strategy_library.score.subscore import (
    EvaluationProfile,
    compute_fund_score,
)
from fip.platform.config.evaluation_policy import EvaluationPolicy
from fip.platform.decision_data.context import DecisionExecutionContext
from fip.services.factor_service.repositories.factor_value import FactorValueReader
from fip.services.fund_service.models.evaluation import (
    FundRanking,
    FundScore,
    FundScoreAttribution,
    FundTierRow,
)

WRITES_SCHEMAS = frozenset({"evaluation"})

# M1 声明了但不可算的因子及其原因。这些因子【必须】出现在归因里
# （FS §10.4），因此这里为它们构造 UNAVAILABLE 的 NormalizedFactor，
# 而不是干脆不产出 —— 「从归因中消失」正是本条要防的事。
UNCOMPUTABLE_IN_M1 = {
    "F-REL-002": "Benchmark 四层建模推到 M2（spec §6.2），Alpha 不可算",
    "F-REL-003": "Benchmark 四层建模推到 M2（spec §6.2），Beta 不可算",
    "F-REL-004": "Benchmark 四层建模推到 M2（spec §6.2），Information Ratio 不可算",
}


@dataclass(frozen=True, slots=True)
class EvaluationRunResult:
    scored: int
    ranked: int
    tiered: int
    universe_snapshot_id: int | None


class FundEvaluationService:
    def __init__(
        self, session: Session, policy: EvaluationPolicy, profile: EvaluationProfile
    ) -> None:
        self._session = session
        self._policy = policy
        self._profile = profile

    def run(
        self,
        context: DecisionExecutionContext,
        factor_run_id: int,
        peer_group_snapshot_id: int,
    ) -> EvaluationRunResult:
        reader = FactorValueReader(self._session)
        per_fund = reader.normalized_factors(factor_run_id)
        effectiveness = reader.effectiveness(self._profile.profile_id)

        scores = {}
        for share_class_id, factors in sorted(per_fund.items()):
            for factor_id, reason in UNCOMPUTABLE_IN_M1.items():
                factors.setdefault(factor_id, _unavailable_factor(factor_id, reason))
            scores[share_class_id] = compute_fund_score(
                self._profile, factors, effectiveness
            )
            self._write_score(context, peer_group_snapshot_id, share_class_id,
                              scores[share_class_id])

        rankings = rank_within_peer_group(
            [
                RankingEntry(share_class_id=i, profile_id=self._profile.profile_id,
                             metric_value=s.total_score)
                for i, s in sorted(scores.items())
            ],
            peer_group_size=len(per_fund),
            min_peer_group_size=self._policy.min_peer_group_size,
        )

        # G-9：组内绝对水平必须与 Tier 一同产出。取【有效】的 Sharpe 与 MDD
        # 原始值算中位数；一个都没有时是 None（UNAVAILABLE），不是 0。
        level = peer_group_absolute_level(
            sharpe_values=reader.valid_raw_values(factor_run_id, "F-RAP-001"),
            mdd_values=reader.valid_raw_values(factor_run_id, "F-RISK-003"),
        )

        tiered = 0
        for ranking in rankings:
            self._write_ranking(context, peer_group_snapshot_id, ranking)
            tier = assign_tier(
                ranking,
                total_score=scores[ranking.share_class_id].total_score,
                thresholds=self._policy.tier_thresholds,
                peer_group_level=level,
                min_peer_group_size=self._policy.min_peer_group_size,
            )
            self._write_tier(context, peer_group_snapshot_id, tier)
            tiered += 1 if tier.tier is not None else 0

        self._session.flush()
        return EvaluationRunResult(
            scored=len(scores), ranked=len(rankings), tiered=tiered,
            universe_snapshot_id=None,     # B2 由 CLI 在 Task 18 单独触发
        )

    def _write_score(self, context, peer_group_snapshot_id, share_class_id, result):
        """五子分 + 总分 + data_completeness + 逐因子归因。

        G-4：data_completeness 与分数【一起】落库、一起呈现 ——
        「基于 3 个指标的 85 分与基于 12 个指标的 85 分，可信度完全不同」。
        """
        by_name = {s.name: s for s in result.sub_scores}
        score = FundScore(
            share_class_id=share_class_id,
            effective_at=context.decision_at,
            version=1,
            profile_id=result.profile_id,
            total_score=result.total_score,
            return_score=_value(by_name, "Return"),
            risk_score=_value(by_name, "Risk"),
            risk_adjusted_score=_value(by_name, "Risk-Adjusted"),
            stability_score=_value(by_name, "Stability"),
            relative_performance_score=_value(by_name, "Relative Performance"),
            score_status=result.status.value,
            data_completeness=result.data_completeness,
            weight_source="EQUAL_WITHIN_VALID",
            peer_group_snapshot_id=peer_group_snapshot_id,
            evaluation_policy_version=context.policy_version,
            scoring_policy_version=context.strategy_version,
            available_at=context.decision_at,
            availability_quality="DERIVED",
        )
        self._session.add(score)
        self._session.flush()
        for sub in result.sub_scores:
            for row in sub.attributions:
                self._session.add(
                    FundScoreAttribution(
                        fund_score_id=score.id,
                        sub_score_name=sub.name.value,
                        factor_id=row.factor_id,
                        window=row.window,
                        raw_value=row.raw_value,
                        normalized_score=row.normalized_score,
                        direction=None if row.direction is None else row.direction.value,
                        weight=row.weight,
                        weighted_contribution=row.weighted_contribution,
                        participated=row.participated,
                        exclusion_reason=row.exclusion_reason,
                        effectiveness_verdict=row.effectiveness_verdict,
                        redistributed_to=",".join(row.redistributed_to) or None,
                    )
                )
```

> `_write_ranking` / `_write_tier` / `_value` / `_unavailable_factor` 四个辅助
> 与 `_write_score` 同构：逐字段搬运，无判断逻辑。
> `_write_tier` 必须写入 `peer_sharpe_median` 与 `peer_max_drawdown_median`
> 两列 —— 它们不是可选的展示字段，是 G-9 的落库形态
> （`tests/integration/test_evaluation_pipeline.py::test_tier_row_carries_the_
> peer_group_absolute_level` 对此断言）。

- [ ] **Step 7: 运行确认通过**

Run: `.venv/bin/pytest tests/fitness tests/integration/test_schema_write_ownership.py tests/integration/test_evaluation_pipeline.py -v -m "integration or not integration"`

Expected: 全部通过。三条必须出现在 PASSED 里：
`test_each_schema_has_exactly_one_declaring_service`（SB-1 静态）、
`test_fund_service_writes_only_the_evaluation_schema`（SB-1 动态）、
`test_the_listener_would_actually_catch_a_violation`（监听器自检）。

Run: `make check`

Expected: lint、typecheck 与全部 281+ 条既有测试仍然通过（不得有回归）。

- [ ] **Step 8: 提交**

```bash
git add -A
git commit -m "feat(services): factor_service / fund_service 装配与 SB-1

SB-1 在 Plan-1 里是静默缺席的（只有一个写入方时它空洞）；Plan-2 引入两个
新 service 后第一次有真实约束力，因此补两条检查：静态查 ORM 模型定义在
哪个 service 包，动态用 before_flush 监听器查每个 service 实际 flush 了
哪些 schema，并配一条自检证明监听器看得见违规。
MIN_PEER_GROUP_SIZE 的配置路径全仓只出现在 EvaluationPolicy 一处（G-7）。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SZBJBiDWT8FHcx7NhkgcTD"
```

---

### Task 18: CLI 与端到端验收

> Plan-2 的收尾。完成后可用 `fip_dev` 里的真实数据端到端验证 M1.2–M1.4 的核心能力。
>
> **环境事实**：`psql` / `createdb` **不在 PATH**，因此本任务的全部核对
> 一律走 `.venv/bin/python`（Plan-1 Task 19 的核对用的是 `psql`，照抄会得到
> `command not found`）。

**Files:**
- Modify: `src/fip/platform/cli.py`
- Test: `tests/integration/test_cli_plan2.py`

**Interfaces:**

- Consumes: `EvaluationPolicy.load`、`FactorComputeService.run`、
  `FundEvaluationService.run`、`UniverseSnapshotWriter.write`、
  `PeerGroupBuilder`（Task 11）
- Produces: CLI 子命令
  ```
  fip build-peer-groups --decision-at YYYY-MM-DD
  fip compute-factors   --decision-at YYYY-MM-DD --window 3Y
  fip evaluate          --decision-at YYYY-MM-DD --window 3Y
  fip build-universe    --decision-at YYYY-MM-DD
  fip show-evaluation   --symbol 000001 --decision-at YYYY-MM-DD
  ```

- [ ] **Step 1: 写失败的 CLI 集成测试**

```python
# tests/integration/test_cli_plan2.py
"""Plan-2 的 CLI —— 重点是 G-9 与 G-4 的【输出结构】约束。

G-9 与 G-4 不是「建议这么展示」，是可验收项：
「仅展示 Tier 而不展示组内绝对水平，视为违反本条」（FC:157）。
因此它们必须落在输出结构上，由测试断言，而不是靠写代码的人记得。
"""
import datetime as dt

import pytest

from fip.platform import cli

pytestmark = pytest.mark.integration


def test_show_evaluation_prints_tier_with_peer_group_absolute_level(
    capsys, seeded_evaluation, monkeypatch
):
    """G-9：Tier 不得单独输出，必须与组内 Sharpe 中位数 + MDD 中位数同屏。"""
    monkeypatch.setattr(cli, "_session", lambda: seeded_evaluation.session)
    cli.main(["show-evaluation", "--symbol", seeded_evaluation.symbol,
              "--decision-at", "2026-08-31"])
    out = capsys.readouterr().out
    assert "Fund Tier" in out
    assert "组内 Sharpe 中位数" in out
    assert "组内 Maximum Drawdown 中位数" in out


def test_show_evaluation_prints_data_completeness_with_the_score(
    capsys, seeded_evaluation, monkeypatch
):
    """G-4：data_completeness 是输出必备字段，必须随 Score 一起呈现。"""
    monkeypatch.setattr(cli, "_session", lambda: seeded_evaluation.session)
    cli.main(["show-evaluation", "--symbol", seeded_evaluation.symbol,
              "--decision-at", "2026-08-31"])
    out = capsys.readouterr().out
    assert "Total Score" in out
    assert "Data Completeness" in out
    assert "0.76923077" in out


def test_show_evaluation_renders_unavailable_not_zero(
    capsys, seeded_evaluation, monkeypatch
):
    """G-3：REL 子分必须显示为 UNAVAILABLE，不得渲染成 0 或空白。

    「0 分」与「没有这个分」在屏幕上必须能分开 —— 渲染成 0.00 会让
    读者以为这只基金相对 Benchmark 表现最差。
    """
    monkeypatch.setattr(cli, "_session", lambda: seeded_evaluation.session)
    cli.main(["show-evaluation", "--symbol", seeded_evaluation.symbol,
              "--decision-at", "2026-08-31"])
    out = capsys.readouterr().out
    assert "Relative Performance" in out
    line = next(l for l in out.splitlines() if "Relative Performance" in l)
    assert "UNAVAILABLE" in line
    assert "0.00" not in line


def test_show_evaluation_reports_missing_tier_without_inventing_one(
    capsys, seeded_small_group, monkeypatch
):
    """小样本：必须显式说「样本不足，未产出 Tier」，不得留白也不得给 D。"""
    monkeypatch.setattr(cli, "_session", lambda: seeded_small_group.session)
    cli.main(["show-evaluation", "--symbol", seeded_small_group.symbol,
              "--decision-at", "2026-08-31"])
    out = capsys.readouterr().out
    assert "INSUFFICIENT_SAMPLE" in out
    assert "n_effective" in out


def test_build_universe_exits_nonzero_when_pool_is_undersized(
    seeded_evaluation, monkeypatch
):
    """§19：Universe 规模低于下限 → 显式失败并阻断，不得静默产出过小的池子。

    快照仍然落库（标 INSUFFICIENT_UNIVERSE，留痕），但 CLI 必须以非零
    退出码结束 —— 否则批处理脚本会把一个不合格的池子当成成功继续用。
    """
    monkeypatch.setattr(cli, "_session", lambda: seeded_evaluation.session)
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["build-universe", "--decision-at", "2026-08-31"])
    assert excinfo.value.code != 0
    assert "INSUFFICIENT_UNIVERSE" in str(excinfo.value)
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/pytest tests/integration/test_cli_plan2.py -q -m integration`

Expected: `AttributeError` / `argparse` 报未知子命令 `show-evaluation`。粘进报告。

- [ ] **Step 3: 实现 CLI 子命令**

```python
# src/fip/platform/cli.py —— 追加（保留 Plan-1 的三个子命令与文件顶部的
# TYPE_CHECKING 说明；platform 层【不得】在模块级 import services，
# 下面每个函数体内的延迟 import 是有意为之，见文件顶部注释）

import pathlib

CONFIG_ROOT = pathlib.Path(__file__).resolve().parents[3] / "config"


def _policy():
    """装载 Evaluation Policy。PROVISIONAL 参数的使用会被如实记录/告警。"""
    from fip.platform.config.evaluation_policy import EvaluationPolicy
    from fip.platform.config.loader import load_config_file

    config = load_config_file(
        CONFIG_ROOT / "policy" / "evaluation" / "v1.yaml", RuntimeMode.BACKTEST
    )
    return EvaluationPolicy.load(config)


def _context(decision_at: dt.date) -> DecisionExecutionContext:
    return DecisionExecutionContext(
        decision_id=f"CLI-{decision_at}",
        decision_at=decision_at,
        data_as_of=decision_at,
        strategy_version="cli",
        policy_version="cli",
        code_version="cli",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )


def cmd_compute_factors(args: argparse.Namespace) -> None:
    from fip.services.factor_service.compute import FactorComputeService

    decision_at = dt.date.fromisoformat(args.decision_at)
    with _session() as session:
        snapshot_id = _latest_peer_group_snapshot(session, decision_at)
        result = FactorComputeService(session, _policy()).run(
            _context(decision_at), snapshot_id, window=args.window
        )
        session.commit()
    print(f"因子批次 {result.run_id}：VALID {result.computed} 条、"
          f"非 VALID {result.unavailable} 条（后者【不是】0，是如实的不可用）")


def cmd_evaluate(args: argparse.Namespace) -> None:
    from fip.services.fund_service.evaluate import FundEvaluationService

    decision_at = dt.date.fromisoformat(args.decision_at)
    with _session() as session:
        snapshot_id = _latest_peer_group_snapshot(session, decision_at)
        run_id = _latest_factor_run(session, decision_at, args.window)
        result = FundEvaluationService(session, _policy(), _profile()).run(
            _context(decision_at), run_id, snapshot_id
        )
        session.commit()
    print(f"评分 {result.scored} 只、排名 {result.ranked} 条、产出 Tier {result.tiered} 只")
    if result.tiered == 0:
        # 不是错误：新成立的细分类别天然样本少（FR:358）。但必须说出来，
        # 否则「一个 Tier 都没有」看起来像跑失败了。
        print("  未产出任何 Tier —— n_effective < MIN_PEER_GROUP_SIZE，"
              "按 FC §8.5 不产出而非给低置信标记")


def cmd_build_universe(args: argparse.Namespace) -> None:
    from fip.services.fund_service.universe import UniverseSnapshotWriter

    decision_at = dt.date.fromisoformat(args.decision_at)
    policy = _policy()
    with _session() as session:
        snapshot_id = _latest_peer_group_snapshot(session, decision_at)
        outcomes, refs = _select_candidates(session, decision_at, policy)
        universe_id = UniverseSnapshotWriter(session).write(
            decision_at=decision_at,
            peer_group_snapshot_id=snapshot_id,
            selection_policy_version="cli",
            condition_version="v1",
            min_universe_size=policy.min_universe_size,
            outcomes=outcomes,
            eligibility_refs=refs,
        )
        session.commit()
        selected = sum(1 for o in outcomes
                       if o.selection_status.value == "SELECTED")
    rejected = len(outcomes) - selected
    print(f"Universe 快照 {universe_id}：入池 {selected} 只、"
          f"被拒 {rejected} 只（被拒成员与全部条件结果均已落库）")
    if selected < policy.min_universe_size:
        # 快照已留痕（universe_status = INSUFFICIENT_UNIVERSE），但本期
        # 组合构建必须被阻断：不得降级为「用更少的基金优化」。
        raise SystemExit(
            f"INSUFFICIENT_UNIVERSE：入池 {selected} 只 < 下限 "
            f"{policy.min_universe_size} 只。快照已落库留痕，但本期决策阻断 —— "
            "不得静默产出过小的池子，也不得降级为用更少的基金优化。"
        )


def cmd_show_evaluation(args: argparse.Namespace) -> None:
    """一只基金的评价全貌。

    ⚠️ 这个函数的【输出结构】本身是可验收项，不是展示偏好：
      · G-9：Tier 必须与组内 Sharpe 中位数 + MDD 中位数同屏，
        「仅展示 Tier 而不展示组内绝对水平，视为违反本条」（FC:157）
      · G-4：data_completeness 必须随 Score 呈现
      · G-3：UNAVAILABLE 渲染成 "UNAVAILABLE"，不得渲染成 0.00 或空白
    删掉其中任何一行都会让 tests/integration/test_cli_plan2.py 变红。
    """
    decision_at = dt.date.fromisoformat(args.decision_at)
    with _session() as session:
        share_class = _resolve(session, args.symbol)
        view = _evaluation_view(session, share_class.id, decision_at)

    if view is None:
        raise SystemExit(
            f"{args.symbol} 在 decision_at={decision_at} 没有评价结果。"
            "未留存快照的时点系统必须拒绝提供推算结果（FR-PEER-002），"
            "不会现场重算一个『今天的值』充数。"
        )

    print(f"{share_class.display_name}  @ decision_at={decision_at}")
    print(f"  Profile            {view.profile_id}")
    print(f"  Total Score        {_render(view.total_score)}   "
          f"score_status={view.score_status}")
    print(f"  Data Completeness  {_render(view.data_completeness)}"
          f"   （分母 = Profile 声明的因子数，含声明但不可算的 REL 三项）")
    for name, value in view.sub_scores:
        print(f"    {name:<22} {_render(value)}")
    print(f"  Rank / N           {_render(view.rank)} / {view.n_effective}"
          f"   （组规模 {view.peer_group_size}）")
    print(f"  Percentile         {_render(view.percentile)}")
    print(f"  Fund Tier          {_render(view.tier)}   "
          f"classification_status={view.classification_status}")
    # ↓ 这两行是 G-9 的强制缓解措施，不得删除、不得折叠到 --verbose 之后。
    print(f"    组内 Sharpe 中位数            {_render(view.peer_sharpe_median)}")
    print(f"    组内 Maximum Drawdown 中位数  {_render(view.peer_mdd_median)}")
    print("  归因（逐因子，含被排除项）：")
    for row in view.attributions:
        mark = " " if row.participated else "×"
        print(f"    {mark} {row.factor_id:<12} raw={_render(row.raw_value):>14}  "
              f"norm={_render(row.normalized_score):>14}  "
              f"w={row.weight}  contrib={_render(row.weighted_contribution)}"
              + (f"  ← {row.exclusion_reason}" if row.exclusion_reason else ""))


def _render(value: object | None) -> str:
    """None 一律渲染成 UNAVAILABLE。

    这是 G-3 在展示层的落地：把 None 渲染成 "0.00" 或 "" 会让
    「不可得」冒充「等于 0」或「等于空」。C-6 的同一条原则。
    """
    return "UNAVAILABLE" if value is None else str(value)
```

```python
# src/fip/platform/cli.py —— main() 中追加子命令注册
    p_pg = sub.add_parser("build-peer-groups", help="按分类与币种构建 Peer Group（B1）")
    p_pg.add_argument("--decision-at", required=True, dest="decision_at")
    p_pg.set_defaults(func=cmd_build_peer_groups)

    p_factor = sub.add_parser("compute-factors", help="计算 10 个因子并在组内标准化")
    p_factor.add_argument("--decision-at", required=True, dest="decision_at")
    p_factor.add_argument("--window", required=True,
                          help="评价周期，如 3Y。排名必须显式声明周期（FR §4.1）")
    p_factor.set_defaults(func=cmd_compute_factors)

    p_eval = sub.add_parser("evaluate", help="五子分 / 归因 / 排名 / 分层")
    p_eval.add_argument("--decision-at", required=True, dest="decision_at")
    p_eval.add_argument("--window", required=True)
    p_eval.set_defaults(func=cmd_evaluate)

    p_universe = sub.add_parser("build-universe", help="Eligibility Rules 与候选池快照（B2）")
    p_universe.add_argument("--decision-at", required=True, dest="decision_at")
    p_universe.set_defaults(func=cmd_build_universe)

    p_show = sub.add_parser("show-evaluation", help="一只基金的评价全貌")
    p_show.add_argument("--symbol", required=True)
    p_show.add_argument("--decision-at", required=True, dest="decision_at")
    p_show.set_defaults(func=cmd_show_evaluation)
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/pytest tests/integration/test_cli_plan2.py -v -m integration`

Expected: 五条全部通过。

- [ ] **Step 5: 端到端跑一遍真实数据**

前置：Task 6 的批量灌数已完成（目标 ≥ 300 只份额类别，D-2）。
若尚未完成，本步仍要跑 —— 它会走到小样本分支，那本身是判据 **A-3** 的一半。

```bash
.venv/bin/fip build-peer-groups --decision-at 2026-08-31
.venv/bin/fip compute-factors   --decision-at 2026-08-31 --window 3Y
.venv/bin/fip evaluate          --decision-at 2026-08-31 --window 3Y
.venv/bin/fip build-universe    --decision-at 2026-08-31 || echo "退出码 $? —— 见判据 A-4"
.venv/bin/fip show-evaluation   --symbol 000001 --decision-at 2026-08-31
```

- [ ] **Step 6: 五条可验收判据（真实数据，全部用 python 核对——psql 不在 PATH）**

**A-1 · `UNAVAILABLE` 未被任何填充值替代（G-3）**

```bash
.venv/bin/python - <<'PY'
from sqlalchemy import create_engine, text
from fip.settings import settings

engine = create_engine(settings.database_url, future=True)
with engine.connect() as conn:
    filled = conn.execute(text("""
        SELECT count(*) FROM evaluation.fund_score_attribution
        WHERE participated IS FALSE
          AND (normalized_score IS NOT NULL
               OR weighted_contribution IS NOT NULL
               OR weight <> 0
               OR exclusion_reason IS NULL)
    """)).scalar_one()
    rel_scored = conn.execute(text("""
        SELECT count(*) FROM evaluation.fund_score
        WHERE relative_performance_score IS NOT NULL
    """)).scalar_one()
    ghost = conn.execute(text("""
        SELECT count(*) FROM factor.factor_value
        WHERE factor_status <> 'VALID' AND raw_value IS NOT NULL
    """)).scalar_one()
    print(f"被排除却带值/带权重/无原因的归因行 = {filled}（必须为 0）")
    print(f"REL 子分被填了值的 fund_score 行 = {rel_scored}（必须为 0）")
    print(f"非 VALID 却带 raw_value 的因子值 = {ghost}（必须为 0）")
PY
```

Expected: 三个数**全为 0**。任何一个非 0 都意味着某处用值补了「不可得」——
这正是 G-3 与 C-6 要防的静默污染。

**A-2 · M1 的常态是 `PARTIAL`，且 `data_completeness` 反映缺失的 REL 子分（D-19 / G-4）**

```bash
.venv/bin/python - <<'PY'
from sqlalchemy import create_engine, text
from fip.settings import settings

engine = create_engine(settings.database_url, future=True)
with engine.connect() as conn:
    for row in conn.execute(text("""
        SELECT score_status, data_completeness, count(*)
        FROM evaluation.fund_score GROUP BY 1, 2 ORDER BY 3 DESC
    """)):
        print(row)
PY
```

Expected: 只有一行 `('PARTIAL', Decimal('0.76923077'), N)`（N = 参与评分的份额类别数）。
`COMPLETED` 出现即错误（M1 没有 Benchmark，五子分不可能齐全）；
`data_completeness = 1.0` 出现即错误（分母漏算了声明但不可算的 REL 三项，
「基于 4 个子分的 85 分与基于 5 个子分的 85 分」就此不可区分）；
`VALIDATION_PENDING` 出现说明 Task 13 的 `factor_effectiveness` 没跑出来。

**A-3 · `Rank` / `n_effective` / `Percentile` 三者落库且分位可反算（G-8）**

```bash
.venv/bin/python - <<'PY'
from decimal import Decimal
from sqlalchemy import create_engine, text
from fip.settings import settings

engine = create_engine(settings.database_url, future=True)
with engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT rank, n_effective, percentile, ranking_status
        FROM evaluation.fund_ranking
    """)).all()
    assert rows, "fund_ranking 一行都没有 —— 排名根本没落库"
    bad = []
    for rank, n, percentile, status in rows:
        if status == 'INSUFFICIENT_SAMPLE':
            if rank is not None or percentile is not None or n is None:
                bad.append(("样本不足行的形态不对", rank, n, percentile))
            continue
        expected = (Decimal(n - rank) / Decimal(n - 1) * 100)
        if abs(expected - percentile) > Decimal("1e-8"):
            bad.append(("分位反算不上", rank, n, percentile, expected))
    print(f"总行数 {len(rows)}，异常 {len(bad)}：{bad[:5]}")
PY
```

Expected: 异常数 **0**。这条判据的意义在于：只存 Rank 而不存 `N` 与 Percentile 时，
历史分位【不可还原】（FR:433）——反算能对上，证明三者是一致地落了库，
而不是其中某一个被事后重算出来的。

**A-4 · `REJECTED` 留痕，且条件求值未被短路（D-17 / G-11）**

```bash
.venv/bin/python - <<'PY'
from sqlalchemy import create_engine, text
from fip.settings import settings

engine = create_engine(settings.database_url, future=True)
with engine.connect() as conn:
    print("成员状态分布：", conn.execute(text("""
        SELECT selection_status, count(*) FROM evaluation.fund_universe_member
        GROUP BY 1
    """)).all())
    uneven = conn.execute(text("""
        SELECT count(*) FROM (
            SELECT m.id, count(r.id) AS k
            FROM evaluation.fund_universe_member m
            LEFT JOIN evaluation.selection_condition_result r
                   ON r.fund_universe_member_id = m.id
            GROUP BY m.id
        ) t
        WHERE t.k <> (SELECT max(k) FROM (
            SELECT count(*) AS k FROM evaluation.selection_condition_result
            GROUP BY fund_universe_member_id) x)
    """)).scalar_one()
    copies = conn.execute(text("""
        SELECT count(*) FROM information_schema.columns
        WHERE table_schema = 'evaluation'
          AND table_name = 'fund_universe_member'
          AND column_name = 'investment_eligibility'
    """)).scalar_one()
    print(f"条件结果行数与其他成员不一致的成员数 = {uneven}（必须为 0）")
    print(f"可投资性取值副本列 = {copies}（必须为 0，D-15 只存版本引用）")
PY
```

Expected: `REJECTED` 计数 **> 0**（一只被拒的都没有，说明规则形同虚设或被拒的没落库）；
条件行数不一致的成员数 **0**（每只候选的条件行数都等于条件集大小 K ——
短路求值会让被拒基金只有 1 行）；取值副本列 **0**。

**A-5 · CLI 端到端 + G-9 同屏 + 可复现性（G-2）**

```bash
.venv/bin/fip show-evaluation --symbol 000001 --decision-at 2026-08-31 | tee /tmp/eval-1.txt
.venv/bin/fip evaluate --decision-at 2026-08-31 --window 3Y
.venv/bin/fip show-evaluation --symbol 000001 --decision-at 2026-08-31 | tee /tmp/eval-2.txt
diff /tmp/eval-1.txt /tmp/eval-2.txt && echo "重算逐字一致"
```

Expected:
1. 输出中同时出现 `Fund Tier`、`组内 Sharpe 中位数`、`组内 Maximum Drawdown 中位数`
   三行 —— 缺任一行即违反 G-9（`FC:157`「仅展示 Tier 而不展示组内绝对水平，
   视为违反本条」）；
2. `Relative Performance` 那一行显示 `UNAVAILABLE` 而**不是** `0.00`；
3. `Data Completeness` 与 `Total Score` 同屏出现；
4. 两次输出 `diff` 为空 —— 同一 `decision_at` 重算逐字一致（G-2 的容差 1e-10
   在这里被收紧成逐位相同，因为输入完全未变）。

再把 `--decision-at` 往前挪一年重跑，核对**时点单调性**：

```bash
.venv/bin/fip show-evaluation --symbol 000001 --decision-at 2025-08-31
```

Expected: 要么给出一份**不同**的评价（当时可见的数据更少，
`n_effective` 与 `data_completeness` 都不应更大），要么明确报
「该时点没有评价结果」并以非零退出码结束 —— **不得**返回与 2026 相同的结果
（那意味着评价没有按 `available_at <= decision_at` 解析，是前视偏差），
也**不得**现场重算一个「今天的值」冒充当时的快照（FR-PEER-002）。

- [ ] **Step 7: 全量检查**

Run: `make check && .venv/bin/pytest tests/contract -v -m contract`

Expected: lint、typecheck、全部单元/集成/适应度/契约测试通过，
既有 281 条一条不少。

Run: `.venv/bin/alembic -x db=dev revision --autogenerate -m "final-probe" --sql | head -60`

Expected: 报告零操作（G-16）。探针文件用完即删。

Run: `.venv/bin/pytest tests/integration/test_temporal_constraints.py -k snapshot -q`

Expected: 通过。若 Task 7/8 改动过 CHECK 约束而没重新生成黄金快照，这里会红
（G-17：autogenerate 对 CHECK 表达式失明，这条快照才是防线）。

- [ ] **Step 8: 提交**

```bash
git add -A
git commit -m "feat(cli): Plan-2 端到端 —— 因子、评分、排名、分层与候选池

show-evaluation 的输出结构本身是可验收项：Tier 与组内 Sharpe / MDD 中位数
同屏（G-9），Data Completeness 与 Score 同屏（G-4），UNAVAILABLE 渲染为
UNAVAILABLE 而非 0.00（G-3），三者均由测试断言。
Universe 规模不足时快照留痕但 CLI 以非零退出码阻断。
全部核对改用 python 而非 psql（本机 psql 不在 PATH）。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SZBJBiDWT8FHcx7NhkgcTD"
```

---

## 起草 Task 14–18 时发现的矛盾与遗漏

按 Plan-1 的做法如实登记。**前四条需要在执行 Task 14 之前裁定**，
其余是本稿已经自行裁定、但应回填进设计定案或接口契约的项。

### C-1【严重 · 阻塞 Task 16】`derive_eligibility` 的 `HOLD_ONLY` / `EXIT_ONLY` 与上游语义颠倒

上游 §2.13 三处**完全一致**（`05-fund-selection.md:217-223` = `02-business-requirements.md:1232-1238`
= `03-data/02-data-domain-model.md:400-406`）：

| 状态 | 含义 | 可建仓 | 可加仓 | 可持有 | 可减仓 |
|---|---|:---:|:---:|:---:|:---:|
| `HOLD_ONLY` | **暂停申购** | ✗ | ✗ | ✓ | ✓ |
| `NOT_TRADABLE` | 已清盘 / **暂停赎回** | ✗ | ✗ | — | ✗ |

而 Plan-1 的 `src/fip/services/data_service/eligibility.py:56-61` 是：

```python
    if subscription_open and not redemption_open:
        return EligibilityStatus.HOLD_ONLY      # 暂停【赎回】→ 上游说这是 NOT_TRADABLE
    if not subscription_open and redemption_open:
        return EligibilityStatus.EXIT_ONLY      # 暂停【申购】→ 上游说这是 HOLD_ONLY
```

两个分支相对上游语义**互换了**。该文件自己的注释
（`HOLD_ONLY = 可持有、可加仓，不可减仓`）也与上游的「可加仓 ✗」直接冲突。

**为什么这在 Plan-2 才变成严重问题**：Plan-1 里这个函数的产出没有消费方，错了也不显形。
Task 16 一旦按 §9.3 的处理表消费它，后果立刻是实质性的：

- 暂停申购的基金（常见、良性、暂停期结束就恢复）被判 `EXIT_ONLY` → **不入池**；
- 暂停赎回的基金（真正不可交易的那一类）被判 `HOLD_ONLY` → **入池并标注约束**。

即：该排除的进了池，不该排除的被赶了出去，而全部条件结果照常落库、
没有任何一条测试会红。

**需要的裁定**：修正 `derive_eligibility`（属 Plan-1 交接性质的修复，
建议并入 Task 1），还是认定上游那张表在本项目语境下需要改写。
两者选其一，但**不能带着这个不一致进 Task 16** ——
本稿 Task 16 的处理表是照上游写的。

### C-2【须裁定】子分层权重：上游既禁止拍板，又没有给值，而 Tier 依赖总分

`FS:301-304` 只把**因子层**权重定案为 `EQUAL_WITHIN_VALID`，**子分层**推给
「由 Profile 定义」；`§8.5` 只定了个别因子在个别画像下的相对高低
（费率 / MDD / Alpha / TE），**四项在 M1 全都不可算**；
而 `BR:278` 明确禁止「现在拍一个 25% / 25% / 25% / 25%」，`FS:299` 要求「不得事先拍板权重」。

于是：没有子分权重 → 没有总分 → 没有 Tier → M1.4 的验收标准通不过。
**这正是 D-1 用来把因子有效性检验拉进 Plan-2 的同一条论证链，只是发生在上一层，
而设计定案没有处理它。**

本稿的处置：`sub_score_weights` 五项各 `0.2`，标 **PROVISIONAL**，
`source` 写明「上游禁止拍板但未给值」，于是 LIVE 模式下每次取用都会发出
`ProvisionalParameterUsed`。但这应当是设计定案里的一条正式裁定（建议编号 D-22），
不该由 Task 14 的实现者顺手决定 —— 它与因子层的 `EQUAL_WITHIN_VALID` **性质不同**：
后者已定案，前者是占位。

### C-3【须裁定】`data_completeness` 的分母与 D-8 的「10 个因子」冲突

- D-8 把 REL 全类**扣出** M1 因子清单，得到 10 个；任务总览里 Task 9 也叫「10 个因子的纯函数」。
- 但 spec §6.2 与 M1.4 完成判据要求「Relative Performance Score 正确呈现为 `UNAVAILABLE`
  **且 `Data Completeness` 反映之**」，理由是「基于 4 个子分的 85 分与基于 5 个子分的
  85 分必须可区分」。

若 Profile 声明的因子数 = 可算的 10 个，则 `data_completeness ≡ 1.0`，
**上面那句「必须可区分」就被静默抹掉了** —— M1 用来跑通 `UNAVAILABLE` 机制的
唯一场景随之消失。

本稿的处置：区分**声明**与**可算** —— Profile 声明 13 个（10 可算 + 3 个 REL），
分母取 13，M1 的 `data_completeness` 恒为 `10/13 = 0.76923077`。
三个 REL ID 取 D-8 自己点名的、从现存文档中泄露出的真实 ID
（`F-REL-002` Alpha / `F-REL-003` Beta / `F-REL-004` IR）；
Tracking Error 与 Benchmark 超额收益**不声明**，因为它们的真实 ID 未泄露，
凭空编号会在拿到正式文档时与真 ID 冲突。

**需要回填的地方**：接口契约里 `FACTOR_IDS`（Task 9）若定义成恰好 10 个，
Task 14 的分母会静默变回 10。「声明 13 / 可算 10」这个区分必须写进契约，
否则它活不过两个任务。

### C-4【须裁定】`score_status` 的五个取值没有优先级，且两个层级被混用

D-19 定下五值，但三份上游文档都没说**同时成立时取哪个**。M1 的常态里这不是假设性问题：
REL 子分 `UNAVAILABLE`（→ 基金层 `PARTIAL`）与某个子分有效因子数 < 2
（→ `INSUFFICIENT_FACTORS`）会同时发生。

另外 `FS:344` 说的是「某**子分**标 `INSUFFICIENT_FACTORS`」，而 D-19 把它列为
**`score_status`**（基金层）的取值 —— 两个层级被混进同一个枚举。

本稿的处置：同一枚举用于两层（取值含义一致），基金层优先级钉为
`VALIDATION_PENDING > UNAVAILABLE > INSUFFICIENT_FACTORS > PARTIAL > COMPLETED`，
理由是「越靠前的状态越是『这个分数不能按字面使用』的强信号」。
这是**补齐**，应回填设计定案。

### C-5 `N = 1` 的形态与 `fund_ranking` 的联动 CHECK 不相容

- `FR §7.3`：`N = 1` → `Percentile = UNAVAILABLE`（此时 `Rank = 1` 是存在的）。
- `04-database-design.md:722-728` 的联动 CHECK 只允许两种形态：
  `(NORMAL ∧ rank NOT NULL ∧ percentile NOT NULL)` 或
  `(INSUFFICIENT_SAMPLE ∧ rank IS NULL ∧ percentile IS NULL)`。

**没有第三种形态能容纳「有名次但无分位」。** 本稿把 `N = 1` 归入
`INSUFFICIENT_SAMPLE`（生产配置下 `1 < 30` 恒成立，语义无损），并用一条测试钉住。
若将来 `MIN_PEER_GROUP_SIZE` 被调到 1，这条冲突会立刻显形。

### C-6 接口契约的缺口（本稿已钉定，须回填）

契约自称唯一权威，但 Task 14–18 需要的这些名字它一个都没有：

| 缺失 | 谁产出 → 谁消费 | 本稿的处置 |
|---|---|---|
| `FactorEffectiveness` 的形状 | Task 13 → 14 | 定义在 `score/subscore.py` |
| `FACTOR_IDS` / `preference_direction(fid)` | Task 9 → 17 | 按此签名调用 |
| `EvaluationProfile` 的形状与**由谁装载** | 配置 → 14/17 | 类型在 Task 14；**`config/strategy/factor/v1.yaml` 在 18 个任务里没有归属**（File Structure 写着「新建」），建议归 Task 9 |
| `factor` / `evaluation` 两组 ORM 类名与模块路径 | Task 7/8 → 15/16/17 | 见本稿开头「本稿钉定的上游接口」 |
| Task 15/16 的产出类型（`RankingResult` / `TierResult` / `SelectionOutcome` 等） | 15/16 → 17/18 | 本稿定义 |

### C-7 QE-1 / SDL-1 的适应度断言字符串在 P2-1 之后已失效

D-3 表里 QE-1 写「不得 import **`fip.libs.strategy_library`**」，
P2-1 撤销了 `libs/` 落位却没有同步这一行 —— 照抄该字符串写出的检查**永远不会触发**
（真实路径是 `fip.strategy_library`）。这与 D-4 指责 SB-1「静默缺席」是同一种病，
只是换成了「检查存在但永远为真」。

同一张表里 SDL-1 的「不得 import `fip.services.*.repositories`」这一半，
在现有 `tests/fitness/test_architecture.py` 里**也没有实现** ——
那条测试查的是 `IO_LIBS`（`sqlalchemy` / `psycopg` / `requests` …）这组**顶层包名**，
根本不检查 `fip.services.*` 前缀。Task 4 落实 SDL-1 时必须把这一半补上。

### C-8 三处文档未裁决项，本稿自行裁定（须回填）

| # | 文档状态 | 本稿裁定 |
|---|---|---|
| BLOCK-9 | 「组内 Sharpe 中位数 / MDD 中位数」落 `fund_tier` 还是 `peer_group_snapshot`，**文档未裁决**，设计定案无对应条目 | 落 `fund_tier`，每行自带。落 `peer_group_snapshot` 需要多一次 join 才能满足 G-9，而「少 join 一次就违规」的约束活不长 |
| TBD-DBD-3 | `fund_score_attribution` 的存储策略（完整明细表 / JSONB / 仅存当前）**未定案** | 完整明细表（`03-erd §9.3`：进入 `WHERE` / `GROUP BY` 的字段必须结构化，归因分析需要按 `factor_id` 聚合） |
| —— | `fund_score` / `fund_ranking` / `fund_tier` 的唯一约束**是否含 `profile_id`**，Task 8 的建表要点里没有提 | **必须含**。G-10 要求按 Profile 拆分子排名；不含 `profile_id` 的唯一键会在 M2 加第二个 Profile 的那一天变成主键冲突，而 M1 全程不会显形 |

### C-9 A-2 判据的期望值依赖 C-3 的裁定

Task 18 的判据 A-2 期望 `data_completeness = 0.76923077`（10/13）。
若 C-3 被裁定为「分母只算可算因子」，该期望值应改为 `1.0` ——
但那样一来 A-2 就退化成一条恒真的判据，M1.4 的完成判据
「`Data Completeness` 反映之」也随之失去被验证的对象。
**这条依赖关系是有意写出来的**：A-2 的期望值是 C-3 裁定结果的直接函数，
改一个必须改另一个。
