from __future__ import annotations

# Frozen response component selected by each domain operation.  Session and
# operation responses use their existing shared envelopes and are intentionally
# excluded from this domain registry.
RESPONSE_COMPONENT_REGISTRY: dict[str, str] = {
    "getFund": "FundEnvelope",
    "listFunds": "FundListEnvelope",
    "getFundNavSeries": "NavSeriesEnvelope",
    "getFundEvaluations": "FundEvaluationEnvelope",
    "getFundScores": "FundScoreEnvelope",
    "listUniverses": "UniverseListEnvelope",
    "getUniverse": "UniverseEnvelope",
    "listPortfolios": "PortfolioListEnvelope",
    "getPortfolio": "PortfolioEnvelope",
    "submitOptimization": "OptimizationSubmissionEnvelope",
    "getOptimization": "OptimizationEnvelope",
    "getDecision": "DecisionEnvelope",
    "reviewDecision": "DecisionReviewOutcomeEnvelope",
    "createBacktest": "BacktestCreatedEnvelope",
    "validateBacktest": "BacktestValidationEnvelope",
    "runBacktest": "BacktestRunEnvelope",
    "getBacktestStatus": "BacktestStatusEnvelope",
    "getBacktestResult": "BacktestResultEnvelope",
    "getBacktestPerformance": "BacktestPerformanceEnvelope",
    "getBacktestBiasCheck": "BacktestBiasCheckEnvelope",
}
