import { Alert, Modal, Text } from "@mantine/core";
import { useMediaQuery } from "@mantine/hooks";
import { lazy, Suspense, useState } from "react";
import { Link } from "react-router-dom";
import type {
  FundFactorAnalysisEvaluationPeriod,
  FundListItem,
} from "../../api/generated/m17.schemas";
import type { FundDetailTab } from "./FundDetailContent";

const FundDetailContent = lazy(() =>
  import("./FundDetailContent").then((module) => ({
    default: module.FundDetailContent,
  })),
);

type Props = {
  fund: FundListItem | null;
  asOfDate?: string;
  returnTo: string;
  onClose: () => void;
};

function ModalDetail({
  fund,
  asOfDate,
  returnTo,
}: Omit<Props, "onClose"> & { fund: FundListItem }) {
  const [tab, setTab] = useState<FundDetailTab>("nav");
  const [factorPeriod, setFactorPeriod] =
    useState<FundFactorAnalysisEvaluationPeriod>("1Y");
  const search = new URLSearchParams({
    share_class_id: fund.share_class_id,
    return_to: returnTo,
  });
  if (asOfDate) search.set("as_of_date", asOfDate);
  if (tab !== "nav") search.set("tab", tab);
  if (tab === "factors") search.set("factor_period", factorPeriod);
  return (
    <>
      <Alert mb="md" color="yellow">
        申购状态按当前接口固定显示为开放，非实时交易状态。
      </Alert>
      <Suspense fallback={<Text role="status">正在加载基金详情…</Text>}>
        <FundDetailContent
          fundId={fund.fund_id}
          shareClassId={fund.share_class_id}
          asOfDate={asOfDate}
          returnTo={returnTo}
          actions={
            <Link to={`/funds/${fund.fund_id}?${search.toString()}`}>
              打开独立详情页
            </Link>
          }
          state={{
            tab,
            factorPeriod,
            onTabChange: (value) => setTab((value || "nav") as FundDetailTab),
            onFactorPeriodChange: setFactorPeriod,
          }}
        />
      </Suspense>
    </>
  );
}

export function FundDetailModal({ fund, asOfDate, returnTo, onClose }: Props) {
  const fullScreen = useMediaQuery("(max-width: 48em)");
  return (
    <Modal
      opened={fund !== null}
      onClose={onClose}
      title="基金详情"
      size="min(1200px, 95vw)"
      fullScreen={fullScreen}
      closeButtonProps={{ "aria-label": "关闭基金详情" }}
      returnFocus
      trapFocus
      closeOnEscape
    >
      {fund && (
        <ModalDetail
          key={fund.share_class_id + ":" + (asOfDate || "")}
          fund={fund}
          asOfDate={asOfDate}
          returnTo={returnTo}
        />
      )}
    </Modal>
  );
}
