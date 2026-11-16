import { Button, Modal, Stack, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { CircleCheck } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import type { FundIngestionSubmission } from "../api/generated/m17.schemas";
import { getSessionQueryOptions } from "../api/queries";
import { ErrorState } from "../components/ErrorState";
import { PageHeader } from "../components/PageHeader";
import styles from "../features/ingestion/DataIngestion.module.css";
import { IngestionHistoryTable } from "../features/ingestion/IngestionHistoryTable";
import {
  datasetLabels,
  IngestionScopeForm,
} from "../features/ingestion/IngestionScopeForm";
import { IngestionTaskDetail } from "../features/ingestion/IngestionTaskDetail";

export const DataIngestionPage = () => {
  const session = useQuery(getSessionQueryOptions());
  const [search, setSearch] = useSearchParams();
  const [submitted, setSubmitted] = useState<FundIngestionSubmission>();
  const operationId = search.get("operation_id");
  // 打开或关闭日志时只改 operation_id，保留新建表单的预填参数。
  const setOperation = (id: string | null) =>
    setSearch((current) => {
      const next = new URLSearchParams(current);
      if (id) next.set("operation_id", id);
      else next.delete("operation_id");
      return next;
    });

  if (session.isPending)
    return <Text role="status">正在读取数据抓取权限…</Text>;
  if (session.isError)
    return (
      <ErrorState
        error={session.error}
        onRetry={() => void session.refetch()}
      />
    );
  if (session.data.capabilities.can_manage_data_ingestion !== true)
    return (
      <Stack>
        <PageHeader
          title="403 · 无数据抓取权限"
          breadcrumbs={[{ label: "数据抓取" }]}
        />
        <Text>当前身份没有管理数据抓取的权限，请联系工作区管理员。</Text>
        <Button component={Link} to="/home" w="fit-content">
          返回工作台
        </Button>
      </Stack>
    );
  const canManageAll =
    session.data.capabilities.can_manage_full_universe_ingestion === true;

  return (
    <div className={styles.page}>
      <h1 className={styles.visuallyHidden}>数据抓取</h1>
      <IngestionScopeForm
        initialSearch={search}
        canManageAll={canManageAll}
        actor={session.data.user_id}
        onSubmitted={setSubmitted}
      />
      {submitted && (
        <div className={styles.card}>
          <div
            className={styles.footer}
            style={{ border: 0, padding: "10px 16px" }}
          >
            <span className={styles.summary} role="status">
              <CircleCheck size={14} aria-hidden="true" />
              已提交
              {datasetLabels[submitted.dataset as keyof typeof datasetLabels] ??
                ""}
              任务 <strong>{submitted.operation_id}</strong>
              ，后台持续执行，离开页面不影响进度。
            </span>
            <Button
              size="compact-xs"
              variant="light"
              onClick={() => setOperation(submitted.operation_id)}
            >
              查看执行日志
            </Button>
          </div>
        </div>
      )}
      <IngestionHistoryTable
        canManageAll={canManageAll}
        onOpen={setOperation}
      />
      <Modal
        opened={Boolean(operationId)}
        onClose={() => setOperation(null)}
        title={`执行日志 · ${operationId ?? ""}`}
        size="xl"
        centered
      >
        {operationId && (
          <IngestionTaskDetail
            key={operationId}
            operationId={operationId}
            canManageAll={canManageAll}
            onOperation={setOperation}
          />
        )}
      </Modal>
    </div>
  );
};
