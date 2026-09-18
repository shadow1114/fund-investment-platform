import { useState } from "react";

import type { BacktestCreateRequest } from "../../api/generated/m17.schemas";

type Props = {
  disabled?: boolean;
  pending?: boolean;
  onSubmit: (request: BacktestCreateRequest) => void;
};

const initial = {
  strategy_id: "",
  start_date: "",
  end_date: "",
  amount: "1000000.00",
  currency: "CNY",
  backtest_mode: "CURRENT_RULE" as const,
  benchmark_id: "",
  equal_weight_baseline_enabled: true,
  in_sample_end: "",
  parameter_freeze_date: "",
  rebalancing_policy_version: "",
  portfolio_rule_version: "",
  return_estimate_version: "",
  risk_model_version: "",
  eligibility_rules_version: "",
  transaction_cost_model_version: "",
  execution_price_rule: "NEXT_DAY_NAV",
  cash_return_assumption: "ZERO",
  infeasible_handling: "ABORT" as const,
};

export const BacktestForm = ({ disabled, pending, onSubmit }: Props) => {
  const [form, setForm] = useState(initial);
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((current) => ({ ...current, [key]: value }));

  return (
    <form
      aria-label="回测配置"
      onSubmit={(event) => {
        event.preventDefault();
        const request: BacktestCreateRequest = {
          strategy_id: form.strategy_id,
          start_date: form.start_date,
          end_date: form.end_date,
          initial_capital: { amount: form.amount, currency: form.currency },
          backtest_mode: form.backtest_mode,
          benchmark_id: form.benchmark_id,
          equal_weight_baseline_enabled: form.equal_weight_baseline_enabled,
          rebalancing_policy_version: form.rebalancing_policy_version,
          portfolio_rule_version: form.portfolio_rule_version,
          return_estimate_version: form.return_estimate_version,
          risk_model_version: form.risk_model_version,
          eligibility_rules_version: form.eligibility_rules_version,
          transaction_cost_model_version: form.transaction_cost_model_version,
          execution_price_rule: form.execution_price_rule,
          cash_return_assumption: form.cash_return_assumption,
          infeasible_handling: form.infeasible_handling,
        };
        if (form.in_sample_end && form.parameter_freeze_date) {
          request.is_oos_split = {
            in_sample_end: form.in_sample_end,
            parameter_freeze_date: form.parameter_freeze_date,
          };
        }
        onSubmit(request);
      }}
    >
      <fieldset disabled={disabled || pending}>
        <legend>创建配置（创建不会启动计算）</legend>
        <label>
          策略 ID
          <input
            required
            value={form.strategy_id}
            onChange={(event) => set("strategy_id", event.target.value)}
          />
        </label>
        <label>
          开始日期
          <input
            required
            type="date"
            value={form.start_date}
            onChange={(event) => set("start_date", event.target.value)}
          />
        </label>
        <label>
          结束日期
          <input
            required
            type="date"
            value={form.end_date}
            onChange={(event) => set("end_date", event.target.value)}
          />
        </label>
        <label>
          初始资金
          <input
            required
            inputMode="decimal"
            value={form.amount}
            onChange={(event) => set("amount", event.target.value)}
          />
        </label>
        <label>
          币种
          <input
            required
            value={form.currency}
            onChange={(event) => set("currency", event.target.value)}
          />
        </label>
        <label>
          回测模式
          <select
            value={form.backtest_mode}
            onChange={(event) =>
              set(
                "backtest_mode",
                event.target.value as typeof form.backtest_mode,
              )
            }
          >
            <option value="CURRENT_RULE">CURRENT_RULE</option>
            <option value="HISTORICAL_FIDELITY">HISTORICAL_FIDELITY</option>
          </select>
        </label>
        <label>
          基准 ID
          <input
            required
            value={form.benchmark_id}
            onChange={(event) => set("benchmark_id", event.target.value)}
          />
        </label>
        <label>
          <input
            type="checkbox"
            checked={form.equal_weight_baseline_enabled}
            onChange={(event) =>
              set("equal_weight_baseline_enabled", event.target.checked)
            }
          />
          启用等权基线
        </label>
        <label>
          样本内结束日
          <input
            type="date"
            value={form.in_sample_end}
            onChange={(event) => set("in_sample_end", event.target.value)}
          />
        </label>
        <label>
          参数冻结日
          <input
            type="date"
            value={form.parameter_freeze_date}
            onChange={(event) =>
              set("parameter_freeze_date", event.target.value)
            }
          />
        </label>
        <label>
          再平衡政策版本
          <input
            required
            value={form.rebalancing_policy_version}
            onChange={(event) =>
              set("rebalancing_policy_version", event.target.value)
            }
          />
        </label>
        <label>
          组合规则版本
          <input
            required
            value={form.portfolio_rule_version}
            onChange={(event) =>
              set("portfolio_rule_version", event.target.value)
            }
          />
        </label>
        <label>
          收益估计版本
          <input
            required
            value={form.return_estimate_version}
            onChange={(event) =>
              set("return_estimate_version", event.target.value)
            }
          />
        </label>
        <label>
          风险模型版本
          <input
            required
            value={form.risk_model_version}
            onChange={(event) => set("risk_model_version", event.target.value)}
          />
        </label>
        <label>
          资格规则版本
          <input
            required
            value={form.eligibility_rules_version}
            onChange={(event) =>
              set("eligibility_rules_version", event.target.value)
            }
          />
        </label>
        <label>
          交易成本模型版本
          <input
            required
            value={form.transaction_cost_model_version}
            onChange={(event) =>
              set("transaction_cost_model_version", event.target.value)
            }
          />
        </label>
        <label>
          执行价格规则
          <input
            required
            value={form.execution_price_rule}
            onChange={(event) =>
              set("execution_price_rule", event.target.value)
            }
          />
        </label>
        <label>
          现金收益假设
          <input
            required
            value={form.cash_return_assumption}
            onChange={(event) =>
              set("cash_return_assumption", event.target.value)
            }
          />
        </label>
        <label>
          不可行处理
          <select
            value={form.infeasible_handling}
            onChange={(event) =>
              set(
                "infeasible_handling",
                event.target.value as typeof form.infeasible_handling,
              )
            }
          >
            <option value="ABORT">ABORT</option>
            <option value="SKIP_PERIOD">SKIP_PERIOD</option>
          </select>
        </label>
        <button type="submit">{pending ? "创建中…" : "创建回测"}</button>
      </fieldset>
    </form>
  );
};
