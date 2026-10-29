import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

import { theme } from "../app/theme";

export const renderWithMantine = (
  element: ReactElement,
  options?: RenderOptions,
) =>
  render(
    <MantineProvider theme={theme} defaultColorScheme="light">
      {element}
    </MantineProvider>,
    options,
  );

export const renderWorkbench = (
  element: ReactElement,
  {
    route = "/",
    queryClient,
  }: { route?: string; queryClient?: QueryClient } = {},
) => {
  const client =
    queryClient ??
    new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
        mutations: { retry: false },
      },
    });

  return render(
    <MantineProvider theme={theme} defaultColorScheme="light">
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[route]}>{element}</MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  );
};
