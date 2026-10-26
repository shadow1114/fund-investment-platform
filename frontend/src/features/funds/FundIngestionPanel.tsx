import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useState } from "react";
import { Button, Group, Modal, Stack, Text } from "@mantine/core";

import {
  getFundBasicInfoHistoryQueryOptions,
  getFundIngestionsQueryOptions,
  queryKeys,
} from "../../api/queries";
import {
  useSubmitFundIngestion,
  useSubmitFundIngestionBatch,
} from "../../api/mutations";
import { ErrorState } from "../../components/ErrorState";

const taskStatusLabel = (status: string, taskStatus?: string | null) => {
  if (status === "RUNNING") return "排队中或抓取中";
  if (status === "FAILED" || taskStatus === "FAILED") return "失败";
  if (taskStatus === "PARTIAL_SUCCESS") return "部分成功";
  if (status === "COMPLETED") return "完成";
  if (status === "BLOCKED") return "被数据质量阻断";
  if (status === "CANCELLED") return "已取消";
  return status;
};

export const FundIngestionPanel = ({
  fundId,
  canManage,
  permissionUnavailable,
  asOfDate,
}: {
  fundId: string;
  canManage?: boolean;
  permissionUnavailable?: boolean;
  asOfDate?: string;
}) => {
  const [confirmNav, setConfirmNav] = useState(false);
  const queryClient = useQueryClient();
  const tasks = useQuery({
    ...getFundIngestionsQueryOptions(fundId),
    refetchInterval: (query) =>
      query.state.data?.some((task) => task.status === "RUNNING")
        ? 2500
        : false,
  });
  const submit = useSubmitFundIngestion();
  const retryBatch = useSubmitFundIngestionBatch();
  const basicInfo = useQuery(
    getFundBasicInfoHistoryQueryOptions(fundId, asOfDate),
  );
  useEffect(() => {
    if (tasks.data?.some((task) => task.status === "COMPLETED")) {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.fundBasicInfoHistory(fundId, asOfDate),
      });
    }
    if (
      tasks.data?.some(
        (task) => task.status === "COMPLETED" && task.dataset === "NAV",
      )
    ) {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.fundNavSeries(fundId),
      });
    }
  }, [asOfDate, fundId, queryClient, tasks.data]);

  const start = (dataset: "BASIC_INFO" | "NAV") => {
    submit.mutate({ fundId, request: { dataset } });
  };

  return (
    <section aria-labelledby="fund-ingestion-heading">
      <h2 id="fund-ingestion-heading">数据抓取</h2>
      <p>
        任务由后台采集器执行；NAV
        按该基金已登记的份额类别补齐可用历史。重跑会重试整个范围，未变化的数据不增加修订版本。
      </p>
      {canManage === true && (
        <div>
          <button
            type="button"
            disabled={submit.isPending}
            onClick={() => start("BASIC_INFO")}
          >
            抓取基金基本信息
          </button>{" "}
          <Button
            variant="default"
            disabled={submit.isPending}
            onClick={() => setConfirmNav(true)}
          >
            抓取 NAV 与分红拆分
          </Button>
        </div>
      )}
      <Modal
        opened={confirmNav}
        onClose={() => setConfirmNav(false)}
        title="确认抓取 NAV 与分红拆分"
        centered
      >
        <Stack>
          <Text>
            将按已登记的份额类别补齐数据源可提供的历史，并为有变化的数据写入新修订。是否提交？
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setConfirmNav(false)}>
              取消
            </Button>
            <Button
              loading={submit.isPending}
              onClick={() => {
                setConfirmNav(false);
                start("NAV");
              }}
            >
              提交抓取
            </Button>
          </Group>
        </Stack>
      </Modal>
      {canManage === false && <p>当前身份没有触发数据抓取的权限。</p>}
      {canManage === undefined && (
        <p role={permissionUnavailable ? "alert" : "status"}>
          {permissionUnavailable
            ? "无法读取当前身份权限；为保护数据源，暂不显示抓取操作。"
            : "正在读取抓取权限…"}
        </p>
      )}
      <h3>已抓取的基金基本信息</h3>
      {basicInfo.isPending && <p role="status">正在读取基本信息历史…</p>}
      {basicInfo.isError && <ErrorState error={basicInfo.error} />}
      {basicInfo.data && basicInfo.data.length === 0 && (
        <p>暂无基本信息快照。</p>
      )}
      {basicInfo.data && basicInfo.data[0] && (
        <>
          <p>
            来源：{basicInfo.data[0].source} · 版本：v
            {basicInfo.data[0].version} · 可用时间：
            {new Date(basicInfo.data[0].available_at).toLocaleString("zh-CN")} ·
            时间质量：{basicInfo.data[0].availability_quality} · 适配器：
            {basicInfo.data[0].adapter_version} · 数据源库：
            {basicInfo.data[0].library_version}
          </p>
          <dl>
            {Object.entries(basicInfo.data[0].normalized_fields).map(
              ([key, value]) => (
                <div key={key}>
                  <dt>{key}</dt>
                  <dd>{value == null ? "—" : String(value)}</dd>
                </div>
              ),
            )}
          </dl>
          <details>
            <summary>查看上游原始字段</summary>
            <dl>
              {Object.entries(basicInfo.data[0].raw_fields).map(
                ([key, value]) => (
                  <div key={key}>
                    <dt>{key}</dt>
                    <dd>{value == null ? "—" : String(value)}</dd>
                  </div>
                ),
              )}
            </dl>
          </details>
          {basicInfo.data.length > 1 && (
            <details>
              <summary>查看更早的基本信息版本</summary>
              <ul>
                {basicInfo.data.slice(1).map((snapshot) => (
                  <li key={`${snapshot.version}-${snapshot.available_at}`}>
                    v{snapshot.version} · {snapshot.source} · 可用时间{" "}
                    {new Date(snapshot.available_at).toLocaleString("zh-CN")} ·{" "}
                    {snapshot.availability_quality}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
      {submit.isPending && <p role="status">抓取任务正在提交…</p>}
      {submit.isError && <ErrorState error={submit.error} />}
      {submit.isSuccess && (
        <p role="status">已提交任务 {submit.data.operation_id}。</p>
      )}
      {tasks.isPending && <p role="status">正在读取抓取任务…</p>}
      {tasks.isError && <ErrorState error={tasks.error} />}
      {tasks.data && tasks.data.length === 0 && <p>暂无抓取记录。</p>}
      {tasks.data && tasks.data.length > 0 && (
        <table>
          <caption>最近基金数据抓取任务</caption>
          <thead>
            <tr>
              <th scope="col">提交 / 开始 / 结束时间</th>
              <th scope="col">数据集</th>
              <th scope="col">数据源 / 触发人</th>
              <th scope="col">范围</th>
              <th scope="col">状态</th>
              <th scope="col">成功/失败份额</th>
              <th scope="col">结果</th>
            </tr>
          </thead>
          <tbody>
            {tasks.data.map((task) => (
              <tr key={task.operation_id}>
                <td>
                  提交 {new Date(task.created_at).toLocaleString("zh-CN")}
                  <br />
                  开始{" "}
                  {task.started_at
                    ? new Date(task.started_at).toLocaleString("zh-CN")
                    : "—"}
                  <br />
                  结束{" "}
                  {task.finished_at
                    ? new Date(task.finished_at).toLocaleString("zh-CN")
                    : "—"}
                </td>
                <td>
                  {task.dataset === "BASIC_INFO"
                    ? "基金基本信息"
                    : "NAV/分红拆分"}
                </td>
                <td>
                  {task.source} / {task.actor}
                </td>
                <td>
                  {task.fund_id === "BATCH"
                    ? `批量 ${task.fund_ids.length} 只`
                    : "单只基金"}
                </td>
                <td>{taskStatusLabel(task.status, task.task_status)}</td>
                <td>
                  {task.success_count ?? "—"} / {task.failure_count ?? "—"}
                  {task.status === "RUNNING" && "（处理中，进度暂不可用）"}
                </td>
                <td>
                  {task.failure && <span>{task.failure}</span>}
                  <ul>
                    {task.items.map((item, index) => {
                      const status = String(item.status ?? "UNKNOWN");
                      const error = item.error ? String(item.error) : undefined;
                      const navRows = item.nav_versions_created;
                      const latestEffectiveAt = item.latest_effective_at;
                      const eventRows = item.corporate_action_versions_created;
                      const infoVersion = item.basic_info_version;
                      const fieldCount = item.field_count;
                      return (
                        <li key={`${task.operation_id}-${index}`}>
                          基金 {String(item.fund_id ?? "—")} · 份额{" "}
                          {String(item.share_class_id ?? "—")}：
                          {status === "SUCCESS"
                            ? "成功"
                            : status === "FAILED"
                              ? "失败"
                              : status}
                          {typeof navRows === "number" &&
                            `，新增 NAV 修订 ${navRows} 条`}
                          {typeof latestEffectiveAt === "string" &&
                            `，最新估值日 ${latestEffectiveAt.slice(0, 10)}`}
                          {typeof eventRows === "number" &&
                            `，新增分红/拆分修订 ${eventRows} 条`}
                          {typeof infoVersion === "number" &&
                            `，基本信息 v${infoVersion}（${typeof fieldCount === "number" ? fieldCount : 0} 个规范字段）`}
                          {error && `，${error}`}
                        </li>
                      );
                    })}
                  </ul>
                  {(task.status === "FAILED" ||
                    task.task_status === "PARTIAL_SUCCESS") &&
                    task.fund_ids.length > 0 && (
                      <button
                        type="button"
                        disabled={submit.isPending || retryBatch.isPending}
                        onClick={() => {
                          if (task.fund_ids.length === 1) {
                            submit.mutate({
                              fundId: task.fund_ids[0],
                              request: { dataset: task.dataset },
                            });
                          } else {
                            retryBatch.mutate({
                              dataset: task.dataset,
                              fund_ids: task.fund_ids,
                            });
                          }
                        }}
                      >
                        重新抓取同一范围
                      </button>
                    )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
};

export const FundBasicInfoRefreshButton = ({
  fundId,
  canManage,
}: {
  fundId: string;
  canManage: boolean;
}) => {
  const submit = useSubmitFundIngestion();
  if (!canManage) return null;
  return (
    <div>
      <button
        type="button"
        disabled={submit.isPending}
        onClick={() =>
          submit.mutate({ fundId, request: { dataset: "BASIC_INFO" } })
        }
      >
        {submit.isPending ? "提交中…" : "抓取基本信息"}
      </button>
      {submit.isError && (
        <p role="alert">抓取任务提交失败：{submit.error.message}</p>
      )}
      {submit.isSuccess && (
        <p role="status">任务已提交：{submit.data.operation_id}</p>
      )}
    </div>
  );
};

export const FundBatchIngestionAction = ({
  fundIds,
  canManage,
}: {
  fundIds: string[];
  canManage: boolean;
}) => {
  const submit = useSubmitFundIngestionBatch();
  if (!canManage || fundIds.length === 0) return null;
  const start = (dataset: "BASIC_INFO" | "NAV") => {
    submit.mutate({ dataset, fund_ids: fundIds });
  };
  return (
    <div aria-label="批量抓取">
      <span>已选 {fundIds.length} 只基金（单次最多 100 只）</span>{" "}
      <button
        type="button"
        disabled={submit.isPending || fundIds.length > 100}
        onClick={() => start("BASIC_INFO")}
      >
        批量抓取基本信息
      </button>{" "}
      <button
        type="button"
        disabled={submit.isPending || fundIds.length > 100}
        onClick={() => start("NAV")}
      >
        批量抓取 NAV
      </button>
      {fundIds.length > 100 && <p role="alert">每次最多选择 100 只基金。</p>}
      {submit.isPending && <p role="status">批量任务正在提交…</p>}
      {submit.isError && (
        <p role="alert">批量任务提交失败：{submit.error.message}</p>
      )}
      {submit.isSuccess && (
        <p role="status">批量任务已提交：{submit.data.operation_id}</p>
      )}
    </div>
  );
};
