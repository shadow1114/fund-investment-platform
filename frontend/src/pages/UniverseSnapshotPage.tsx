import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { getUniverse, listUniverses } from "../api/generated/m17";
import type {
  ListUniversesParams,
  ResponseMeta,
  UniverseMeta,
} from "../api/generated/m17.schemas";
import { unwrapResponse } from "../api/http";
import { ErrorState } from "../components/ErrorState";
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
  });

  const applyFilters = (values: UniverseFilterValues) => {
    const next = new URLSearchParams();
    Object.entries(values).forEach(([key, value]) => {
      if (value) next.set(key, value);
    });
    setSearch(next);
  };

  return (
    <section>
      <h1>候选池快照</h1>
      <UniverseFilters
        key={serializedSearch}
        initialValues={filters}
        onSubmit={applyFilters}
      />
      {query.isPending && <p role="status">正在加载候选池快照…</p>}
      {query.isError && <ErrorState error={query.error} />}
      {query.data && (
        <>
          <ProvenanceBar meta={provenanceMeta(query.data.meta)} />
          {query.data.data.length === 0 ? (
            <p>没有符合条件的候选池快照</p>
          ) : (
            <ul aria-label="候选池快照列表">
              {query.data.data.map((universe) => (
                <li key={universe.universe_id}>
                  <Link to={`/universes/${universe.universe_id}`}>
                    查看快照 {universe.universe_id}
                  </Link>
                  <span>策略：{universe.strategy_id}</span>
                  <span>决策时间：{universe.decision_at}</span>
                  <span>成员数：{universe.member_count}</span>
                  <span>
                    资格规则版本：{universe.eligibility_rules_version}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
};

const UniverseDetail = ({ universeId }: { universeId: string }) => {
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

  if (query.isPending) return <p role="status">正在加载候选池快照…</p>;
  if (query.isError) return <ErrorState error={query.error} />;

  const { data, meta } = query.data;
  return (
    <section>
      <Link to="/universes">返回候选池快照列表</Link>
      <h1>候选池快照</h1>
      <dl>
        <dt>快照 ID</dt>
        <dd>{data.universe_id}</dd>
        <dt>决策时间</dt>
        <dd>{data.decision_at}</dd>
        <dt>候选池策略</dt>
        <dd>{data.universe_strategy}</dd>
      </dl>
      <p>资格规则版本：{meta.eligibility_rules_version}</p>
      <p>
        评分策略版本：
        {meta.scoring_policy_version ?? "未使用（仅资格筛选）"}
      </p>
      <ProvenanceBar meta={provenanceMeta(meta)} />
      <section aria-labelledby="selected-members-heading">
        <h2 id="selected-members-heading">已入选（{data.members.length}）</h2>
        <UniverseTable members={data.members} label="已入选成员" />
      </section>
      <section aria-labelledby="rejected-members-heading">
        <h2 id="rejected-members-heading">已排除（{data.excluded.length}）</h2>
        <UniverseTable members={data.excluded} label="已排除成员" />
      </section>
    </section>
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
