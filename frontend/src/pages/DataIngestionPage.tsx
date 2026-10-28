import { Button, Stack, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type {
  FundIngestionTask,
  FundIngestionPreview,
} from "../api/generated/m17.schemas";
import { getSessionQueryOptions } from "../api/queries";
import { ErrorState } from "../components/ErrorState";
import { PageHeader } from "../components/PageHeader";
import { IngestionHistoryTable } from "../features/ingestion/IngestionHistoryTable";
import { IngestionScopeForm } from "../features/ingestion/IngestionScopeForm";
import { IngestionTaskDetail } from "../features/ingestion/IngestionTaskDetail";
import styles from "./DataIngestionPage.module.css";

export const DataIngestionPage = () => {
  const session = useQuery(getSessionQueryOptions());
  const [search, setSearch] = useSearchParams();
  const [latest, setLatest] = useState<FundIngestionTask>();
  const [preview, setPreview] = useState<FundIngestionPreview>();
  const operationId = search.get("operation_id");
  if (session.isPending)
    return <Text role="status">正在读取数据抓取权限…</Text>;
  if (session.isError)
    return (
      <ErrorState
        error={session.error}
        onRetry={() => void session.refetch()}
      />
    );
  if (
    !session.isSuccess ||
    session.data.capabilities.can_manage_data_ingestion !== true
  )
    return (
      <Stack>
        <PageHeader
          title="403 · 无数据抓取权限"
          breadcrumbs={[{ label: "基金数据中心" }]}
        />
        <Text>当前身份没有管理基金数据抓取的权限，请联系工作区管理员。</Text>
        <Button component={Link} to="/home" w="fit-content">
          返回工作台
        </Button>
      </Stack>
    );
  const canManageAll =
    session.data.capabilities.can_manage_full_universe_ingestion === true;
  return (
    <Stack className={styles.page} gap="lg">
      <PageHeader
        title="基金数据中心"
        breadcrumbs={[{ label: "基金数据中心" }]}
        context={
          <Text size="sm" c="dimmed">
            数据源：
            {(!operationId && preview?.source) ||
              latest?.source ||
              "暂不可用"}{" "}
            · 最近更新时间：
            {latest?.finished_at
              ? new Date(latest.finished_at).toLocaleString("zh-CN")
              : latest
                ? "最近任务尚未完成"
                : "暂无任务记录"}
          </Text>
        }
      />
      <Text>
        单只、多只和平台基金库快照统一在此提交；任务由后台持续执行，离开页面后可通过任务链接恢复。
      </Text>
      {operationId ? (
        <IngestionTaskDetail
          key={operationId}
          operationId={operationId}
          canManageAll={canManageAll}
          onOperation={(id) => setSearch({ operation_id: id })}
        />
      ) : (
        <IngestionScopeForm
          key={search.toString()}
          initialSearch={search}
          canManageAll={canManageAll}
          actor={session.data.user_id}
          onPreview={setPreview}
          onSubmitted={(submission) =>
            setSearch({ operation_id: submission.operation_id })
          }
        />
      )}
      <IngestionHistoryTable onLatest={setLatest} />
    </Stack>
  );
};
