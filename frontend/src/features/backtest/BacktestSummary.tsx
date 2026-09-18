import type {
  BacktestResult,
  PerformanceMetrics,
} from "../../api/generated/m17.schemas";
import { formatMoney } from "../../components/Formatters";
import { MetricValue } from "../../components/MetricValue";

const Metrics = ({
  title,
  metrics,
}: {
  title: string;
  metrics: PerformanceMetrics;
}) => (
  <section aria-label={title}>
    <h3>{title}</h3>
    <dl>
      <dt>总收益</dt>
      <dd>
        <MetricValue value={metrics.total_return} format="percent" />
      </dd>
      <dt>年化收益</dt>
      <dd>
        <MetricValue value={metrics.annualized_return} format="percent" />
      </dd>
      <dt>波动率</dt>
      <dd>
        <MetricValue value={metrics.volatility} format="percent" />
      </dd>
      <dt>最大回撤</dt>
      <dd>
        <MetricValue value={metrics.max_drawdown} format="percent" />
      </dd>
      <dt>Sharpe</dt>
      <dd>
        <MetricValue
          value={metrics.sharpe_ratio}
          status={metrics.sharpe_ratio_status}
          reason={metrics.sharpe_ratio_reason}
        />
      </dd>
    </dl>
  </section>
);

export const BacktestSummary = ({ result }: { result: BacktestResult }) => (
  <section aria-label="回测摘要">
    <h2>回测摘要</h2>
    {result.status === "COMPLETED" &&
      result.validation_status === "INVALID" && (
        <p role="alert">执行已完成，但验证结果为 INVALID。</p>
      )}
    {result.status === "ABORTED" && (
      <p role="alert">回测已 ABORTED，以下为可检查的已产生结果。</p>
    )}
    <p>模式：{result.backtest_mode}</p>
    <p>
      区间：{result.period.start_date} 至 {result.period.end_date}；预热至{" "}
      {result.period.warm_up_end_date}
    </p>
    <p>
      初始资金：
      {formatMoney(
        result.initial_capital.amount,
        result.initial_capital.currency,
      )}
      ；最终资产：
      {formatMoney(result.final_value.amount, result.final_value.currency)}
    </p>
    {result.validation_summary.warnings.length > 0 && (
      <p>警告：{result.validation_summary.warnings.join("、")}</p>
    )}
    {result.validation_summary.invalid_reasons.length > 0 && (
      <p>无效原因：{result.validation_summary.invalid_reasons.join("、")}</p>
    )}
    <Metrics title="组合" metrics={result.summary.portfolio} />
    <Metrics title="基准" metrics={result.summary.benchmark} />
    {result.summary.equal_weight_baseline ? (
      <Metrics
        title="等权基线"
        metrics={result.summary.equal_weight_baseline}
      />
    ) : (
      <p>
        等权基线不可用（
        {result.summary.equal_weight_baseline_reason ??
          result.summary.equal_weight_baseline_status}
        ）
      </p>
    )}
    <p>
      相对基准超额收益：
      <MetricValue
        value={result.excess_return.vs_benchmark}
        status={result.excess_return.vs_benchmark_status}
        reason={result.excess_return.vs_benchmark_reason}
        format="percent"
      />
    </p>
    <p>
      相对等权超额收益：
      <MetricValue
        value={result.excess_return.vs_equal_weight}
        status={result.excess_return.vs_equal_weight_status}
        reason={result.excess_return.vs_equal_weight_reason}
        format="percent"
      />
    </p>
    <p>
      显著性：{result.significance_verdict.overall}（
      {result.significance_verdict.thresholds_status}）
    </p>
  </section>
);
