import { useQuery } from "@tanstack/react-query";
import { getOperationQueryOptions } from "../api/queries";
import { ErrorState } from "./ErrorState";
type Props = {
  operationId: string;
  resultRef?: string | null;
  pollIntervalMs?: number;
};
const names: Record<string, string> = {
  RUNNING: "运行中",
  COMPLETED: "已完成",
  BLOCKED: "已阻塞",
  FAILED: "失败",
  CANCELLED: "已取消",
};
export const OperationProgress = ({
  operationId,
  resultRef,
  pollIntervalMs = 1000,
}: Props) => {
  const q = useQuery({
    ...getOperationQueryOptions(operationId),
    refetchInterval: (query) =>
      query.state.data?.status === "RUNNING" ? pollIntervalMs : false,
  });
  const op = q.data;
  if (q.isLoading) return <div>加载中</div>;
  if (q.error) return <ErrorState error={q.error} />;
  if (!op) return null;
  return (
    <section aria-label="操作进度">
      <strong>{names[op.status] ?? op.status}</strong>
      {op.progress && (
        <span>
          ：{op.progress.completed}/{op.progress.total ?? "?"}{" "}
          {op.progress.unit}
        </span>
      )}
      {(op.result_ref ?? resultRef) && <div>{op.result_ref ?? resultRef}</div>}
      {op.failure && (
        <div>
          {op.failure.code}：{op.failure.message}
        </div>
      )}
    </section>
  );
};
