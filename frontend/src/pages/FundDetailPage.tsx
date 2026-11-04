import { Link, useParams, useSearchParams } from "react-router-dom";
import type { FundFactorAnalysisEvaluationPeriod } from "../api/generated/m17.schemas";
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
    rawTab === "evaluation" || rawTab === "score" || rawTab === "factors"
      ? rawTab
      : "nav";
  const rawPeriod = search.get(
    "factor_period",
  ) as FundFactorAnalysisEvaluationPeriod;
  const factorPeriod = factorPeriods.includes(rawPeriod) ? rawPeriod : "1Y";
  return (
    <FundDetailContent
      fundId={fundId}
      shareClassId={search.get("share_class_id") || undefined}
      asOfDate={asOfDate}
      returnTo={returnTo}
      actions={<Link to={returnTo}>返回基金研究</Link>}
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
          next.set("tab", "factors");
          next.set("factor_period", value);
          setSearch(next);
        },
      }}
    />
  );
};
