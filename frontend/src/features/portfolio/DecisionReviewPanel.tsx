import { useState } from "react";

import type {
  Decision,
  DecisionReviewRequest,
  DecisionReviewRequestAction,
  Weight,
} from "../../api/generated/m17.schemas";
import { ErrorState } from "../../components/ErrorState";
import { WeightExplainChain } from "../../components/WeightExplainChain";

const parseWeights = (input: string): Weight[] =>
  input
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [fundId, rawWeight] = line.split(",").map((value) => value.trim());
      const weight = Number(rawWeight);
      if (!fundId || !Number.isFinite(weight)) {
        throw new Error("覆盖权重格式应为：基金ID,小数权重");
      }
      return { fund_id: fundId, weight };
    });

type Props = {
  decision: Decision;
  canReview: boolean;
  pending: boolean;
  error: unknown;
  onReview: (request: DecisionReviewRequest) => void;
};

export const DecisionReviewPanel = ({
  decision,
  canReview,
  pending,
  error,
  onReview,
}: Props) => {
  const [reason, setReason] = useState("");
  const [weightsInput, setWeightsInput] = useState("");
  const [inputError, setInputError] = useState<string>();

  const review = (action: DecisionReviewRequestAction) => {
    setInputError(undefined);
    try {
      onReview({
        action,
        reason,
        ...(action === "OVERRIDDEN"
          ? { overridden_weights: parseWeights(weightsInput) }
          : {}),
      });
    } catch (caught) {
      setInputError(caught instanceof Error ? caught.message : "覆盖权重无效");
    }
  };

  return (
    <section aria-label="决策复核">
      <h2>决策复核</h2>
      <p>决策状态：{decision.decision_status}</p>
      <WeightExplainChain
        proposedWeights={decision.proposed_weights}
        finalWeights={decision.final_weights}
        review={decision.review}
      />
      {canReview && (
        <fieldset>
          <legend>PM 复核操作</legend>
          <label>
            复核原因
            <textarea
              required
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <label>
            覆盖权重（每行：基金ID,小数权重）
            <textarea
              value={weightsInput}
              onChange={(event) => setWeightsInput(event.target.value)}
            />
          </label>
          <button
            disabled={pending || !reason.trim()}
            onClick={() => review("APPROVED")}
          >
            批准
          </button>
          <button
            disabled={pending || !reason.trim()}
            onClick={() => review("REJECTED")}
          >
            拒绝
          </button>
          <button
            disabled={pending || !reason.trim() || !weightsInput.trim()}
            onClick={() => review("OVERRIDDEN")}
          >
            覆盖
          </button>
        </fieldset>
      )}
      {inputError && <p role="alert">{inputError}</p>}
      {error ? <ErrorState error={error} /> : null}
    </section>
  );
};
