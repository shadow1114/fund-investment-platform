import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";
import { listFunds } from "./generated/m17";
import {
  fundPageQueryOptions,
  invalidateIngestionFundData,
  listFundsQueryOptions,
  queryKeys,
} from "./queries";

vi.mock("./generated/m17", () => ({ listFunds: vi.fn() }));

describe("fund list query contract", () => {
  beforeEach(() => vi.clearAllMocks());

  it("requires subscription status provenance metadata", async () => {
    vi.mocked(listFunds).mockResolvedValue({
      status: 200,
      data: {
        data: [],
        meta: {
          as_of_date: "2026-11-03",
          data_version: "api-v1",
          versions: {},
          is_point_in_time: false,
          availability_quality_distribution: {
            EXACT: 0,
            DERIVED: 0,
            INFERRED: 0,
          },
          pagination: {
            page: 1,
            page_size: 20,
            total_items: 0,
            total_pages: 0,
          },
        },
        error: null,
      },
      headers: new Headers(),
    } as never);

    const options = listFundsQueryOptions();
    await expect(options.queryFn!({} as never)).rejects.toMatchObject({
      code: "CONTRACT_ERROR",
      message: "Response metadata is missing: subscription_status_source",
    });
  });
});

describe("ingestion cache invalidation", () => {
  it("invalidates company options when fund basic information is ingested", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const companyQueryKey = queryKeys.fundManagementCompanies({});
    client.setQueryData(companyQueryKey, {
      data: [{ company_name: "旧公司" }],
    });

    await invalidateIngestionFundData(client);

    expect(client.getQueryState(companyQueryKey)?.isInvalidated).toBe(true);
    expect(client.getQueryData(queryKeys.fundDataRevision)).toBe(1);
    client.clear();
  });

  it("does not reuse a pre-ingestion request for the refreshed fund list", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    let resolveOld!: (value: string) => void;
    const oldRequest = new Promise<string>((resolve) => (resolveOld = resolve));
    const queryFn = vi
      .fn<() => Promise<string>>()
      .mockReturnValueOnce(oldRequest)
      .mockResolvedValueOnce("after-ingestion");
    const requestParams = { page: 1, page_size: 20 };
    const beforeIngestion = fundPageQueryOptions(requestParams, 0);
    const afterIngestion = fundPageQueryOptions(requestParams, 1);
    const pending = client.fetchQuery({
      ...beforeIngestion,
      queryFn,
    } as never) as Promise<string>;
    await vi.waitFor(() => expect(queryFn).toHaveBeenCalledTimes(1));
    const refreshed = await client.fetchQuery({
      ...afterIngestion,
      queryFn,
    } as never);

    expect(queryFn).toHaveBeenCalledTimes(2);
    expect(refreshed).toBe("after-ingestion");
    resolveOld("before-ingestion");
    await pending;
    client.clear();
  });
});
