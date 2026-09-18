import type { ResponseMeta } from "../api/generated/m17.schemas";

type Props = {
  meta?: Pick<
    ResponseMeta,
    "versions" | "is_point_in_time" | "availability_quality_distribution"
  >;
};
const labels: Record<string, string> = {
  EXACT: "精确",
  DERIVED: "派生",
  INFERRED: "推断",
};
export const ProvenanceBar = ({ meta }: Props) => {
  const missing = [
    meta?.versions === undefined ? "versions" : null,
    meta?.is_point_in_time === undefined ? "is_point_in_time" : null,
    meta?.availability_quality_distribution === undefined
      ? "availability_quality_distribution"
      : null,
  ].filter((field): field is string => field !== null);

  return (
    <aside aria-label="数据溯源">
      {missing.length > 0 && (
        <div role="alert">数据溯源契约错误：缺少 {missing.join(", ")}</div>
      )}
      <span>
        点时数据：
        {meta?.is_point_in_time === undefined
          ? "未知"
          : meta.is_point_in_time
            ? "是"
            : "否"}
      </span>
      {Object.entries(meta?.versions ?? {}).map(([k, v]) => (
        <span key={k}>
          {k}: {v}
        </span>
      ))}
      {Object.entries(meta?.availability_quality_distribution ?? {}).map(
        ([k, v]) => (
          <span key={k}>
            {labels[k] ?? k} {v}
          </span>
        ),
      )}
    </aside>
  );
};
