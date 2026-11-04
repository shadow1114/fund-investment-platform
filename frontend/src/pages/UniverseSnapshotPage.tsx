import { Button, Group, Stack, Tabs, Text } from "@mantine/core";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { ColDef, ICellRendererParams } from "ag-grid-community";
import { useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { getUniverse, listUniverses } from "../api/generated/m17";
import type {
  ListUniversesParams,
  ResponseMeta,
  UniverseMeta,
  UniverseSummary,
} from "../api/generated/m17.schemas";
import { unwrapResponse } from "../api/http";
import { ResearchDataTable } from "../components/ResearchDataTable";
import { ErrorState } from "../components/ErrorState";
import { PageHeader } from "../components/PageHeader";
import { ProvenanceBar } from "../components/ProvenanceBar";
import {
  UniverseFilters,
  type UniverseFilterValues,
} from "../features/universe/UniverseFilters";
import { UniverseTable } from "../features/universe/UniverseTable";

const filtersFromSearch = (search: URLSearchParams): UniverseFilterValues => ({
  strategy_id: search.get("strategy_id") ?? "",
  decision_at: search.get("decision_at") ?? "",
  eligibility_rules_version: search.get("eligibility_rules_version") ?? "",
});

const paramsFromFilters = (
  filters: UniverseFilterValues,
): ListUniversesParams => ({
  strategy_id: filters.strategy_id || undefined,
  decision_at: filters.decision_at || undefined,
  eligibility_rules_version: filters.eligibility_rules_version || undefined,
});

const provenanceMeta = (meta: ResponseMeta) => ({
  versions: meta.versions,
  is_point_in_time: meta.is_point_in_time,
  availability_quality_distribution: meta.availability_quality_distribution,
});

const UniverseList = () => {
  const [search, setSearch] = useSearchParams();
  const serializedSearch = search.toString();
  const filters = useMemo(
    () => filtersFromSearch(new URLSearchParams(serializedSearch)),
    [serializedSearch],
  );
  const params = useMemo(() => paramsFromFilters(filters), [filters]);
  const query = useQuery({
    queryKey: ["universe-list", params],
    queryFn: async () => {
      const response = await listUniverses(params);
      return {
        data: unwrapResponse(response),
        meta: response.data.meta as ResponseMeta,
      };
    },
    placeholderData: keepPreviousData,
  });
  const columns: ColDef<UniverseSummary>[] = [
    {
      field: "universe_id",
      headerName: "快照 ID",
      cellRenderer: ({ value }: ICellRendererParams<UniverseSummary>) => (
        <Link
          to={`/universes/${encodeURIComponent(value)}?return_to=${encodeURIComponent(`/universes?${serializedSearch}`)}`}
        >
          {value}
        </Link>
      ),
      lockVisible: true,
    },
    {
      field: "universe_strategy",
      headerName: "策略",
      cellRenderer: ({ value }: ICellRendererParams<UniverseSummary>) =>
        value === "UNKNOWN" ? "未知策略" : `策略 ${value}`,
    },
    { field: "decision_at", headerName: "决策日期" },
    { field: "member_count", headerName: "成员数" },
    { field: "eligibility_rules_version", headerName: "资格规则版本" },
  ];

  const applyFilters = (values: UniverseFilterValues) => {
    const next = new URLSearchParams();
    Object.entries(values).forEach(([key, value]) => {
      if (value) next.set(key, value);
    });
    setSearch(next);
  };

  return (
    <Stack gap="lg">
      <PageHeader
        title="候选池快照"
        breadcrumbs={[{ label: "候选池" }]}
        context={
          <Text size="sm" c="dimmed">
            按真实快照筛选和查看纳入/排除依据。
          </Text>
        }
      />
      <UniverseFilters
        key={serializedSearch}
        initialValues={filters}
        onSubmit={applyFilters}
      />
      {query.isPending && <Text role="status">正在加载候选池快照…</Text>}
      {query.isFetching && query.data && (
        <Text role="status" size="sm" c="dimmed">
          正在更新；保留上一次已返回的快照列表。
        </Text>
      )}
      {query.isError && (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      )}
      {query.data && (
        <Stack gap="sm">
          <ProvenanceBar meta={provenanceMeta(query.data.meta)} />
          <Group justify="space-between">
            <Text size="sm" c="dimmed">
              当前接口返回 {query.data.data.length}{" "}
              条快照；列表为完整已返回集合。
            </Text>
          </Group>
          <ResearchDataTable
            columnDefs={columns}
            rowData={query.data.data}
            getRowId={({ data }) => data.universe_id}
            pagination
            paginationPageSize={20}
            paginationPageSizeSelector={[20, 50, 100]}
            caption="候选池快照列表"
            emptyMessage="没有符合条件的候选池快照。"
            layoutKey="universes"
            requiredColumnIds={["universe_id"]}
          />
        </Stack>
      )}
    </Stack>
  );
};

const validReturnTo = (candidate: string | null) =>
  candidate?.startsWith("/universes") &&
  !candidate.startsWith("//") &&
  !candidate.includes("://")
    ? candidate
    : "/universes";

const UniverseDetail = ({ universeId }: { universeId: string }) => {
  const [search, setSearch] = useSearchParams();
  const query = useQuery({
    queryKey: ["universe-detail", universeId],
    queryFn: async () => {
      const response = await getUniverse(universeId);
      return {
        data: unwrapResponse(response),
        meta: response.data.meta as UniverseMeta,
      };
    },
  });
  if (query.isPending) return <Text role="status">正在加载候选池快照…</Text>;
  if (query.isError)
    return (
      <ErrorState error={query.error} onRetry={() => void query.refetch()} />
    );

  const { data, meta } = query.data;
  const tabParam = search.get("tab");
  const activeTab = tabParam === "rejected" ? "rejected" : "selected";
  const returnTo = validReturnTo(search.get("return_to"));
  const setTab = (tab: string | null) => {
    const next = new URLSearchParams(search);
    if (tab && tab !== "selected") next.set("tab", tab);
    else next.delete("tab");
    setSearch(next);
  };

  return (
    <Stack gap="lg">
      <PageHeader
        title={`候选池快照 ${data.universe_id}`}
        breadcrumbs={[
          { label: "候选池", href: returnTo },
          { label: data.universe_id },
        ]}
        actions={
          <Button component={Link} to={returnTo} variant="default">
            返回候选池列表
          </Button>
        }
      />
      <Group align="flex-start" gap="xl" wrap="wrap">
        <Text>决策时间：{data.decision_at}</Text>
        <Text>
          策略：
          {data.universe_strategy === "UNKNOWN"
            ? "未知策略"
            : `策略 ${data.universe_strategy}`}
        </Text>
        <Text>资格规则版本：{meta.eligibility_rules_version}</Text>
        <Text>
          评分策略版本：{meta.scoring_policy_version ?? "未使用（仅资格筛选）"}
        </Text>
      </Group>
      <ProvenanceBar meta={provenanceMeta(meta)} />
      <Tabs value={activeTab} onChange={setTab} keepMounted={false}>
        <Tabs.List aria-label="候选池成员状态">
          <Tabs.Tab value="selected">已入选（{data.members.length}）</Tabs.Tab>
          <Tabs.Tab value="rejected">已排除（{data.excluded.length}）</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="selected" pt="md">
          <UniverseTable
            members={data.members}
            label="已入选成员"
            decisionAt={data.decision_at}
          />
        </Tabs.Panel>
        <Tabs.Panel value="rejected" pt="md">
          <UniverseTable
            members={data.excluded}
            label="已排除成员"
            decisionAt={data.decision_at}
          />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
};

export const UniverseSnapshotPage = () => {
  const { universeId } = useParams();
  return universeId ? (
    <UniverseDetail universeId={universeId} />
  ) : (
    <UniverseList />
  );
};
