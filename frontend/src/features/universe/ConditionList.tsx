import { useId, useState } from "react";

import type { UniverseCondition } from "../../api/generated/m17.schemas";

type Props = {
  fundId: string;
  kind: "passed" | "failed";
  conditions: UniverseCondition[];
};

const labels = {
  passed: "通过条件",
  failed: "未通过条件",
} as const;

const displayValue = (value: unknown) => {
  if (value === null) return "null";
  if (typeof value === "string" || typeof value === "number") {
    return String(value);
  }
  return JSON.stringify(value);
};

export const ConditionList = ({ fundId, kind, conditions }: Props) => {
  const [expanded, setExpanded] = useState(false);
  const panelId = useId();
  const label = labels[kind];

  if (conditions.length === 0) return <span>{label}：无</span>;

  return (
    <div>
      <button
        type="button"
        aria-label={`${expanded ? "收起" : "展开"} ${fundId} 的${label}`}
        aria-expanded={expanded}
        aria-controls={panelId}
        onClick={() => setExpanded((value) => !value)}
      >
        {expanded ? "收起" : "展开"} {fundId} 的{label}（{conditions.length}）
      </button>
      {expanded && (
        <ul id={panelId} aria-label={`${fundId} 的${label}`}>
          {conditions.map((condition, index) => (
            <li key={`${condition.condition}-${index}`}>
              <strong>{condition.condition}</strong>
              <span>结果：{condition.result}</span>
              <span>实际值：{displayValue(condition.actual)}</span>
              {condition.gap !== undefined && (
                <span>差额：{condition.gap}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
