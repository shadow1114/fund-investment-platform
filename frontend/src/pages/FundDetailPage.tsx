import {
  Accordion,
  Alert,
  Paper,
  Menu,
  Button,
  SimpleGrid,
  Stack,
  Tabs,
  Text,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
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
import { PageHeader } from "../components/PageHeader";
import { ProvenanceBar } from "../components/ProvenanceBar";
import { StatusBadge } from "../components/StatusBadge";
import { EvaluationMetrics, ScoreMetrics } from "../features/funds/FundMetrics";
import { ClassificationView } from "../features/classifications/ClassificationView";
import { ClassificationHistory } from "../features/classifications/ClassificationHistory";
import { getSessionQueryOptions } from "../api/queries";
import { FundIngestionPanel } from "../features/funds/FundIngestionPanel";

const FundNavChart = lazy(() =>
  import("../features/funds/FundNavChart").then((module) => ({
    default: module.FundNavChart,
  })),
);

type Tab = "nav" | "evaluation" | "score";
const validReturnTo = (candidate: string | null, asOfDate?: string) => {
  if (
    candidate === "/funds" ||
    (candidate?.startsWith("/funds?") &&
      !candidate.includes("://") &&
      !candidate.startsWith("//"))
  ) {
    return candidate;
  }
  return asOfDate
    ? `/funds?as_of_date=${encodeURIComponent(asOfDate)}`
    : "/funds";
};

const provenanceMeta = (meta: ResponseMeta) => ({
  as_of_date: meta.as_of_date,
  data_version: meta.data_version,
  versions: meta.versions,
  is_point_in_time: meta.is_point_in_time,
  availability_quality_distribution: meta.availability_quality_distribution,
});

export const FundDetailPage = () => {
  const { fundId = "" } = useParams();
  const [search, setSearch] = useSearchParams();
  const session = useQuery(getSessionQueryOptions());
  const asOfDate = search.get("as_of_date") || undefined;
  const returnTo = validReturnTo(search.get("return_to"), asOfDate);
  const rawTab = search.get("tab");
  const tab: Tab =
    rawTab === "evaluation" || rawTab === "score" ? rawTab : "nav";
  const changeTab = (value: string | null) => {
    const next = new URLSearchParams(search);
    if (value && value !== "nav") next.set("tab", value);
    else next.delete("tab");
    setSearch(next);
  };

  const fund = useQuery({
    queryKey: ["fund-detail", fundId, asOfDate],
    enabled: Boolean(fundId),
    queryFn: async () => {
      const response = await getFund(fundId, { as_of_date: asOfDate });
      return {
        data: unwrapResponse(response),
        meta: response.data.meta as ResponseMeta,
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
  if (fund.isPending) return <Text role="status">正在加载基金详情…</Text>;
  if (fund.isError)
    return (
      <ErrorState error={fund.error} onRetry={() => void fund.refetch()} />
    );

  const tabQuery =
    tab === "nav" ? nav : tab === "evaluation" ? evaluation : score;
  const fundData = fund.data.data;

  return (
    <Stack gap="lg">
      <PageHeader
        title={fundData.fund_name}
        breadcrumbs={[
          { label: "基金研究", href: returnTo },
          { label: fundData.fund_name },
        ]}
        actions={<Link to={returnTo}>返回基金研究</Link>}
        context={
          <Text size="sm" c="dimmed">
            基金代码 {fundData.fund_id}
            {asOfDate ? ` · 数据截止 ${asOfDate}` : " · 当前可见数据"}
          </Text>
        }
      />
      <ProvenanceBar meta={provenanceMeta(fund.data.meta)} />
      <Paper withBorder radius="sm" p="md">
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
          <div>
            <Text size="xs" c="dimmed">
              主要分类
            </Text>
            <Text>{fundData.fund_classification}</Text>
          </div>
          <div>
            <Text size="xs" c="dimmed">
              生命周期
            </Text>
            <StatusBadge domain="lifecycle" value={fundData.lifecycle_status} />
          </div>
          <div>
            <Text size="xs" c="dimmed">
              投资资格
            </Text>
            <StatusBadge
              domain="eligibility"
              value={fundData.investment_eligibility}
            />
          </div>
          <div>
            <Text size="xs" c="dimmed">
              基准
            </Text>
            <Text>{fundData.benchmark.benchmark_name}</Text>
          </div>
        </SimpleGrid>
      </Paper>

      <Accordion variant="separated">
        <Accordion.Item value="classification">
          <Accordion.Control>五维分类与证据</Accordion.Control>
          <Accordion.Panel>
            <ClassificationView
              classification={fundData.classification}
              evidence
            />
            <ClassificationHistory fundId={fundId} decisionAt={asOfDate} />
            {session.data?.capabilities?.can_review_classifications && (
              <Menu>
                <Menu.Target>
                  <Button variant="default">分类操作</Button>
                </Menu.Target>
                <Menu.Dropdown>
                  <Menu.Item component={Link} to="/classification-reviews">
                    打开分类复核工作区
                  </Menu.Item>
                </Menu.Dropdown>
              </Menu>
            )}
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>

      <FundIngestionPanel
        fundId={fundId}
        asOfDate={asOfDate}
        canManage={session.data?.capabilities?.can_manage_data_ingestion}
        permissionUnavailable={session.isError}
      />

      <Tabs value={tab} onChange={changeTab} keepMounted={false}>
        <Tabs.List aria-label="基金研究详情">
          <Tabs.Tab value="nav">净值</Tabs.Tab>
          <Tabs.Tab value="evaluation">业绩风险</Tabs.Tab>
          <Tabs.Tab value="score">评分归因</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="nav" pt="md">
          {nav.isPending && <Text role="status">正在加载复权净值…</Text>}
          {nav.isError && (
            <ErrorState error={nav.error} onRetry={() => void nav.refetch()} />
          )}
          {nav.data && (
            <Stack gap="md">
              <ProvenanceBar meta={provenanceMeta(nav.data.meta)} />
              <Text size="sm">
                净值口径：
                {nav.data.meta.nav_type === "ADJUSTED"
                  ? "后复权"
                  : nav.data.meta.nav_type}{" "}
                · 复权规则：{nav.data.meta.adjustment_rule_version}
              </Text>
              <Suspense fallback={<Text role="status">正在加载净值图表…</Text>}>
                <FundNavChart points={nav.data.data.points} />
              </Suspense>
            </Stack>
          )}
        </Tabs.Panel>
        <Tabs.Panel value="evaluation" pt="md">
          {evaluation.isPending && (
            <Text role="status">正在加载业绩风险指标…</Text>
          )}
          {evaluation.isError && (
            <ErrorState
              error={evaluation.error}
              onRetry={() => void evaluation.refetch()}
            />
          )}
          {evaluation.data && (
            <Stack gap="md">
              <ProvenanceBar meta={provenanceMeta(evaluation.data.meta)} />
              <EvaluationMetrics
                evaluation={evaluation.data.data}
                meta={evaluation.data.meta}
              />
            </Stack>
          )}
        </Tabs.Panel>
        <Tabs.Panel value="score" pt="md">
          {score.isPending && <Text role="status">正在加载评分归因…</Text>}
          {score.isError && (
            <ErrorState
              error={score.error}
              onRetry={() => void score.refetch()}
            />
          )}
          {score.data && (
            <Stack gap="md">
              <ProvenanceBar meta={provenanceMeta(score.data.meta)} />
              <ScoreMetrics score={score.data.data} meta={score.data.meta} />
            </Stack>
          )}
        </Tabs.Panel>
      </Tabs>
      {tabQuery.isFetching && tabQuery.data && (
        <Alert color="blue" variant="light">
          正在更新当前详情数据。
        </Alert>
      )}
    </Stack>
  );
};
