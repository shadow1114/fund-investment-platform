export const responseMeta = {
  request_id: "REQ-M17-SMOKE",
  as_of_date: "2026-09-16",
  data_version: "market-v12",
  versions: {
    classification_version: "class-v3",
    factor_version: "factor-v8",
  },
  is_point_in_time: true,
  availability_quality_distribution: {
    EXACT: 1,
    DERIVED: 0,
    INFERRED: 0,
  },
};

export const errorEnvelope = (code: string) => ({
  data: null,
  meta: { request_id: `REQ-${code}` },
  error: {
    code,
    message: `Contract fixture for ${code}`,
    details: {},
  },
});

export const fundListEnvelope = {
  data: [
    {
      fund_id: "000001",
      fund_name: "Alpha 稳健基金",
      share_class: "A",
      fund_classification: "EQUITY",
      management_company_id: "MC-1",
      inception_date: "2020-01-02",
      lifecycle_status: "NORMAL",
      investment_eligibility: "FULLY_ELIGIBLE",
    },
  ],
  meta: {
    ...responseMeta,
    pagination: {
      page: 1,
      page_size: 20,
      total_items: 1,
      total_pages: 1,
    },
  },
  error: null,
};

export const fundDetailEnvelope = {
  data: {
    ...fundListEnvelope.data[0],
    classification_version: "class-v3",
    manager_ids: ["M-1"],
    benchmark: {
      benchmark_id: "CSI300",
      benchmark_name: "沪深300",
      benchmark_type: "INDEX",
      mapping_version: "map-v2",
      components: null,
    },
    fee_structure: [],
  },
  meta: responseMeta,
  error: null,
};

export const fundNavEnvelope = {
  data: {
    fund_id: "000001",
    points: [
      { date: "2026-09-16", nav: 1.24, nav_status: "VALID", nav_reason: null },
    ],
  },
  meta: {
    ...responseMeta,
    nav_type: "ADJUSTED",
    adjustment_convention: "BACKWARD",
    adjustment_rule_version: "adj-v2",
    unavailable_count: 0,
  },
  error: null,
};

export const fundEvaluationEnvelope = {
  data: {
    fund_id: "000001",
    evaluation_period: "1Y",
    as_of_date: "2026-09-16",
    evaluation_status: "WARNING",
    evaluation_profile: "research-v1",
    data_completeness: { available: 250, expected: 252 },
    factor_results: [],
  },
  meta: {
    ...responseMeta,
    peer_group_id: "PG-1",
    peer_group_version: "pg-v3",
    evaluation_policy_version: "eval-v4",
    factor_version: "factor-v5",
  },
  error: null,
};

export const fundScoreEnvelope = {
  data: {
    fund_id: "000001",
    evaluation_period: "1Y",
    as_of_date: "2026-09-16",
    total_score: null,
    total_score_status: "UNAVAILABLE",
    total_score_reason: "INSUFFICIENT_SAMPLE",
    sub_scores: {
      return_score: null,
      return_score_status: "UNAVAILABLE",
      return_score_reason: "INSUFFICIENT_SAMPLE",
      risk_score: 71.2,
      risk_score_status: "VALID",
      risk_score_reason: null,
      risk_adjusted_score: null,
      risk_adjusted_score_status: "UNAVAILABLE",
      risk_adjusted_score_reason: "INSUFFICIENT_SAMPLE",
      stability_score: 68,
      stability_score_status: "VALID",
      stability_score_reason: null,
      relative_performance_score: 63,
      relative_performance_score_status: "VALID",
      relative_performance_score_reason: null,
    },
    attribution: [],
    data_completeness: { available: 0, expected: 5 },
    score_status: "PARTIAL",
  },
  meta: {
    ...responseMeta,
    peer_group_id: "PG-1",
    peer_group_version: "pg-v3",
    scoring_policy_version: "score-v7",
    evaluation_policy_version: "eval-v4",
    factor_version: "factor-v5",
  },
  error: null,
};

export const universeListEnvelope = {
  data: [
    {
      universe_id: "UNI-001",
      strategy_id: "low-volatility",
      decision_at: "2026-09-16T08:30:00Z",
      universe_strategy: "A",
      member_count: 1,
      eligibility_rules_version: "eligibility-v4",
      scoring_policy_version: null,
    },
  ],
  meta: responseMeta,
  error: null,
};

