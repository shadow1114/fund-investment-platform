export const classificationCatalog = {
  data: {
    scheme: "FIP_CLASSIFICATION_V1",
    rule_version: "1.0.0",
    enum_version: "1.0.0",
    mapping_version: "v1",
    dimensions: {
      asset_class: ["EQUITY", "BOND", "UNKNOWN"],
      strategy: ["ACTIVE", "PASSIVE_INDEX", "UNKNOWN"],
      geography: ["CN", "US", "UNKNOWN"],
      product_structure: ["ETF", "UNKNOWN"],
      market_attributes: ["QDII", "CROSS_BORDER", "UNKNOWN"],
    },
    statuses: ["CONFIRMED", "CANDIDATE", "CONFLICT", "UNKNOWN"],
    confidence_grades: {},
  },
  meta: {},
  error: null,
};
export const emptyClassificationHistory = { data: [], meta: {}, error: null };

export const classificationHistoryEnvelope = {
  data: [
    {
      revision_id: 12,
      version: 1,
      rule_version: "1.0.0",
      enum_version: "1.0.0",
      available_at: "2026-01-01T00:00:00Z",
      classified_at: "2026-01-01T00:00:00Z",
      actor: "fixture-source",
      reason: "正式资料导入",
      reviewed: false,
      intervals: [
        {
          valid_from: "2026-01-01",
          valid_to: null,
          trading_eligibility: null,
          classification: {
            scheme: "FIP_CLASSIFICATION_V1",
            rule_version: "1.0.0",
            enum_version: "1.0.0",
            asset_class: {
              status: "CONFIRMED",
              value: "EQUITY",
              candidates: [],
              evidence: [
                {
                  source: "OFFICIAL",
                  rule_id: "R1",
                  confidence: "OFFICIAL_DOCUMENT",
                  classified_at: "2026-01-01T00:00:00Z",
                  raw_field: "基金类型",
                  raw_value: "股票型",
                  locator: "招募书第3页",
                },
              ],
            },
            strategy: {
              status: "CANDIDATE",
              value: "UNKNOWN",
              candidates: ["ACTIVE"],
              evidence: [],
            },
            geography: {
              status: "UNKNOWN",
              value: ["UNKNOWN"],
              candidates: [],
              evidence: [],
            },
            product_structure: {
              status: "UNKNOWN",
              value: "UNKNOWN",
              candidates: [],
              evidence: [],
            },
            market_attributes: {
              status: "UNKNOWN",
              value: ["UNKNOWN"],
              candidates: [],
              evidence: [],
            },
          },
        },
      ],
    },
  ],
  meta: { as_of_date: "2026-09-16", is_point_in_time: true },
  error: null,
};
