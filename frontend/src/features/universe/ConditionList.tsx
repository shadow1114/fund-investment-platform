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
  if (value === undefined) return "未返回";
  if (value === null) return "null";
  if (typeof value === "string" || typeof value === "number") {
    return String(value);
  }
  return JSON.stringify(value) ?? "不可用";
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
              <dl>
                <dt>筛选条件</dt>
                <dd>{condition.condition}</dd>
                <dt>结果</dt>
                <dd>
                  {condition.result === "PASS"
                    ? "通过"
                    : condition.result === "FAIL"
                      ? "未通过"
                      : `未知（${condition.result}）`}
                </dd>
                <dt>实际值</dt>
                <dd>{displayValue(condition.actual)}</dd>
                <dt>阈值</dt>
                <dd>接口未提供</dd>
                <dt>来源</dt>
                <dd>接口未提供</dd>
                {condition.gap !== undefined && (
                  <>
                    <dt>差额</dt>
                    <dd>{condition.gap}</dd>
                  </>
                )}
              </dl>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
