import { useState, type FormEvent } from "react";

import type { OptimizationRequest } from "../../api/generated/m17.schemas";

type Props = {
  portfolioRuleVersion: string;
  pending: boolean;
  onSubmit: (request: OptimizationRequest) => void;
};

export const OptimizationForm = ({
  portfolioRuleVersion,
  pending,
  onSubmit,
}: Props) => {
  const [decisionAt, setDecisionAt] = useState("");
  const [universeId, setUniverseId] = useState("");
  const [returnVersion, setReturnVersion] = useState("");
  const [riskVersion, setRiskVersion] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit({
      decision_at: decisionAt,
      universe_id: universeId,
      portfolio_rule_version: portfolioRuleVersion,
      return_estimate_version: returnVersion,
      risk_model_version: riskVersion,
      mode: "REBALANCE",
    });
  };

  return (
    <form onSubmit={submit} aria-label="优化输入">
      <h2>发起组合优化</h2>
      <label>
        决策日期
        <input
          type="date"
          required
          value={decisionAt}
          onChange={(event) => setDecisionAt(event.target.value)}
        />
      </label>
      <label>
        候选池 ID
        <input
          required
          value={universeId}
          onChange={(event) => setUniverseId(event.target.value)}
        />
      </label>
      <label>
        组合规则版本
        <input readOnly value={portfolioRuleVersion} />
      </label>
      <label>
        收益估计版本
        <input
          required
          value={returnVersion}
          onChange={(event) => setReturnVersion(event.target.value)}
        />
      </label>
      <label>
        风险模型版本
        <input
          required
          value={riskVersion}
          onChange={(event) => setRiskVersion(event.target.value)}
        />
      </label>
      <button type="submit" disabled={pending}>
        {pending ? "提交中…" : "提交优化"}
      </button>
      <p>只提交版本引用；PIT 校验和估计值取用由服务端执行。</p>
    </form>
  );
};
