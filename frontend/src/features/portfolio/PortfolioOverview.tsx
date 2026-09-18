import type { Portfolio } from "../../api/generated/m17.schemas";

export const PortfolioOverview = ({ portfolio }: { portfolio: Portfolio }) => (
  <section aria-label="组合概览">
    <h1>{portfolio.portfolio_name}</h1>
    <dl>
      <dt>组合 ID</dt>
      <dd>{portfolio.portfolio_id}</dd>
      <dt>状态</dt>
      <dd>{portfolio.status}</dd>
      <dt>风险画像</dt>
      <dd>{portfolio.risk_profile}</dd>
      <dt>基准</dt>
      <dd>{portfolio.portfolio_benchmark.benchmark_name}</dd>
      <dt>组合版本</dt>
      <dd>{portfolio.portfolio_version}</dd>
      <dt>组合规则版本</dt>
      <dd>{portfolio.portfolio_rule_version}</dd>
    </dl>
  </section>
);
