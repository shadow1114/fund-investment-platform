import type { ColDef } from "ag-grid-community";
import { ResearchDataTable } from "../../components/ResearchDataTable";
import {
  Alert,
  Button,
  Group,
  Modal,
  NumberInput,
  Paper,
  Stack,
  Text,
  Textarea,
} from "@mantine/core";
import { useEffect, useMemo, useState } from "react";

import type {
  Decision,
  DecisionReviewOutcomeEnvelope,
  DecisionReviewRequest,
  DecisionReviewRequestAction,
  Weight,
} from "../../api/generated/m17.schemas";
import { ErrorState } from "../../components/ErrorState";
import { StatusBadge } from "../../components/StatusBadge";
import { WeightExplainChain } from "../../components/WeightExplainChain";

type Props = {
  decision: Decision;
  reviewResult?: DecisionReviewOutcomeEnvelope;
  reviewAction?: DecisionReviewRequestAction;
  canReview: boolean;
  pending: boolean;
  error: unknown;
  onReview: (request: DecisionReviewRequest) => void;
};

export const DecisionReviewPanel = ({
  decision,
  reviewResult,
  reviewAction,
  canReview,
  pending,
  error,
  onReview,
}: Props) => {
  const [reason, setReason] = useState("");
  const [weights, setWeights] = useState<Weight[]>(
    decision.proposed_weights.map((weight) => ({ ...weight })),
  );
  const [action, setAction] = useState<DecisionReviewRequestAction>();
  const sum = useMemo(
    () =>
      weights.reduce(
        (total, weight) =>
          total + (Number.isFinite(weight.weight) ? weight.weight : 0),
        0,
      ),
    [weights],
  );
  const columns = useMemo<ColDef<Weight>[]>(
    () => [
      { field: "fund_id", headerName: "基金", lockVisible: true },
      {
        colId: "original",
        headerName: "原建议权重",
        valueGetter: ({ data }) =>
          decision.proposed_weights.find(
            (item) => item.fund_id === data?.fund_id,
          )?.weight,
        valueFormatter: ({ value }) =>
          value == null ? "未提供" : `${(value * 100).toFixed(2)}%`,
      },
      {
        field: "weight",
        headerName: "覆盖权重",
        minWidth: 230,
        cellRenderer: ({ data: weight }: { data: Weight }) => (
          <NumberInput
            aria-label={`${weight.fund_id} 覆盖权重`}
            min={0}
            max={1}
            step={0.01}
            decimalScale={6}
            value={weight.weight}
            onChange={(value) =>
              setWeights((current) =>
                current.map((item) =>
                  item.fund_id === weight.fund_id
                    ? { ...item, weight: Number(value) || 0 }
                    : item,
                ),
              )
            }
            suffix="（小数）"
          />
        ),
      },
      {
        colId: "difference",
        headerName: "差异",
        valueGetter: ({ data }) => {
          const original = decision.proposed_weights.find(
            (item) => item.fund_id === data?.fund_id,
          )?.weight;
          return original == null || !data ? null : data.weight - original;
        },
        valueFormatter: ({ value }) =>
          value == null ? "未提供" : `${(value * 100).toFixed(2)} 个百分点`,
      },
    ],
    [decision.proposed_weights],
  );
  const editable = decision.decision_status === "PROPOSED";
  useEffect(() => {
    if (reviewResult) setAction(undefined);
  }, [reviewResult]);

  const submit = () => {
    if (!action || !reason.trim()) return;
    onReview({
      action,
      reason: reason.trim(),
      ...(action === "OVERRIDDEN" ? { overridden_weights: weights } : {}),
    });
  };

  return (
    <Paper withBorder radius="sm" p="md" aria-label="决策复核">
      <Stack gap="md">
        <Group justify="space-between" wrap="wrap">
          <Text fw={600} size="lg">
            决策复核
          </Text>
          <StatusBadge
            domain="decision"
            value={
              reviewResult?.data.decision_status ?? decision.decision_status
            }
          />
        </Group>
        <WeightExplainChain
          originalWeights={
            reviewResult?.data.original_weights ?? decision.proposed_weights
          }
          finalWeights={
            reviewResult
              ? reviewResult.data.final_weights
              : decision.final_weights
          }
          review={
            reviewResult && reviewAction
              ? {
                  action: reviewAction,
                  reason: reviewResult.data.reason,
                  reviewed_by: reviewResult.data.reviewed_by,
                  reviewed_at: reviewResult.data.reviewed_at,
                }
              : decision.review
          }
          auditId={reviewResult?.meta.audit_id}
        />
        {canReview && editable ? (
          <Stack gap="sm">
            <Textarea
              label="复核理由"
              required
              minRows={3}
              value={reason}
              onChange={(event) => setReason(event.currentTarget.value)}
              description="说明批准、拒绝或覆盖的业务依据。"
            />
            <Text fw={600}>覆盖权重</Text>
            <div
              className="table-scroll"
              role="region"
              aria-label="可编辑覆盖权重"
              tabIndex={0}
            >
              <ResearchDataTable<Weight>
                caption="决策覆盖权重"
                layoutKey="decision-weight-overrides"
                rowData={weights}
                getRowId={({ data }) => data.fund_id}
                pagination
                paginationPageSize={20}
                paginationPageSizeSelector={[20, 50, 100]}
                columnDefs={columns}
                requiredColumnIds={["fund_id", "weight"]}
              />
            </div>
            <Text size="sm" c={Math.abs(sum - 1) <= 0.0001 ? "green" : "red"}>
              覆盖权重合计：{(sum * 100).toFixed(2)}%（提交要求约为 100%）
            </Text>
            <Group>
              <Button
                disabled={pending || !reason.trim()}
                onClick={() => setAction("APPROVED")}
              >
                批准
              </Button>
              <Button
                color="red"
                variant="light"
                disabled={pending || !reason.trim()}
                onClick={() => setAction("REJECTED")}
              >
                拒绝
              </Button>
              <Button
                variant="default"
                disabled={
                  pending ||
                  !reason.trim() ||
                  weights.length === 0 ||
                  Math.abs(sum - 1) > 0.0001
                }
                onClick={() => setAction("OVERRIDDEN")}
              >
                确认覆盖
              </Button>
            </Group>
          </Stack>
        ) : (
          <Alert color="yellow" variant="light">
            {!canReview
              ? "当前会话没有复核权限。"
              : "该决策已不是待复核状态，不能再次提交操作。"}
          </Alert>
        )}
        {error != null && <ErrorState error={error} />}
        <Modal
          opened={Boolean(action)}
          onClose={() => {
            if (!pending) setAction(undefined);
          }}
          title="确认决策复核"
          centered
        >
          <Stack>
            <Text>
              决策 {decision.decision_id} ·{" "}
              {action === "APPROVED"
                ? "批准"
                : action === "REJECTED"
                  ? "拒绝"
                  : "覆盖权重"}
            </Text>
            <Text size="sm">复核理由：{reason}</Text>
            {action === "OVERRIDDEN" && (
              <Text size="sm">覆盖后权重合计 {(sum * 100).toFixed(2)}%。</Text>
            )}
            <Alert color="yellow" variant="light">
              提交后会写入复核记录；最终权限、并发版本和权重校验由服务端执行。
            </Alert>
            {error != null && <ErrorState error={error} />}
            <Group justify="flex-end">
              <Button
                variant="default"
                disabled={pending}
                onClick={() => setAction(undefined)}
              >
                返回修改
              </Button>
              <Button
                color={action === "REJECTED" ? "red" : "teal"}
                loading={pending}
                disabled={!action || !reason.trim()}
                onClick={submit}
              >
                确认提交
              </Button>
            </Group>
          </Stack>
        </Modal>
      </Stack>
    </Paper>
  );
};
