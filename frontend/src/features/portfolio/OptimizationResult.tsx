import type {
  Optimization,
  OptimizationMeta,
} from "../../api/generated/m17.schemas";
import { MetricValue } from "../../components/MetricValue";
import { ProvenanceBar } from "../../components/ProvenanceBar";
import { formatPercent } from "../../components/Formatters";

const statusLabels: Record<string, string> = {
  OPTIMAL: "最优解（OPTIMAL）",
  INFEASIBLE: "无可行解（INFEASIBLE）",
  UNBOUNDED: "目标无界（UNBOUNDED）",
  NOT_CONVERGED: "未收敛（NOT_CONVERGED）",
  NUMERICAL_ERROR: "数值错误（NUMERICAL_ERROR）",
};

const StringList = ({ label, values }: { label: string; values: string[] }) => (
  <section aria-label={label}>
    <h3>{label}</h3>
    {values.length === 0 ? (
      <p>无</p>
    ) : (
      <ul>
        {values.map((value) => (
          <li key={value}>{value}</li>
        ))}
      </ul>
    )}
  </section>
);

export const OptimizationResult = ({
  optimization,
  meta,
}: {
  optimization: Optimization;
  meta: OptimizationMeta;
}) => {
  const isOptimal = optimization.optimization_status === "OPTIMAL";
  return (
    <section aria-label="优化结果">
      <h2>优化结果</h2>
      <strong>
        {statusLabels[optimization.optimization_status] ??
          `未知状态（${optimization.optimization_status}）`}
      </strong>
      {isOptimal && optimization.target_weights ? (
        <section aria-label="目标权重">
          <h3>目标权重</h3>
          {optimization.target_weights.map((weight) => (
            <div key={weight.fund_id}>
              {weight.fund_id} {formatPercent(weight.weight)}
            </div>
          ))}
        </section>
      ) : (
        <p>非 OPTIMAL 结果不产出权重。</p>
      )}
      <p>
        目标值：
        <MetricValue
          value={optimization.objective_value}
          status={optimization.objective_value_status}
          reason={optimization.objective_value_reason}
        />
      </p>
      <p>
        优化后波动率：
        <MetricValue
          value={optimization.post_optimization_risk.portfolio_volatility}
          status={
            optimization.post_optimization_risk.portfolio_volatility_status
          }
          reason={
            optimization.post_optimization_risk.portfolio_volatility_reason
          }
          format="percent"
        />
      </p>
      <StringList
        label="约束诊断"
        values={optimization.conflicting_constraints}
      />
      <StringList label="绑定约束" values={optimization.binding_constraints} />
      <section aria-label="排除候选">
        <h3>排除候选</h3>
        {optimization.excluded_candidates.map((candidate) => (
          <div key={candidate.fund_id}>
            {candidate.fund_id}：{candidate.reason}
          </div>
        ))}
      </section>
      <p>求解路径：{optimization.solve_path}</p>
      <ProvenanceBar meta={meta} />
      <dl>
        <dt>组合规则版本</dt>
        <dd>{meta.portfolio_rule_version}</dd>
        <dt>收益估计版本</dt>
        <dd>{meta.return_estimate_version}</dd>
        <dt>风险模型版本</dt>
        <dd>{meta.risk_model_version}</dd>
        <dt>代码版本</dt>
        <dd>{meta.code_version}</dd>
      </dl>
    </section>
  );
};
