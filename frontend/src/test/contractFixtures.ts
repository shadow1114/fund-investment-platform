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
    capabilities: { can_review_decisions: false },
  },
  meta: { request_id: "REQ-SESSION" },
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
