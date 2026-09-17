import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Link, useRoutes } from "react-router-dom";

import { queryClient } from "./queryClient";
import { routes } from "./routes";

const Navigation = () => (
  <nav aria-label="主导航">
    {[
      ["基金研究", "/funds"],
      ["候选池", "/universes"],
      ["组合决策", "/portfolios"],
      ["回测", "/backtests"],
    ].map(([label, href]) => (
      <Link key={href} to={href}>
        {label}
      </Link>
    ))}
  </nav>
);

const RoutedApp = () => (
  <>
    <Navigation />
    {useRoutes(routes)}
  </>
);

export const App = () => (
  <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <RoutedApp />
    </BrowserRouter>
  </QueryClientProvider>
);

export default App;
