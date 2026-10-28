import { Badge } from "@mantine/core";

type Domain =
  | "lifecycle"
  | "eligibility"
  | "operation"
  | "optimization"
  | "decision"
  | "backtest";

const labels: Record<string, string> = {
  NORMAL: "正常",
  SUSPENDED_SUBSCRIPTION: "暂停申购",
  LIQUIDATED: "已清算",
  MERGED: "已合并",
  TRANSFORMED: "已转型",
  FULLY_ELIGIBLE: "可新建仓",
  HOLD_ONLY: "仅可持有",
  LIMITED: "受限",
  EXIT_ONLY: "仅可退出",
  NOT_TRADABLE: "不可交易",
  RUNNING: "运行中",
  COMPLETED: "已完成",
  BLOCKED: "已阻断",
  FAILED: "失败",
  CANCELLED: "已取消",
  OPTIMAL: "最优解",
  INFEASIBLE: "无可行解",
  UNBOUNDED: "无界",
  NOT_CONVERGED: "未收敛",
  NUMERICAL_ERROR: "数值异常",
  PROPOSED: "待复核",
  APPROVED: "已批准",
  REJECTED: "已拒绝",
  OVERRIDDEN: "已覆盖",
  EXPIRED: "已过期",
  SUPERSEDED: "已被替代",
  CREATED: "已创建",
  VALIDATING_CONFIGURATION: "校验配置中",
  VALIDATING_RESULTS: "校验结果中",
  INVALID: "无效",
  ABORTED: "已中止",
  UNKNOWN: "未知",
};

const colors: Partial<Record<Domain, Record<string, string>>> = {
  lifecycle: {
    NORMAL: "green",
    SUSPENDED_SUBSCRIPTION: "yellow",
    LIQUIDATED: "gray",
    MERGED: "gray",
    TRANSFORMED: "blue",
  },
  eligibility: {
    FULLY_ELIGIBLE: "green",
    HOLD_ONLY: "yellow",
    LIMITED: "orange",
    EXIT_ONLY: "orange",
    NOT_TRADABLE: "red",
  },
  operation: {
    RUNNING: "blue",
    COMPLETED: "green",
    BLOCKED: "yellow",
    FAILED: "red",
    CANCELLED: "gray",
  },
  optimization: {
    OPTIMAL: "green",
    INFEASIBLE: "orange",
    UNBOUNDED: "red",
    NOT_CONVERGED: "yellow",
    NUMERICAL_ERROR: "red",
  },
  decision: {
    PROPOSED: "blue",
    APPROVED: "green",
    REJECTED: "red",
    OVERRIDDEN: "orange",
    EXPIRED: "gray",
    SUPERSEDED: "gray",
  },
  backtest: {
    RUNNING: "blue",
    COMPLETED: "green",
    FAILED: "red",
    INVALID: "orange",
    CANCELLED: "gray",
    ABORTED: "gray",
  },
};

export const statusTextColors: Record<string, string> = {
  green: "#14532d",
  yellow: "#713f12",
  orange: "#7c2d12",
  red: "#7f1d1d",
  blue: "#1e3a8a",
  gray: "#374151",
};

export const StatusBadge = ({
  domain,
  value,
}: {
  domain: Domain;
  value: string;
}) => (
  <Badge
    color={colors[domain]?.[value] ?? "gray"}
    style={{ color: statusTextColors[colors[domain]?.[value] ?? "gray"] }}
    variant={colors[domain]?.[value] ? "light" : "outline"}
    title={labels[value] ? undefined : `原始状态：${value}`}
  >
    {labels[value] ?? `未知（${value || "空"}）`}
  </Badge>
);
