import type {
  FundEvaluation,
  FundEvaluationMeta,
  FundScore,
  FundScoreMeta,
} from "../../api/generated/m17.schemas";
import { MetricValue } from "../../components/MetricValue";
import { ScoreExplainChain } from "../../components/ScoreExplainChain";

const VersionDetails = ({
  entries,
}: {
  entries: Array<[label: string, value: string]>;
}) => (
  <dl aria-label="版本信息">
    {entries.map(([label, value]) => (
      <div key={label}>
        <dt>{label}</dt>
        <dd>{value}</dd>
      </div>
    ))}
  </dl>
);

export const EvaluationMetrics = ({
  evaluation,
  meta,
}: {
  evaluation: FundEvaluation;
  meta: FundEvaluationMeta;
}) => (
  <section aria-label="基金评估指标">
    <p>评估状态：{evaluation.evaluation_status}</p>
    <p>
      数据完整度：{evaluation.data_completeness.available} /{" "}
      {evaluation.data_completeness.expected}
    </p>
    <VersionDetails
      entries={[
        ["peer_group_version", meta.peer_group_version],
        ["evaluation_policy_version", meta.evaluation_policy_version],
        ["factor_version", meta.factor_version],
        ["data_version", meta.data_version],
      ]}
    />
    {evaluation.factor_results.length === 0 ? (
      <p>暂无评估因子</p>
    ) : (
      <table>
        <thead>
          <tr>
            <th scope="col">因子</th>
            <th scope="col">窗口</th>
            <th scope="col">原始值</th>
            <th scope="col">方向</th>
          </tr>
        </thead>
        <tbody>
          {evaluation.factor_results.map((factor) => (
            <tr key={`${factor.factor_id}-${factor.window}`}>
              <td>{factor.factor_id}</td>
              <td>{factor.window}</td>
              <td>
                <MetricValue
                  value={factor.raw_value}
                  status={factor.status}
                  reason={factor.reason_code}
                />
              </td>
              <td>{factor.direction}</td>
            </tr>
          ))}
        </tbody>
      </table>
    )}
  </section>
);

export const ScoreMetrics = ({
  score,
  meta,
}: {
  score: FundScore;
  meta: FundScoreMeta;
}) => (
  <section aria-label="基金评分指标">
    <h3>总分（无量纲）</h3>
    <MetricValue
      value={score.total_score}
      status={score.total_score_status}
      reason={score.total_score_reason}
    />
    <p>评分状态：{score.score_status}</p>
    <VersionDetails
      entries={[
        ["peer_group_version", meta.peer_group_version],
        ["scoring_policy_version", meta.scoring_policy_version],
        ["evaluation_policy_version", meta.evaluation_policy_version],
        ["factor_version", meta.factor_version],
        ["data_version", meta.data_version],
      ]}
    />
    <h3>分项评分（无量纲）</h3>
    <dl>
      <dt>收益</dt>
      <dd>
        <MetricValue
          value={score.sub_scores.return_score}
          status={score.sub_scores.return_score_status}
          reason={score.sub_scores.return_score_reason}
        />
      </dd>
      <dt>风险</dt>
      <dd>
        <MetricValue
          value={score.sub_scores.risk_score}
          status={score.sub_scores.risk_score_status}
          reason={score.sub_scores.risk_score_reason}
        />
      </dd>
      <dt>风险调整</dt>
      <dd>
        <MetricValue
          value={score.sub_scores.risk_adjusted_score}
          status={score.sub_scores.risk_adjusted_score_status}
          reason={score.sub_scores.risk_adjusted_score_reason}
        />
      </dd>
      <dt>稳定性</dt>
      <dd>
        <MetricValue
          value={score.sub_scores.stability_score}
          status={score.sub_scores.stability_score_status}
          reason={score.sub_scores.stability_score_reason}
        />
      </dd>
      <dt>相对表现</dt>
      <dd>
        <MetricValue
          value={score.sub_scores.relative_performance_score}
          status={score.sub_scores.relative_performance_score_status}
          reason={score.sub_scores.relative_performance_score_reason}
        />
      </dd>
    </dl>
    <h3>归因链路</h3>
    {score.attribution.length > 0 ? (
      <ScoreExplainChain attribution={score.attribution} />
    ) : (
      <p>暂无评分归因</p>
    )}
  </section>
);
