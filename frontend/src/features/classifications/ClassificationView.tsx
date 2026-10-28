import type {
  ClassificationPayloadModel,
  ClassificationSnapshot,
  DimensionResult,
} from "../../api/generated/m17.schemas";

export const activeDimensions = ["asset_class", "strategy"] as const;
export const historicalDimensions = [
  "geography",
  "product_structure",
  "market_attributes",
] as const;
export const dimensions = [
  ...activeDimensions,
  ...historicalDimensions,
] as const;
export const dimensionLabels: Record<string, string> = {
  asset_class: "资产类别",
  strategy: "投资策略",
  geography: "投资地域",
  product_structure: "产品结构",
  market_attributes: "市场属性",
  classification_status: "分类状态",
  strategy_tags: "策略标签",
};

const evaluationLabel: Record<string, string> = {
  NOT_EVALUATED: "当前未评估",
  EVALUATED: "已评估",
  PAUSED: "暂停更新（历史保留）",
};
const statusLabel: Record<string, string> = {
  CONFIRMED: "已确认",
  CANDIDATE: "候选",
  CONFLICT: "冲突",
  UNKNOWN: "未知",
};

const Result = ({
  name,
  result,
  evidence,
}: {
  name: string;
  result: DimensionResult;
  evidence: boolean;
}) => (
  <div>
    <strong>{dimensionLabels[name]}</strong>：
    {statusLabel[result.status] ?? result.status}
    {result.evaluation_state && (
      <>
        {" "}
        · 执行状态：
        {evaluationLabel[result.evaluation_state] ?? result.evaluation_state}
      </>
    )}
    {result.evaluation_state !== "PAUSED" && (
      <>
        {" "}
        · 最终值{" "}
        {Array.isArray(result.value) ? result.value.join("、") : result.value}
      </>
    )}
    {!!result.candidates?.length && <p>候选：{result.candidates.join("、")}</p>}
    {evidence &&
      result.evidence?.map((entry, index) => (
        <dl key={index} aria-label={`${dimensionLabels[name]}证据`}>
          {Object.entries(entry).map(([key, value]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>{String(value ?? "—")}</dd>
            </div>
          ))}
        </dl>
      ))}
  </div>
);

export const ClassificationView = ({
  classification,
  evidence = false,
}: {
  classification?:
    (ClassificationSnapshot & Partial<ClassificationPayloadModel>) | null;
  evidence?: boolean;
}) =>
  classification ? (
    <section aria-label="基金分类">
      <p>修订 {classification.revision_id ?? "—"} / {classification.version ?? "—"}</p>
      {classification.source_summary && (
        <p>
          来源：{classification.source_summary.join("、")} · 可用时间{" "}
          {classification.available_at} · 生效 {classification.valid_from}
        </p>
      )}
      {activeDimensions.map((name) => (
        <Result
          key={name}
          name={name}
          result={classification[name]}
          evidence={evidence}
        />
      ))}
      <section aria-label="独立策略标签">
        <h4>独立策略标签</h4>
        {classification.strategy_tags === undefined ||
        classification.strategy_tags === null ? (
          <p>该历史记录未包含量化标签，无法据此判断是否为量化策略。</p>
        ) : (
          <p>
            已确认策略标签：
            {classification.strategy_tags.length
              ? classification.strategy_tags.join("、")
              : "无"}
          </p>
        )}
        {classification.strategy_tag_results ? (
          Object.entries(classification.strategy_tag_results).map(
            ([tag, result]) => (
              <div key={tag}>
                <strong>{tag}</strong>：
                {statusLabel[result.status] ?? result.status}
                {result.evaluation_state === "NOT_EVALUATED" && (
                  <span> · 标签未评估</span>
                )}
                {result.evaluation_state === "EVALUATED" && (
                  <span> · 已评估</span>
                )}
                {!!result.candidates?.length && (
                  <p>标签候选：{result.candidates.join("、")}</p>
                )}
                {evidence &&
                  result.evidence?.map((entry, index) => (
                    <dl key={index} aria-label={`${tag}标签证据`}>
                      {Object.entries(entry).map(([key, value]) => (
                        <div key={key}>
                          <dt>{key}</dt>
                          <dd>{String(value ?? "—")}</dd>
                        </div>
                      ))}
                    </dl>
                  ))}
              </div>
            ),
          )
        ) : classification.scheme === "FIP_CLASSIFICATION" ? (
          <p>标签结果尚未提供。</p>
        ) : null}
      </section>
      <details>
        <summary>历史维度（只读）</summary>
        <p>地域、产品结构和市场属性保留为历史信息，当前不参与分类结果。</p>
        {historicalDimensions.map((name) => (
          <Result
            key={name}
            name={name}
            result={classification[name]}
            evidence={evidence}
          />
        ))}
      </details>
    </section>
  ) : (
    <p>分类：UNKNOWN（暂无可见修订）</p>
  );
