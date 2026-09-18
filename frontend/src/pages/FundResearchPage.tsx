import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import { listFunds } from "../api/generated/m17";
import type {
  FundListMeta,
  InvestmentEligibility,
  LifecycleStatus,
  ListFundsParams,
  OrderParameter,
} from "../api/generated/m17.schemas";
import { unwrapResponse } from "../api/http";
import { ErrorState } from "../components/ErrorState";
import { ProvenanceBar } from "../components/ProvenanceBar";
import {
  FundFilters,
  type FundFilterValues,
} from "../features/funds/FundFilters";
import { FundTable } from "../features/funds/FundTable";

const split = (value: string | null) =>
  value ? value.split(",").filter(Boolean) : undefined;

const parseParams = (search: URLSearchParams): ListFundsParams => ({
  fund_name: search.get("fund_name") || undefined,
  fund_type: split(search.get("fund_type")),
  lifecycle_status: split(search.get("lifecycle_status")) as
    LifecycleStatus[] | undefined,
  investment_eligibility: split(search.get("investment_eligibility")) as
    InvestmentEligibility[] | undefined,
  as_of_date: search.get("as_of_date") || undefined,
  page: Number(search.get("page") || "1"),
  page_size: Number(search.get("page_size") || "20"),
  sort: search.get("sort") || "fund_name",
  order: (search.get("order") || "asc") as OrderParameter,
});

const initialFilterValues = (search: URLSearchParams): FundFilterValues => ({
  fund_name: search.get("fund_name") || "",
  fund_type: search.get("fund_type") || "",
  lifecycle_status: search.get("lifecycle_status") || "",
  investment_eligibility: search.get("investment_eligibility") || "",
  as_of_date: search.get("as_of_date") || "",
  page_size: search.get("page_size") || "20",
  sort: search.get("sort") || "fund_name",
  order: search.get("order") || "asc",
});

export const FundResearchPage = () => {
  const [search, setSearch] = useSearchParams();
  const serializedSearch = search.toString();
  const params = useMemo(
    () => parseParams(new URLSearchParams(serializedSearch)),
    [serializedSearch],
  );
  const filters = useMemo(
    () => initialFilterValues(new URLSearchParams(serializedSearch)),
    [serializedSearch],
  );
  const query = useQuery({
    queryKey: ["fund-research", params],
    queryFn: async () => {
      const response = await listFunds(params);
      return {
        funds: unwrapResponse(response, {
          requiredMeta: [
            "as_of_date",
            "data_version",
            "versions",
            "is_point_in_time",
            "pagination",
            "availability_quality_distribution",
          ],
        }),
        meta: response.data.meta as FundListMeta,
      };
    },
  });

  const applyFilters = (values: FundFilterValues) => {
    const next = new URLSearchParams();
    Object.entries(values).forEach(([key, value]) => {
      if (value) next.set(key, value);
    });
    next.set("page", "1");
    setSearch(next);
  };
  const changePage = (page: number) => {
    const next = new URLSearchParams(search);
    next.set("page", String(page));
    setSearch(next);
  };

  return (
    <section>
      <h1>基金研究</h1>
      <FundFilters
        key={serializedSearch}
        initialValues={filters}
        onSubmit={applyFilters}
      />
      {query.isPending && <p role="status">正在加载基金…</p>}
      {query.isError && <ErrorState error={query.error} />}
      {query.data && (
        <>
          <ProvenanceBar meta={query.data.meta} />
          {query.data.funds.length === 0 ? (
            <p>没有符合条件的基金</p>
          ) : (
            <FundTable
              funds={query.data.funds}
              asOfDate={query.data.meta.as_of_date}
            />
          )}
          <nav aria-label="基金列表分页">
            <button
              type="button"
              disabled={query.data.meta.pagination.page <= 1}
              onClick={() => changePage(query.data.meta.pagination.page - 1)}
            >
              上一页
            </button>
            <span>
              第 {query.data.meta.pagination.page} /{" "}
              {query.data.meta.pagination.total_pages} 页，共{" "}
              {query.data.meta.pagination.total_items} 只基金
            </span>
            <button
              type="button"
              disabled={
                query.data.meta.pagination.page >=
                query.data.meta.pagination.total_pages
              }
              onClick={() => changePage(query.data.meta.pagination.page + 1)}
            >
              下一页
            </button>
          </nav>
        </>
      )}
    </section>
  );
};
