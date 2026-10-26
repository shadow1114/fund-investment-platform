import type {
  ClassificationPayloadModel,
  ClassificationSnapshot,
} from "../../api/generated/m17.schemas";
export const dimensions = [
  "asset_class",
  "strategy",
  "geography",
  "product_structure",
  "market_attributes",
] as const;
export const dimensionLabels: Record<string, string> = {
  asset_class: "资产类别",
  strategy: "投资策略",
  geography: "投资地域",
  product_structure: "产品结构",
  market_attributes: "市场属性",
  classification_status: "分类状态",
};
export const ClassificationView = ({
  classification,
  evidence = false,
}: {
  classification?:
    (ClassificationSnapshot & Partial<ClassificationPayloadModel>) | null;
  evidence?: boolean;
}) =>
  classification ? (
    <section aria-label="五维分类">
      <p>
        {classification.scheme} · 规则 {classification.rule_version} · 枚举{" "}
        {classification.enum_version} · 修订 {classification.revision_id} / v
        {classification.version}
      </p>
      <p>
        来源：{classification.source_summary?.join("、")} · 可用时间{" "}
        {classification.available_at} · 生效 {classification.valid_from}
      </p>
      {dimensions.map((name) => {
        const item = classification[name];
        return (
          <div key={name}>
            <strong>{dimensionLabels[name]}</strong>：{item.status} · 最终值{" "}
            {Array.isArray(item.value) ? item.value.join("、") : item.value}
            {!!item.candidates?.length && (
              <p>候选：{item.candidates.join("、")}</p>
            )}
            {evidence &&
              item.evidence?.map((entry, index) => (
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
      })}
    </section>
  ) : (
    <p>五维分类：UNKNOWN（暂无可见修订）</p>
  );