const unavailableMemberFields = {
  total_score: null,
  total_score_status: "UNAVAILABLE",
  total_score_reason: "ELIGIBILITY_ONLY",
  rank: null,
  rank_status: "UNAVAILABLE",
  rank_reason: "ELIGIBILITY_ONLY",
  percentile: null,
  percentile_status: "UNAVAILABLE",
  percentile_reason: "ELIGIBILITY_ONLY",
  fund_tier: null,
};

export const universeDetailEnvelope = {
  data: {
    universe_id: "UNI-001",
    decision_at: "2026-09-16T08:30:00Z",
    universe_strategy: "A",
    members: [
      {
        fund_id: "000001",
        selection_status: "SELECTED",
        ...unavailableMemberFields,
        investment_eligibility: "FULLY_ELIGIBLE",
        passed_conditions: [
          {
            condition: "minimum_track_record_years",
            actual: 5.2,
            result: "PASS",
            gap: 2.2,
          },
        ],
        failed_conditions: [],
      },
    ],
    excluded: [
      {
        fund_id: "000002",
        selection_status: "REJECTED",
        ...unavailableMemberFields,
        total_score_status: "EXCLUDED",
        total_score_reason: "FAILED_ELIGIBILITY",
        rank_status: "EXCLUDED",
        rank_reason: "FAILED_ELIGIBILITY",
        percentile_status: "EXCLUDED",
        percentile_reason: "FAILED_ELIGIBILITY",
        investment_eligibility: "NOT_TRADABLE",
        passed_conditions: [],
        failed_conditions: [
          {
            condition: "minimum_aum",
            actual: 8_000_000,
            result: "FAIL",
            gap: -2_000_000,
          },
        ],
      },
    ],
  },
  meta: {
    ...responseMeta,
    eligibility_rules_version: "eligibility-v4",
    scoring_policy_version: null,
  },
  error: null,
};

export const portfolio = {
  portfolio_id: "P001",
  portfolio_name: "稳健组合",
  portfolio_type: "MUTUAL_FUND",
  status: "ACTIVE",
  base_currency: "CNY",
  portfolio_version: "portfolio-v12",
  risk_profile: "BALANCED",
  portfolio_benchmark: {
    benchmark_id: "CSI300",
    benchmark_name: "沪深300",
  },
  portfolio_rule_version: "rule-v7",
};

export const portfolioListEnvelope = {
  data: [portfolio],
  meta: {
    ...responseMeta,
    pagination: {
      page: 1,
      page_size: 20,
      total_items: 1,
      total_pages: 1,
    },
  },
  error: null,
};

export const portfolioEnvelope = {
  data: portfolio,
  meta: responseMeta,
  error: null,
};

export const sessionEnvelope = {
  data: {
    user_id: "USR-001",
    roles: ["Researcher"],
    capabilities: {
      can_review_decisions: false,
      can_review_classifications: false,
      can_manage_data_ingestion: false,
    },
  },
  meta: { request_id: "REQ-SESSION" },
  error: null,
};

export const fundIngestionListEnvelope = {
  data: [],
  meta: responseMeta,
  error: null,
};

export const fundIngestionSubmissionEnvelope = {
  data: {
    operation_id: "ING-001",
    fund_id: "1001",
    fund_ids: ["1001"],
    dataset: "NAV",
    status: "RUNNING",
  },
  meta: responseMeta,
  error: null,
};

export const fundBasicInfoHistoryEnvelope = {
  data: [],
  meta: responseMeta,
  error: null,
};

export const operationEnvelope = {
  data: {
    operation_id: "OP-001",
    status: "COMPLETED",
    progress: { completed: 1, total: 1, unit: "steps" },
    result_ref: "/api/v1/portfolios/P001/optimizations/OPT-001",
    failure: null,
  },
  meta: responseMeta,
  error: null,
};

export const backtestCreatedEnvelope = {
  data: {
    backtest_id: "BT-001",
    status: "CREATED",
    created_at: "2026-09-19T08:00:00Z",
  },
  meta: responseMeta,
  error: null,
};

