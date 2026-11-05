import { Modal, Text } from "@mantine/core";
import { lazy, Suspense, useState } from "react";
import type { FundListItem } from "../../api/generated/m17.schemas";
import type { FundDetailTab } from "./FundDetailContent";
import type { FundAnalyticsPeriod } from "./FactorAnalysisPanel";

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
  const [factorPeriod, setFactorPeriod] = useState<FundAnalyticsPeriod>("1Y");
  return (
    <>
      <Suspense fallback={<Text role="status">正在加载基金详情…</Text>}>
        <FundDetailContent
          fundId={fund.fund_id}
          fundCode={fund.fund_code ?? undefined}
          shareClassId={fund.share_class_id}
          asOfDate={asOfDate}
          returnTo={returnTo}
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
  return (
    <Modal.Root
      opened={fund !== null}
      onClose={onClose}
      size="100%"
      xOffset={0}
      yOffset={0}
      returnFocus
      trapFocus
      closeOnEscape
      styles={{
        inner: {
          top: "var(--app-shell-header-offset, 0px)",
          left: "var(--app-shell-navbar-offset, 0px)",
          width: "calc(100% - var(--app-shell-navbar-offset, 0px))",
          height: "calc(100dvh - var(--app-shell-header-offset, 0px))",
          padding: 0,
          alignItems: "stretch",
        },
        overlay: {
          top: "var(--app-shell-header-offset, 0px)",
          left: "var(--app-shell-navbar-offset, 0px)",
          width: "calc(100% - var(--app-shell-navbar-offset, 0px))",
          height: "calc(100dvh - var(--app-shell-header-offset, 0px))",
        },
        content: {
          flex: 1,
          height: "100%",
          maxHeight: "100%",
          borderRadius: 0,
        },
        header: {
          minHeight: 40,
          padding: "4px 12px",
          justifyContent: "flex-end",
        },
        body: { padding: "0 16px 16px" },
      }}
    >
      <Modal.Overlay />
      <Modal.Content aria-label="基金详情">
        <Modal.Header>
          <Modal.CloseButton aria-label="关闭基金详情" />
        </Modal.Header>
        <Modal.Body>
          {fund && (
            <ModalDetail
              key={fund.share_class_id + ":" + (asOfDate || "")}
              fund={fund}
              asOfDate={asOfDate}
              returnTo={returnTo}
            />
          )}
        </Modal.Body>
      </Modal.Content>
    </Modal.Root>
  );
}
