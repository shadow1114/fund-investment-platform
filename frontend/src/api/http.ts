type ApiFailure = {
  code: string;
  message: string;
  details: Record<string, unknown>;
};

type Envelope = {
  data: unknown;
  meta: Record<string, unknown>;
  error: ApiFailure | null;
};

type GeneratedResponse = {
  status: number;
  data: Envelope;
  headers: Headers;
};

type SuccessfulData<Response> = Response extends {
  data: { error: null; data: infer Data };
}
  ? Data
  : never;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, failure: ApiFailure) {
    super(failure.message);
    this.name = "ApiError";
    this.status = status;
    this.code = failure.code;
    this.details = failure.details;
  }
}

export function unwrapResponse<Response extends GeneratedResponse>(
  response: Response,
): SuccessfulData<Response> {
  if (response.data.error !== null) {
    throw new ApiError(response.status, response.data.error);
  }

  if (response.status < 200 || response.status >= 300) {
    throw new ApiError(response.status, {
      code: "HTTP_ERROR",
      message: `Request failed with status ${response.status}`,
      details: {},
    });
  }

  return response.data.data as SuccessfulData<Response>;
}

export function withIdempotencyKey(key: string): RequestInit {
  return { headers: { "Idempotency-Key": key } };
}
