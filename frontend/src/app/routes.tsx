import { lazy, Suspense, type ReactNode } from "react";
import { Button, Stack, Text } from "@mantine/core";
import { Navigate } from "react-router-dom";
import { Link } from "react-router-dom";

import { WorkspaceHomePage } from "../pages/WorkspaceHomePage";

import { PageHeader } from "../components/PageHeader";
const FundDetailPage = lazy(() =>
  import("../pages/FundDetailPage").then((module) => ({
    default: module.FundDetailPage,
  })),
);
const FundResearchPage = lazy(() =>
  import("../pages/FundResearchPage").then((module) => ({
    default: module.FundResearchPage,
  })),
);
const BacktestPage = lazy(() =>
  import("../pages/BacktestPage").then((module) => ({
    default: module.BacktestPage,
  })),
);
const PortfolioDecisionPage = lazy(() =>
  import("../pages/PortfolioDecisionPage").then((module) => ({
    default: module.PortfolioDecisionPage,
  })),
);
const UniverseSnapshotPage = lazy(() =>
  import("../pages/UniverseSnapshotPage").then((module) => ({
    default: module.UniverseSnapshotPage,
  })),
);
const ClassificationReviewPage = lazy(() =>
  import("../pages/ClassificationReviewPage").then((module) => ({
    default: module.ClassificationReviewPage,
  })),
);

const withLoading = (element: ReactNode) => (
  <Suspense
    fallback={
      <Text role="status" p="lg">
        正在加载页面…
      </Text>
    }
  >
    {element}
  </Suspense>
);

const NotFoundPage = () => (
  <Stack>
    <PageHeader title="页面不存在" breadcrumbs={[{ label: "页面不存在" }]} />
    <Text c="dimmed">请检查地址，或返回工作台继续浏览。</Text>
    <Button component={Link} to="/home" w="fit-content">
      返回工作台
    </Button>
  </Stack>
);

export const routes: { path: string; element: ReactNode }[] = [
  { path: "/home", element: <WorkspaceHomePage /> },
  { path: "/", element: <Navigate replace to="/home" /> },
  {
    path: "/classification-reviews",
    element: withLoading(<ClassificationReviewPage />),
  },
  { path: "/funds", element: withLoading(<FundResearchPage />) },
  { path: "/funds/:fundId", element: withLoading(<FundDetailPage />) },
  { path: "/universes", element: withLoading(<UniverseSnapshotPage />) },
  {
    path: "/universes/:universeId",
    element: withLoading(<UniverseSnapshotPage />),
  },
  { path: "/portfolios", element: withLoading(<PortfolioDecisionPage />) },
  {
    path: "/portfolios/:portfolioId",
    element: withLoading(<PortfolioDecisionPage />),
  },
  { path: "/backtests", element: withLoading(<BacktestPage />) },
  { path: "*", element: <NotFoundPage /> },
];
