import { QueryClient } from "@tanstack/react-query";

type HttpError = { status?: number };

const isNonRetryable = (error: unknown) =>
  [401, 403, 404, 422].includes((error as HttpError)?.status ?? 0);

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        if (isNonRetryable(error)) return false;
        return failureCount < 3 && ((error as HttpError)?.status ?? 500) >= 500;
      },
    },
  },
});
