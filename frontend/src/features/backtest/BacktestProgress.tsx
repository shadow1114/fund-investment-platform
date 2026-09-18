import type { BacktestStatus } from "../../api/generated/m17.schemas";

const statusNames: Record<string, string> = {
  CREATED: "已创建",
  VALIDATING_CONFIGURATION: "校验配置中",
  RUNNING: "执行中",
  VALIDATING_RESULTS: "校验结果中",
  COMPLETED: "执行已完成",
  FAILED: "执行失败",
  INVALID: "结果无效",
  CANCELLED: "已取消",
  ABORTED: "已中止",
};

export const BacktestProgress = ({ status }: { status: BacktestStatus }) => {
  const total = status.progress.total_periods;
  return (
    <section aria-label="回测进度">
      <h2>回测进度</h2>
      <strong>{statusNames[status.status] ?? status.status}</strong>
      <p>验证状态：{status.validation_status ?? "尚未产生"}</p>
      <p>
        期次：{status.progress.completed_periods}/{total ?? "未知"}
        {status.progress.total_periods_is_estimate ? "（估算）" : ""}
      </p>
      {status.progress.current_decision_date && (
        <p>当前决策日：{status.progress.current_decision_date}</p>
      )}
    </section>
  );
};
