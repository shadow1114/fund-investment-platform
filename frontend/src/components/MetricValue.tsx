import { formatPercent } from "./Formatters";
type Props = {
  value: number | string | null;
  status?: string;
  reason?: string | null;
  format?: "percent" | "number" | ((v: number | string) => string);
};
export const MetricValue = ({
  value,
  status,
  reason,
  format = "number",
}: Props) => {
  if (value == null || status === "UNAVAILABLE" || status === "EXCLUDED")
    return <span>不可用（{reason ?? status ?? "UNKNOWN"}）</span>;
  const output =
    typeof format === "function"
      ? format(value)
      : format === "percent"
        ? typeof value === "number"
          ? formatPercent(value)
          : `不可用（INVALID_NUMERIC_VALUE）`
        : String(value);
  return <span>{output}</span>;
};
