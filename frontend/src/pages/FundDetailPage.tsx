import { useParams, useSearchParams } from "react-router-dom";
import type { FundAnalyticsPeriod } from "../features/funds/FactorAnalysisPanel";
import {
  FundDetailContent,
  factorPeriods,
  type FundDetailTab,
} from "../features/funds/FundDetailContent";

const validReturnTo = (candidate: string | null, asOfDate?: string) => {
  if (
    candidate === "/funds" ||
    (candidate?.startsWith("/funds?") &&
      !candidate.includes("://") &&
      !candidate.startsWith("//"))
  ) {
    return candidate;
  }
  return asOfDate
    ? `/funds?as_of_date=${encodeURIComponent(asOfDate)}`
    : "/funds";
};

export const FundDetailPage = () => {
  const { fundId = "" } = useParams();
  const [search, setSearch] = useSearchParams();
  const asOfDate = search.get("as_of_date") || undefined;
  const returnTo = validReturnTo(search.get("return_to"), asOfDate);
  const rawTab = search.get("tab");
  const tab: FundDetailTab =
    rawTab === "drawdown" || rawTab === "rolling" ? rawTab : "nav";
  const rawPeriod = search.get("factor_period") as FundAnalyticsPeriod;
  const factorPeriod = factorPeriods.includes(rawPeriod) ? rawPeriod : "1Y";
  return (
    <FundDetailContent
      fundId={fundId}
      fundCode={search.get("fund_code") || undefined}
      shareClassId={search.get("share_class_id") || undefined}
      asOfDate={asOfDate}
      returnTo={returnTo}
      state={{
        tab,
        factorPeriod,
        onTabChange: (value) => {
          const next = new URLSearchParams(search);
          if (value && value !== "nav") next.set("tab", value);
          else next.delete("tab");
          setSearch(next);
        },
        onFactorPeriodChange: (value) => {
          const next = new URLSearchParams(search);
          next.set("factor_period", value);
          setSearch(next);
        },
      }}
    />
  );
};
