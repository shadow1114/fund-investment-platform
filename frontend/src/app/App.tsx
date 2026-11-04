import { MantineProvider } from "@mantine/core";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useRoutes } from "react-router-dom";

import { PageLayout } from "../components/PageLayout";
import { queryClient } from "./queryClient";
import { routes } from "./routes";
import { theme } from "./theme";

const RoutedApp = () => <PageLayout>{useRoutes(routes)}</PageLayout>;

export const App = () => (
  <MantineProvider theme={theme} defaultColorScheme="light">
    <QueryClientProvider client={queryClient}>
      <MemoryRouter
        initialEntries={[
          window.location.pathname +
            window.location.search +
            window.location.hash,
        ]}
      >
        <RoutedApp />
      </MemoryRouter>
    </QueryClientProvider>
  </MantineProvider>
);

export default App;
