import { Anchor, Stack, Text, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { listFunds, listPortfolios } from "../api/generated/m17";
import { unwrapResponse } from "../api/http";
import { ErrorState } from "../components/ErrorState";
import styles from "./WorkspaceHomePage.module.css";

const useWorkspaceCount = (kind: "funds" | "portfolios") =>
  useQuery({
    queryKey: ["api", "workspace-count", kind],
    queryFn: async () => {
      const response = await (kind === "funds"
        ? listFunds({ page_size: 1 })
        : listPortfolios({ page_size: 1 }));
      unwrapResponse(response, { requiredMeta: ["pagination"] });
      const total = response.data.meta.pagination?.total_items;
      if (typeof total !== "number" || !Number.isInteger(total) || total < 0)
        throw new Error("总数暂不可用，请重新读取。");
      return total;
    },
  });

const WorkspaceCount = ({
  kind,
  label,
  href,
}: {
  kind: "funds" | "portfolios";
  label: string;
  href: string;
}) => {
  const query = useWorkspaceCount(kind);
  return (
    <section className={styles.metric} aria-label={label}>
      <Anchor component={Link} to={href} fw={600}>
        {label}
      </Anchor>
      {query.isPending ? (
        <Text role="status" c="dimmed">
          正在读取…
        </Text>
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <>
          <Text className={styles.number}>
            {query.data.toLocaleString("zh-CN")}
          </Text>
          <Text size="xs" c="dimmed">
            {query.data === 0 ? "暂无数据" : "来自当前可访问的数据范围"}
          </Text>
        </>
      )}
    </section>
  );
};

export const WorkspaceHomePage = () => (
  <Stack gap="xl">
    <section className={styles.welcome}>
      <Text size="xs" className={styles.eyebrow}>
        客户投资工作区
      </Text>
      <Title order={1}>工作台</Title>
      <Text mt="sm">从基金研究到组合管理，连接每一步投资决策。</Text>
    </section>
    <div className={styles.metrics}>
      <WorkspaceCount kind="funds" label="基金总数" href="/funds" />
      <WorkspaceCount kind="portfolios" label="组合数" href="/portfolios" />
    </div>
    <section>
      <Title order={2} size="lg" mb="md">
        开始研究
      </Title>
      <div className={styles.entries}>
        {[
          ["基金研究", "/funds", "筛选基金，查看净值、风险与评分来源。"],
          ["候选池", "/universes", "查看候选基金与点时数据快照。"],
          ["组合管理", "/portfolios", "查看组合配置与投资决策。"],
          ["策略回测", "/backtests", "检验策略表现与回测偏差。"],
        ].map(([label, href, description]) => (
          <Link key={href} to={href} className={styles.entry}>
            <Text fw={600}>{label} →</Text>
            <Text size="sm" mt="sm" c="dimmed">
              {description}
            </Text>
          </Link>
        ))}
      </div>
    </section>
  </Stack>
);
