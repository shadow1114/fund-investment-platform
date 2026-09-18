import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { FundDetailPage } from "../pages/FundDetailPage";
import { FundResearchPage } from "../pages/FundResearchPage";
import { BacktestPage } from "../pages/BacktestPage";
import { PortfolioDecisionPage } from "../pages/PortfolioDecisionPage";
import { UniverseSnapshotPage } from "../pages/UniverseSnapshotPage";

export const routes: { path: string; element: ReactNode }[] = [
  { path: "/", element: <Navigate replace to="/funds" /> },
  { path: "/funds", element: <FundResearchPage /> },
  { path: "/funds/:fundId", element: <FundDetailPage /> },
  { path: "/universes", element: <UniverseSnapshotPage /> },
  { path: "/universes/:universeId", element: <UniverseSnapshotPage /> },
  { path: "/portfolios", element: <PortfolioDecisionPage /> },
  { path: "/portfolios/:portfolioId", element: <PortfolioDecisionPage /> },
  { path: "/backtests", element: <BacktestPage /> },
];
