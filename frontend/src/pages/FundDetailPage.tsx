import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import {
  getFund,
  getFundEvaluations,
  getFundNavSeries,
  getFundScores,
} from "../api/generated/m17";
import type {
  FundEvaluationMeta,
  FundScoreMeta,
  NavSeriesMeta,
  ResponseMeta,
} from "../api/generated/m17.schemas";
import { unwrapResponse } from "../api/http";
import { ErrorState } from "../components/ErrorState";
import { ProvenanceBar } from "../components/ProvenanceBar";
import { FundNavChart } from "../features/funds/FundNavChart";
import { EvaluationMetrics, ScoreMetrics } from "../features/funds/FundMetrics";

type Tab = "nav" | "evaluation" | "score";

const provenanceMeta = (meta: ResponseMeta) => ({
  versions: meta.versions,
  is_point_in_time: meta.is_point_in_time,
  availability_quality_distribution: meta.availability_quality_distribution,
});

export const FundDetailPage = () => {
  const { fundId = "" } = useParams();
  const [search] = useSearchParams();
  const asOfDate = search.get("as_of_date") || undefined;
  const [tab, setTab] = useState<Tab>("nav");
  const tabRefs = useRef<Record<Tab, HTMLButtonElement | null>>({
    nav: null,
    evaluation: null,
    score: null,
  });
  const selectTab = (nextTab: Tab, focus = false) => {
    setTab(nextTab);
    if (focus) tabRefs.current[nextTab]?.focus();
  };
  const fund = useQuery({
    queryKey: ["fund-detail", fundId, asOfDate],
    enabled: Boolean(fundId),
    queryFn: async () => {
      const response = await getFund(fundId, { as_of_date: asOfDate });
      return {
        data: unwrapResponse(response),
        meta: response.data.meta,
      };
    },
  });
  const nav = useQuery({
    queryKey: ["fund-nav", fundId, asOfDate],
    enabled: Boolean(fundId),
    queryFn: async () => {
      const response = await getFundNavSeries(fundId, {
        as_of_date: asOfDate,
        nav_type: "ADJUSTED",
      });
      return {
        data: unwrapResponse(response),
        meta: response.data.meta as NavSeriesMeta,
      };
    },
  });
  const evaluation = useQuery({
    queryKey: ["fund-evaluation", fundId, asOfDate],
    enabled: Boolean(fundId),
    queryFn: async () => {
      const response = await getFundEvaluations(fundId, {
        as_of_date: asOfDate,
        evaluation_period: "1Y",
      });
      return {
        data: unwrapResponse(response),
        meta: response.data.meta as FundEvaluationMeta,
      };
    },
  });
  const score = useQuery({
    queryKey: ["fund-score", fundId, asOfDate],
    enabled: Boolean(fundId),
    queryFn: async () => {
      const response = await getFundScores(fundId, {
        as_of_date: asOfDate,
        evaluation_period: "1Y",
      });
      return {
        data: unwrapResponse(response),
        meta: response.data.meta as FundScoreMeta,
      };
    },
  });

  if (!fundId) return <ErrorState error={new Error("缺少基金 ID")} />;
  if (fund.isPending) return <p role="status">正在加载基金详情…</p>;
  if (fund.isError) return <ErrorState error={fund.error} />;

  const tabQuery =
    tab === "nav" ? nav : tab === "evaluation" ? evaluation : score;

  return (
    <section>
      <Link to={`/funds${asOfDate ? `?as_of_date=${asOfDate}` : ""}`}>
        返回基金列表
      </Link>
      <h1>{fund.data.data.fund_name}</h1>
      <dl>
        <dt>基金代码</dt>
        <dd>{fund.data.data.fund_id}</dd>
        <dt>分类</dt>
        <dd>{fund.data.data.fund_classification}</dd>
        <dt>生命周期</dt>
        <dd>{fund.data.data.lifecycle_status}</dd>
        <dt>投资资格</dt>
        <dd>{fund.data.data.investment_eligibility}</dd>
        <dt>基准</dt>
        <dd>{fund.data.data.benchmark.benchmark_name}</dd>
      </dl>
      <div role="tablist" aria-label="基金详情">
        {(
          [
            ["nav", "净值"],
            ["evaluation", "评估"],
            ["score", "评分"],
          ] as const
        ).map(([id, label], index, allTabs) => (
          <button
            key={id}
            id={`${id}-tab`}
            ref={(element) => {
              tabRefs.current[id] = element;
            }}
            role="tab"
            type="button"
            aria-selected={tab === id}
            aria-controls={`${id}-panel`}
            tabIndex={tab === id ? 0 : -1}
            onClick={() => selectTab(id)}
            onKeyDown={(event) => {
              let nextIndex: number | undefined;
              if (event.key === "ArrowRight")
                nextIndex = (index + 1) % allTabs.length;
              if (event.key === "ArrowLeft")
                nextIndex = (index - 1 + allTabs.length) % allTabs.length;
              if (event.key === "Home") nextIndex = 0;
              if (event.key === "End") nextIndex = allTabs.length - 1;
              if (nextIndex !== undefined) {
                event.preventDefault();
                selectTab(allTabs[nextIndex][0], true);
              }
            }}
          >
            {label}
          </button>
        ))}
      </div>
      <section
        id={`${tab}-panel`}
        role="tabpanel"
        tabIndex={0}
        aria-labelledby={`${tab}-tab`}
        aria-label={
          tab === "nav" ? "净值" : tab === "evaluation" ? "评估" : "评分"
        }
      >
        {tabQuery.isPending && <p role="status">正在加载数据…</p>}
        {tabQuery.isError && <ErrorState error={tabQuery.error} />}
        {tab === "nav" && nav.data && (
          <>
            <ProvenanceBar meta={provenanceMeta(nav.data.meta)} />
            <p>
              净值口径：{nav.data.meta.nav_type} · 调整规则：
              {nav.data.meta.adjustment_rule_version}
            </p>
            <FundNavChart points={nav.data.data.points} />
          </>
        )}
        {tab === "evaluation" && evaluation.data && (
          <>
            <ProvenanceBar meta={provenanceMeta(evaluation.data.meta)} />
            <EvaluationMetrics
              evaluation={evaluation.data.data}
              meta={evaluation.data.meta}
            />
          </>
        )}
        {tab === "score" && score.data && (
          <>
            <ProvenanceBar meta={provenanceMeta(score.data.meta)} />
            <ScoreMetrics score={score.data.data} meta={score.data.meta} />
          </>
        )}
      </section>
    </section>
  );
};
