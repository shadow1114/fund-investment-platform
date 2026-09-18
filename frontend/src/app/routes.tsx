import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { FundDetailPage } from "../pages/FundDetailPage";
import { FundResearchPage } from "../pages/FundResearchPage";
import { UniverseSnapshotPage } from "../pages/UniverseSnapshotPage";

const Page = ({ title }: { title: string }) => (
  <main>
    <h1>{title}</h1>
  </main>
);

export const routes: { path: string; element: ReactNode }[] = [
  { path: "/", element: <Navigate replace to="/funds" /> },
  { path: "/funds", element: <FundResearchPage /> },
  { path: "/funds/:fundId", element: <FundDetailPage /> },
  { path: "/universes", element: <UniverseSnapshotPage /> },
  { path: "/universes/:universeId", element: <UniverseSnapshotPage /> },
  { path: "/portfolios", element: <Page title="组合决策" /> },
  { path: "/backtests", element: <Page title="回测" /> },
];
