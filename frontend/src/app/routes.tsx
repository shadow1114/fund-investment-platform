import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

const Page = ({ title }: { title: string }) => (
  <main>
    <h1>{title}</h1>
  </main>
);

export const routes: { path: string; element: ReactNode }[] = [
  { path: "/", element: <Navigate replace to="/funds" /> },
  { path: "/funds", element: <Page title="基金研究" /> },
  { path: "/universes", element: <Page title="候选池" /> },
  { path: "/portfolios", element: <Page title="组合决策" /> },
  { path: "/backtests", element: <Page title="回测" /> },
];