export const backtestValidationEnvelope = {
  data: {
    validation_result: "PASS_WITH_WARNINGS",
    warm_up_end_date: "2021-01-04",
    effective_period: { from: "2021-01-04", to: "2026-06-30" },
    in_sample_length_days: 1091,
    out_of_sample_length_days: 912,
    warnings: [{ code: "OOS_PERIOD_SHORT", message: "样本外区间偏短" }],
    blocking_issues: [],
  },
  meta: responseMeta,
  error: null,
};

export const backtestRunEnvelope = {
  data: { operation_id: "OP-BT-1", backtest_id: "BT-001", status: "RUNNING" },
  meta: responseMeta,
  error: null,
};

export const backtestOperationEnvelope = {
  data: {
    operation_id: "OP-BT-1",
    status: "COMPLETED",
    progress: { completed: 6, total: 6, unit: "periods" },
    result_ref: "/api/v1/backtests/BT-001/result",
    failure: null,
  },
  meta: responseMeta,
  error: null,
};

export const backtestStatusEnvelope = {
  data: {
    backtest_id: "BT-001",
    status: "COMPLETED",
    validation_status: "INVALID",
    progress: {
      current_decision_date: "2026-06-30",
      completed_periods: 6,
      total_periods: 6,
      total_periods_is_estimate: false,
    },
    started_at: "2026-09-19T08:01:00Z",
  },
  meta: responseMeta,
  error: null,
};

const backtestMetrics = {
  total_return: 0.12,
  annualized_return: 0.0742,
  volatility: 0.13,
  max_drawdown: 0.08,
  sharpe_ratio: null,
  sharpe_ratio_status: "UNAVAILABLE",
  sharpe_ratio_reason: "INSUFFICIENT_SAMPLE",
};

