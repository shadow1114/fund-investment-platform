import type { BacktestValidation as Validation } from "../../api/generated/m17.schemas";

const labels: Record<string, string> = {
  PASS: "通过（PASS）",
  PASS_WITH_WARNINGS: "通过，但有警告（PASS_WITH_WARNINGS）",
};

export const BacktestValidation = ({
  validation,
}: {
  validation: Validation;
}) => (
  <section aria-label="配置预校验">
    <h2>配置预校验</h2>
    <strong>
      {labels[validation.validation_result] ?? validation.validation_result}
    </strong>
    <p>预热结束日：{validation.warm_up_end_date}</p>
    <p>
      有效区间：{validation.effective_period.from} 至{" "}
      {validation.effective_period.to}
    </p>
    <p>
      样本内 {validation.in_sample_length_days} 天；样本外{" "}
      {validation.out_of_sample_length_days} 天
    </p>
    {validation.warnings.length > 0 && (
      <>
        <h3>警告</h3>
        <ul>
          {validation.warnings.map((issue) => (
            <li key={issue.code}>
              <strong>{issue.code}</strong>：{issue.message}
            </li>
          ))}
        </ul>
      </>
    )}
    {validation.blocking_issues.length > 0 && (
      <>
        <h3>阻断问题</h3>
        <ul>
          {validation.blocking_issues.map((issue) => (
            <li key={issue.code}>
              <strong>{issue.code}</strong>：{issue.message}
            </li>
          ))}
        </ul>
      </>
    )}
  </section>
);
