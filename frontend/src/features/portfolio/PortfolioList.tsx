import { Link } from "react-router-dom";

import type { PortfolioSummary } from "../../api/generated/m17.schemas";

export const PortfolioList = ({
  portfolios,
}: {
  portfolios: PortfolioSummary[];
}) => (
  <ul aria-label="组合列表">
    {portfolios.map((portfolio) => (
      <li key={portfolio.portfolio_id}>
        <Link to={`/portfolios/${portfolio.portfolio_id}`}>
          {portfolio.portfolio_name}
        </Link>
        <span>
          {portfolio.status} · {portfolio.portfolio_type} ·{" "}
          {portfolio.base_currency}
        </span>
        <span>版本：{portfolio.portfolio_version}</span>
      </li>
    ))}
  </ul>
);