export const backtestResultEnvelope = {
  data: {
    backtest_id: "BT-001",
    status: "COMPLETED",
    validation_status: "INVALID",
    backtest_mode: "CURRENT_RULE",
    period: {
      start_date: "2020-01-01",
      end_date: "2026-06-30",
      warm_up_end_date: "2021-01-04",
    },
    initial_capital: { amount: "1000000.00", currency: "CNY" },
    final_value: { amount: "1120000.00", currency: "CNY" },
    summary: {
      portfolio: backtestMetrics,
      benchmark: backtestMetrics,
      equal_weight_baseline: null,
      equal_weight_baseline_status: "UNAVAILABLE",
      equal_weight_baseline_reason: "BASELINE_DISABLED",
    },
    excess_return: {
      vs_benchmark: 0.018,
      vs_benchmark_status: "VALID",
      vs_benchmark_reason: null,
      vs_equal_weight: null,
      vs_equal_weight_status: "UNAVAILABLE",
      vs_equal_weight_reason: "BASELINE_DISABLED",
    },
    significance_verdict: {
      overall: "CANNOT_DETERMINE",
      thresholds_status: "PENDING_CALIBRATION",
      layers: {
        statistical: {
          passed: null,
          passed_status: "UNAVAILABLE",
          passed_reason: "THRESHOLDS_PENDING",
          bootstrap_ci_lower_vs_benchmark: null,
          bootstrap_ci_lower_vs_benchmark_status: "UNAVAILABLE",
          bootstrap_ci_lower_vs_benchmark_reason: "INSUFFICIENT_SAMPLE",
          bootstrap_ci_lower_vs_equal_weight: null,
          bootstrap_ci_lower_vs_equal_weight_status: "UNAVAILABLE",
          bootstrap_ci_lower_vs_equal_weight_reason: "BASELINE_DISABLED",
        },
        effect_size: {
          passed: null,
          passed_status: "UNAVAILABLE",
          passed_reason: "THRESHOLDS_PENDING",
          ir_vs_benchmark: null,
          ir_vs_benchmark_status: "UNAVAILABLE",
          ir_vs_benchmark_reason: "INSUFFICIENT_SAMPLE",
          ir_vs_equal_weight: null,
          ir_vs_equal_weight_status: "UNAVAILABLE",
          ir_vs_equal_weight_reason: "BASELINE_DISABLED",
          delta_sharpe_vs_benchmark: null,
          delta_sharpe_vs_benchmark_status: "UNAVAILABLE",
          delta_sharpe_vs_benchmark_reason: "INSUFFICIENT_SAMPLE",
          delta_sharpe_vs_equal_weight: null,
          delta_sharpe_vs_equal_weight_status: "UNAVAILABLE",
          delta_sharpe_vs_equal_weight_reason: "BASELINE_DISABLED",
        },
        robustness: {
          passed: null,
          passed_status: "UNAVAILABLE",
          passed_reason: "THRESHOLDS_PENDING",
          outperform_ratio_vs_benchmark: null,
          outperform_ratio_vs_benchmark_status: "UNAVAILABLE",
          outperform_ratio_vs_benchmark_reason: "INSUFFICIENT_SAMPLE",
          outperform_ratio_vs_equal_weight: null,
          outperform_ratio_vs_equal_weight_status: "UNAVAILABLE",
          outperform_ratio_vs_equal_weight_reason: "BASELINE_DISABLED",
        },
        economic: {
          passed: null,
          passed_status: "UNAVAILABLE",
          passed_reason: "THRESHOLDS_PENDING",
          annualized_return_improvement_vs_benchmark: null,
          annualized_return_improvement_vs_benchmark_status: "UNAVAILABLE",
          annualized_return_improvement_vs_benchmark_reason:
            "INSUFFICIENT_SAMPLE",
          annualized_return_improvement_vs_equal_weight: null,
          annualized_return_improvement_vs_equal_weight_status: "UNAVAILABLE",
          annualized_return_improvement_vs_equal_weight_reason:
            "BASELINE_DISABLED",
          max_drawdown_improvement_vs_benchmark: null,
          max_drawdown_improvement_vs_benchmark_status: "UNAVAILABLE",
          max_drawdown_improvement_vs_benchmark_reason: "INSUFFICIENT_SAMPLE",
          max_drawdown_improvement_vs_equal_weight: null,
          max_drawdown_improvement_vs_equal_weight_status: "UNAVAILABLE",
          max_drawdown_improvement_vs_equal_weight_reason: "BASELINE_DISABLED",
        },
      },
    },
    validation_summary: {
      warnings: ["TRADABILITY_NOT_VERIFIED"],
      invalid_reasons: ["BIAS_CHECK_INCOMPLETE"],
    },
  },
  meta: {
    ...responseMeta,
    configuration_version: "config-v1",
    code_version: "backtest-1.4.0",
    transaction_cost_model_version: "cost-v2",
  },
  error: null,
};

const backtestPoint = (value: number) => ({
  date: "2026-06-30",
  value,
  value_status: "VALID",
  value_reason: null,
});

export const backtestPerformanceEnvelope = {
  data: {
    segment: "FULL",
    series: {
      portfolio_value: [backtestPoint(1120000)],
      cumulative_return: {
        portfolio: [backtestPoint(0.12)],
        benchmark: [backtestPoint(0.1)],
        equal_weight_baseline: null,
        equal_weight_baseline_status: "UNAVAILABLE",
        equal_weight_baseline_reason: "BASELINE_DISABLED",
      },
      drawdown: [backtestPoint(-0.08)],
      rolling_sharpe: [],
      rolling_excess_return: [],
    },
  },
  meta: responseMeta,
  error: null,
};

export const backtestBiasEnvelope = {
  data: {
    backtest_id: "BT-001",
    checks: {
      look_ahead_bias: { status: "PASS", violations: [] },
      survivorship_bias: { status: "PASS", violations: [] },
      tradability_bias: {
        status: "NOT_VERIFIED",
        reason: "INVESTMENT_ELIGIBILITY_HISTORY_INCOMPLETE",
      },
      point_in_time: { status: "PASS" },
      transaction_cost: {
        status: "PARTIALLY_MODELED",
        unmodeled_costs: ["BID_ASK_SPREAD"],
      },
      subscription_redemption_lag: { status: "NOT_MODELED" },
    },
    snapshot_summary: {
      snapshot_periods: 56,
      rebuilt_periods: 12,
      total_periods: 68,
      rebuilt_period_list: [],
    },
    data_limitations: ["历史可投资性数据不完整"],
  },
  meta: responseMeta,
  error: null,
};
