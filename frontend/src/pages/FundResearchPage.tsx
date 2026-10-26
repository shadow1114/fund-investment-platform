import { Button, Group, Pill, Stack, Text } from "@mantine/core";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
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
import { PageHeader } from "../components/PageHeader";
import { ProvenanceBar } from "../components/ProvenanceBar";
import {
  FundFilters,
  emptyFundFilters,
  type FundFilterValues,
} from "../features/funds/FundFilters";
import { FundTable } from "../features/funds/FundTable";
import { getSessionQueryOptions } from "../api/queries";
import { dimensionLabels } from "../features/classifications/ClassificationView";

const split = (value: string | null) => value?.split(",").filter(Boolean) ?? [];
const asList = (value: string[]) => (value.length > 0 ? value : undefined);
const asCsv = (value: string[]) =>
  value.length > 0 ? value.join(",") : undefined;

const parseParams = (search: URLSearchParams): ListFundsParams => ({
  asset_class: asCsv(split(search.get("asset_class"))),
  strategy: asCsv(split(search.get("strategy"))),
  geography: asCsv(split(search.get("geography"))),
  product_structure: asCsv(split(search.get("product_structure"))),
  market_attributes: asCsv(split(search.get("market_attributes"))),
  classification_status: asCsv(split(search.get("classification_status"))),
  fund_name: search.get("fund_name") || undefined,
  fund_type: asList(split(search.get("fund_type"))),
  lifecycle_status: asList(split(search.get("lifecycle_status"))) as
    LifecycleStatus[] | undefined,
  investment_eligibility: asList(
    split(search.get("investment_eligibility")),
  ) as InvestmentEligibility[] | undefined,
  as_of_date: search.get("as_of_date") || undefined,
  page: Number(search.get("page") || "1"),
  page_size: Number(search.get("page_size") || "20"),
  sort: search.get("sort") || "fund_name",
  order: (search.get("order") || "asc") as OrderParameter,
});

const initialFilterValues = (search: URLSearchParams): FundFilterValues => ({
  ...emptyFundFilters(),
  asset_class: split(search.get("asset_class")),
  strategy: split(search.get("strategy")),
  geography: split(search.get("geography")),
  product_structure: split(search.get("product_structure")),
  market_attributes: split(search.get("market_attributes")),
  classification_status: split(search.get("classification_status")),
  fund_name: search.get("fund_name") || "",
  fund_type: split(search.get("fund_type")),
  lifecycle_status: split(search.get("lifecycle_status")),
  investment_eligibility: split(search.get("investment_eligibility")),
  as_of_date: search.get("as_of_date") || "",
  page_size: search.get("page_size") || "20",
  sort: search.get("sort") || "fund_name",
  order: search.get("order") || "asc",
});

const serializeFilters = (values: FundFilterValues) => {
  const next = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    const serialized = Array.isArray(value) ? value.join(",") : value;
    if (serialized) next.set(key, serialized);
  });
  next.set("page", "1");
  return next;
};

const labels: Record<string, string> = {
  ...dimensionLabels,
  fund_name: "基金名称",
  fund_type: "基金类型",
  lifecycle_status: "生命周期",
  investment_eligibility: "投资资格",
  as_of_date: "数据截止日",
};

export const FundResearchPage = () => {
  const [search, setSearch] = useSearchParams();
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
    placeholderData: keepPreviousData,
  });

  const applyFilters = (values: FundFilterValues) =>
    setSearch(serializeFilters(values));
  const resetFilters = () => setSearch(serializeFilters(emptyFundFilters()));
  const changePage = (page: number) => {
    const next = new URLSearchParams(search);
    next.set("page", String(page));
    setSearch(next);
  };
  const removeFilter = (key: string, value: string) => {
    const next = new URLSearchParams(search);
    const existing = split(next.get(key));
    if (existing.length > 1 && existing.includes(value)) {
      const remaining = existing.filter((entry) => entry !== value);
      next.set(key, remaining.join(","));
    } else {
      next.delete(key);
    }
    next.set("page", "1");
    setSearch(next);
  };
  const activeFilters = Object.entries(filters).flatMap(([key, value]) => {
    if (["page_size", "sort", "order"].includes(key)) return [];
    const entries = Array.isArray(value) ? value : value ? [value] : [];
    return entries.map((entry) => ({ key, value: entry }));
  });

  return (
    <Stack gap="lg">
      <PageHeader
        title="基金研究"
        breadcrumbs={[{ label: "基金研究" }]}
        context={
          <Text size="sm" c="dimmed">
            {params.as_of_date
              ? `数据截止 ${params.as_of_date}`
              : "使用当前可见数据"}{" "}
            · {query.data?.meta.pagination.total_items ?? "—"} 只符合条件
          </Text>
        }
      />
      <FundFilters
        key={serializedSearch}
        initialValues={filters}
        onSubmit={applyFilters}
        onReset={resetFilters}
      />
      {activeFilters.length > 0 && (
        <Group gap="xs" aria-label="已选筛选条件">
          <Text size="sm" c="dimmed">
            已选条件
          </Text>
          {activeFilters.map(({ key, value }) => (
            <Button
              key={`${key}-${value}`}
              type="button"
              size="compact-xs"
              variant="light"
              onClick={() => removeFilter(key, value)}
              aria-label={`移除${labels[key] ?? key} ${value}`}
            >
              {labels[key] ?? key}：{value} ×
            </Button>
          ))}
        </Group>
      )}
      {query.isPending && <Text role="status">正在加载基金…</Text>}
      {query.isFetching && query.data && (
        <Text role="status" size="sm" c="dimmed">
          正在更新筛选结果；下方暂时保留上一次查询。
        </Text>
      )}
      {query.isError && (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      )}
      {query.data && (
        <Stack gap="md">
          <ProvenanceBar meta={query.data.meta} />
          {query.data.funds.length === 0 ? (
            <Pill>没有符合条件的基金</Pill>
          ) : (
            <FundTable
              key={serializedSearch}
              funds={query.data.funds}
              asOfDate={query.data.meta.as_of_date}
              returnTo={`/funds?${search.toString()}`}
              canManageIngestion={
                session.data?.capabilities?.can_manage_data_ingestion ?? false
              }
              sort={params.sort ?? "fund_name"}
              order={params.order ?? "asc"}
              onSort={(sort, order) => {
                const next = new URLSearchParams(search);
                next.set("sort", sort);
                next.set("order", order);
                next.set("page", "1");
                setSearch(next);
              }}
            />
          )}
          {query.data.funds.length > 0 && (
            <Group justify="space-between" wrap="wrap">
              <Text size="sm" c="dimmed">
                第 {query.data.meta.pagination.page} /{" "}
                {query.data.meta.pagination.total_pages} 页 · 共{" "}
                {query.data.meta.pagination.total_items} 只基金
              </Text>
              <Group gap="xs">
                <Button
                  variant="default"
                  disabled={query.data.meta.pagination.page <= 1}
                  onClick={() =>
                    changePage(query.data!.meta.pagination.page - 1)
                  }
                >
                  上一页
                </Button>
                <Button
                  variant="default"
                  disabled={
                    query.data.meta.pagination.page >=
                    query.data.meta.pagination.total_pages
                  }
                  onClick={() =>
                    changePage(query.data!.meta.pagination.page + 1)
                  }
                >
                  下一页
                </Button>
              </Group>
            </Group>
          )}
        </Stack>
      )}
    </Stack>
  );
};
