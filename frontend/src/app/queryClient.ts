import { QueryClient } from "@tanstack/react-query";

type HttpError = { status?: number };

const statusOf = (error: unknown) => (error as HttpError)?.status;

const isNonRetryable = (error: unknown) =>
  [401, 403, 404, 422].includes(statusOf(error) ?? 0);

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        if (isNonRetryable(error)) return false;
        const status = statusOf(error);
        return (
          failureCount < 3 &&
          typeof status === "number" &&
          status >= 500 &&
          status <= 599
        );
      },
    },
  },
});
