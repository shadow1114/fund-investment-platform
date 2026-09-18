type Props = {
  meta?: {
    versions?: Record<string, string>;
    is_point_in_time?: boolean;
    availability_quality_distribution?: Record<string, number>;
  };
};
const labels: Record<string, string> = {
  EXACT: "精确",
  DERIVED: "派生",
  INFERRED: "推断",
};
export const ProvenanceBar = ({ meta = {} }: Props) => (
  <aside aria-label="数据溯源">
    <span>点时数据：{meta.is_point_in_time ? "是" : "否"}</span>
    {Object.entries(meta.versions ?? {}).map(([k, v]) => (
      <span key={k}>
        {k}: {v}
      </span>
    ))}
    {Object.entries(meta.availability_quality_distribution ?? {}).map(
      ([k, v]) => (
        <span key={k}>
          {labels[k] ?? k} {v}
        </span>
      ),
    )}
  </aside>
);
