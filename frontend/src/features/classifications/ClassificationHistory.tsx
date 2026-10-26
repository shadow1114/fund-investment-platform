import { useQuery } from "@tanstack/react-query";
import { getClassificationHistory } from "../../api/generated/m17";
import { unwrapResponse } from "../../api/http";
import { ClassificationView } from "./ClassificationView";
import { ErrorState } from "../../components/ErrorState";
export const ClassificationHistory = ({
  fundId,
  decisionAt,
}: {
  fundId: string;
  decisionAt?: string;
}) => {
  const history = useQuery({
    queryKey: ["classification-history", fundId, decisionAt],
    queryFn: async () =>
      unwrapResponse(
        await getClassificationHistory(fundId, { decision_at: decisionAt }),
      ),
  });
  return (
    <details>
      <summary>可见分类历史</summary>
      <p>可见时点：{decisionAt || "当前"}</p>
      {history.isPending && <p>加载历史…</p>}
      {history.isError && <ErrorState error={history.error} />}
      {history.data?.map((revision) => (
        <article key={revision.revision_id}>
          <h3>
            修订 {revision.revision_id} / v{revision.version}
          </h3>
          <p>
            可用时间 {revision.available_at} · 审核者 {revision.actor} · 理由{" "}
            {revision.reason}
          </p>
          {revision.intervals.map((interval) => (
            <div key={interval.valid_from}>
              <p>
                生效区间 {interval.valid_from} —{" "}
                {interval.valid_to || "持续有效"}
              </p>
              <ClassificationView
                classification={interval.classification}
                evidence
              />
            </div>
          ))}
        </article>
      ))}
      <details>
        <summary>历史原始记录</summary>
        <pre>{history.data && JSON.stringify(history.data, null, 2)}</pre>
      </details>
    </details>
  );
};
