import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  getFundBasicInfoHistoryQueryOptions,
  getFundIngestionsQueryOptions,
} from "../../api/queries";
import { ErrorState } from "../../components/ErrorState";

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
  const basicInfo = useQuery(
    getFundBasicInfoHistoryQueryOptions(fundId, asOfDate),
  );
  const tasks = useQuery(getFundIngestionsQueryOptions(fundId));
  return (
    <section aria-labelledby="fund-ingestion-heading">
      <h2 id="fund-ingestion-heading">数据抓取</h2>
      <p>
        在基金数据中心预览范围、提交抓取并查看项级结果。NAV
        按已登记份额类别补齐可用历史。
      </p>
      {canManage === true && (
        <p>
          <Link
            to={`/data-ingestion?fund_id=${encodeURIComponent(fundId)}&dataset=BASIC_INFO`}
          >
            在数据中心抓取基本信息
          </Link>
          {" · "}
          <Link
            to={`/data-ingestion?fund_id=${encodeURIComponent(fundId)}&dataset=NAV`}
          >
            在数据中心抓取 NAV 与分红/拆分
          </Link>
        </p>
      )}
      {canManage === false && <p>当前身份没有触发数据抓取的权限。</p>}
      {canManage === undefined && (
        <p role={permissionUnavailable ? "alert" : "status"}>
          {permissionUnavailable
            ? "无法读取当前身份权限，暂不显示抓取操作。"
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

      {tasks.isPending && <p role="status">正在读取抓取任务…</p>}
      {tasks.isError && <ErrorState error={tasks.error} />}
      {tasks.data?.length === 0 && <p>暂无抓取任务。</p>}
      {tasks.data && tasks.data.length > 0 && (
        <ul>
          {tasks.data.map((task) => (
            <li key={task.operation_id}>
              {canManage ? (
                <Link
                  to={`/data-ingestion?operation_id=${encodeURIComponent(task.operation_id)}`}
                >
                  {task.operation_id}
                </Link>
              ) : (
                task.operation_id
              )}
              {" · "}
              {task.dataset}
              {" · "}
              {task.task_status ?? task.status}
              {" · "}
              {task.source}
              {" · "}
              {new Date(task.created_at).toLocaleString("zh-CN")}
            </li>
          ))}
        </ul>
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
}) =>
  canManage ? (
    <Link
      to={`/data-ingestion?fund_id=${encodeURIComponent(fundId)}&dataset=BASIC_INFO`}
    >
      在数据中心抓取基本信息
    </Link>
  ) : null;

export const FundBatchIngestionAction = ({
  fundIds,
  canManage,
}: {
  fundIds: string[];
  canManage: boolean;
}) => {
  if (!canManage || fundIds.length === 0) return null;
  const unique = [...new Set(fundIds)];
  const params = new URLSearchParams(
    unique.length === 1
      ? { fund_id: unique[0], dataset: "BASIC_INFO" }
      : {
          scope_type: "SELECTED",
          fund_ids: unique.join(","),
          dataset: "BASIC_INFO",
        },
  );
  return (
    <div aria-label="批量抓取">
      <span>已选 {unique.length} 只基金（单次最多 100 只）</span>{" "}
      {unique.length <= 100 ? (
        <Link to={`/data-ingestion?${params.toString()}`}>
          将所选基金加入数据抓取
        </Link>
      ) : (
        <p role="alert">每次最多选择 100 只基金。</p>
      )}
    </div>
  );
};
