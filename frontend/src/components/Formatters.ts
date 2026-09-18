export const formatPercent = (value: number | null | undefined) =>
  value == null ? "" : `${(value * 100).toFixed(2)}%`;
export const formatMoney = (
  amount: number | string | null | undefined,
  currency = "CNY",
) => {
  if (amount == null) return "";
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(Number(amount));
};
export const formatDate = (date: string | Date | null | undefined) => {
  if (!date) return "";
  const d =
    typeof date === "string"
      ? date.slice(0, 10).split("-")
      : [
          String(date.getFullYear()),
          String(date.getMonth() + 1).padStart(2, "0"),
          String(date.getDate()).padStart(2, "0"),
        ];
  return `${d[0]}/${d[1]}/${d[2]}`;
};
