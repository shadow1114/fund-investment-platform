import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { ActionIcon } from "@mantine/core";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import type {
  FundListItem,
  InvestmentEligibility,
  LifecycleStatus,
  ListFundsParams,
  OrderParameter,
} from "../api/generated/m17.schemas";
import { getSessionQueryOptions } from "../api/queries";
import {
  FundFilters,
  emptyFundFilters,
  type FundFilterValues,
} from "../features/funds/FundFilters";
import { FundDetailModal } from "../features/funds/FundDetailModal";
import { FundTable } from "../features/funds/FundTable";
import styles from "../features/funds/FundResearchPage.module.css";

const split = (value: string | null) => value?.split(",").filter(Boolean) ?? [];
const asList = (value: string[]) => (value.length > 0 ? value : undefined);
const allowedPageSizes = [20, 50, 200] as const;
const pageSizeFromUrl = (value: string | null) => {
  const parsed = Number(value || 20);
  return allowedPageSizes.includes(parsed as (typeof allowedPageSizes)[number])
    ? parsed
    : 20;
};

export const parseParams = (search: URLSearchParams): ListFundsParams => ({
  asset_class: search.get("asset_class") || undefined,
  strategy: search.get("strategy") || undefined,
  strategy_tags: asList(split(search.get("strategy_tags"))),
  geography: search.get("geography") || undefined,
  product_structure: search.get("product_structure") || undefined,
  market_attributes: search.get("market_attributes") || undefined,
  classification_status: search.get("classification_status") || undefined,
  fund_name: search.get("fund_name") || undefined,
  fund_code: search.get("fund_code") || undefined,
  company_name: search.get("company_name") || undefined,
  sub_status: (search.get("sub_status") || undefined) as
    ListFundsParams["sub_status"] | undefined,
  fund_type: asList(split(search.get("fund_type"))),
  lifecycle_status: asList(split(search.get("lifecycle_status"))) as
    LifecycleStatus[] | undefined,
  investment_eligibility: asList(
    split(search.get("investment_eligibility")),
  ) as InvestmentEligibility[] | undefined,
  as_of_date: search.get("as_of_date") || undefined,
  page: Number(search.get("page") || "1"),
  page_size: pageSizeFromUrl(search.get("page_size")),
  sort: (search.get("sort") || "fund_name") as ListFundsParams["sort"],
  order: (search.get("order") || "asc") as OrderParameter,
});

const initialFilterValues = (search: URLSearchParams): FundFilterValues => ({
  ...emptyFundFilters(),
  asset_class: search.get("asset_class") || "",
  strategy: split(search.get("strategy")),
  strategy_tags: split(search.get("strategy_tags")),
  geography: split(search.get("geography")),
  product_structure: split(search.get("product_structure")),
  market_attributes: split(search.get("market_attributes")),
  classification_status: split(search.get("classification_status")),
  fund_name: search.get("fund_name") || "",
  fund_code: search.get("fund_code") || "",
  company_name: search.get("company_name") || "",
  sub_status: search.get("sub_status") || "",
  fund_type: split(search.get("fund_type")),
  lifecycle_status: split(search.get("lifecycle_status")),
  investment_eligibility: split(search.get("investment_eligibility")),
  as_of_date: search.get("as_of_date") || "",
  page_size: String(pageSizeFromUrl(search.get("page_size"))),
  sort: search.get("sort") || "fund_name",
  order: search.get("order") || "asc",
});

export const serializeFilters = (values: FundFilterValues) => {
  const next = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    const serialized = Array.isArray(value) ? value.join(",") : value;
    if (serialized) next.set(key, serialized);
  });
  next.set("page", "1");
  return next;
};

export const FundResearchPage = () => {
  const [search, setSearch] = useSearchParams();
  const [detailFund, setDetailFund] = useState<FundListItem | null>(null);
  const [queryCollapsed, setQueryCollapsed] = useState(false);
  const session = useQuery(getSessionQueryOptions());
  const serializedSearch = search.toString();
  const params = useMemo(
    () => parseParams(new URLSearchParams(serializedSearch)),
    [serializedSearch],
  );
  const filters = useMemo(
    () => initialFilterValues(new URLSearchParams(serializedSearch)),
    [serializedSearch],
  );
  const appliedFilterKey = serializeFilters(filters).toString();

  const applyFilters = (values: FundFilterValues) =>
    setSearch(serializeFilters(values));
  const resetFilters = () => setSearch(serializeFilters(emptyFundFilters()));
  const changePagination = (page: number, pageSize: number) => {
    const next = new URLSearchParams(search);
    const currentSize = Number(next.get("page_size") || "20");
    next.set("page_size", String(pageSize));
    next.set("page", String(currentSize === pageSize ? page : 1));
    setSearch(next);
  };
  const changeSort = (sort: string, order: "asc" | "desc") => {
    const next = new URLSearchParams(search);
    if (
      next.get("sort") === sort &&
      next.get("order") === order &&
      (next.get("page") ?? "1") === "1"
    )
      return;
    next.set("sort", sort);
    next.set("order", order);
    next.set("page", "1");
    setSearch(next);
  };
  return (
    <div className={styles.researchPage} data-testid="fund-research-page">
      <FundDetailModal
        fund={detailFund}
        asOfDate={params.as_of_date}
        returnTo={"/funds?" + search.toString()}
        onClose={() => setDetailFund(null)}
      />
      <div
        data-testid="fund-research-workspace"
        className={`${styles.workspace} ${queryCollapsed ? styles.workspaceCollapsed : ""}`}
      >
        <section
          id="fund-research-query-panel"
          className={styles.queryPanel}
          aria-label="基金查询条件"
          hidden={queryCollapsed}
        >
          <FundFilters
            key={appliedFilterKey}
            initialValues={filters}
            onSubmit={applyFilters}
            onReset={resetFilters}
          />
        </section>
        <ActionIcon
          className={styles.queryToggle}
          variant="subtle"
          size="lg"
          type="button"
          aria-label={queryCollapsed ? "展开查询条件" : "收起查询条件"}
          aria-expanded={!queryCollapsed}
          aria-controls="fund-research-query-panel"
          onClick={() => setQueryCollapsed((collapsed) => !collapsed)}
        >
          {queryCollapsed ? (
            <ChevronDown aria-hidden="true" />
          ) : (
            <ChevronUp aria-hidden="true" />
          )}
        </ActionIcon>
        <section className={styles.resultsPanel} aria-label="基金研究结果区">
          <div className={styles.gridSurface}>
            <FundTable
              key={serializedSearch}
              params={params}
              onOpenDetail={setDetailFund}
              returnTo={"/funds?" + search.toString()}
              canManageIngestion={
                session.data?.capabilities?.can_manage_data_ingestion ?? false
              }
              onPageChange={changePagination}
              onSortChange={changeSort}
            />
          </div>
        </section>
      </div>
    </div>
  );
};
