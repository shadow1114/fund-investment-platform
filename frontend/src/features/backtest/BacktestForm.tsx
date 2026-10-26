import {
  Alert,
  Button,
  Checkbox,
  Fieldset,
  NumberInput,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
} from "@mantine/core";
import { useForm } from "@mantine/form";

import type { BacktestCreateRequest } from "../../api/generated/m17.schemas";

type Values = {
  strategy_id: string;
  start_date: string;
  end_date: string;
  amount: string;
  currency: string;
  backtest_mode: "CURRENT_RULE" | "HISTORICAL_FIDELITY";
  benchmark_id: string;
  equal_weight_baseline_enabled: boolean;
  in_sample_end: string;
  parameter_freeze_date: string;
  rebalancing_policy_version: string;
  portfolio_rule_version: string;
  return_estimate_version: string;
  risk_model_version: string;
  eligibility_rules_version: string;
  transaction_cost_model_version: string;
  execution_price_rule: string;
  cash_return_assumption: string;
  infeasible_handling: "ABORT" | "SKIP_PERIOD";
};

const validDate = (date: string) =>
  /^\d{4}-\d{2}-\d{2}$/.test(date) && !Number.isNaN(Date.parse(date));

const initial: Values = {
  strategy_id: "",
  start_date: "",
  end_date: "",
  amount: "",
  currency: "CNY",
  backtest_mode: "CURRENT_RULE",
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
  execution_price_rule: "",
  cash_return_assumption: "",
  infeasible_handling: "ABORT",
};

type Props = {
  pending?: boolean;
  onSubmit: (request: BacktestCreateRequest) => void;
};

export const BacktestForm = ({ pending, onSubmit }: Props) => {
  const form = useForm<Values>({
    initialValues: initial,
    validate: {
      strategy_id: (value) => (value.trim() ? null : "请输入真实策略 ID"),
      start_date: (value, values) =>
        !validDate(value)
          ? "请输入有效开始日期"
          : validDate(values.end_date) && value > values.end_date
            ? "开始日期不能晚于结束日期"
            : null,
      end_date: (value, values) =>
        !validDate(value)
          ? "请输入有效结束日期"
          : validDate(values.start_date) && value < values.start_date
            ? "结束日期不能早于开始日期"
            : null,
      amount: (value) => (Number(value) > 0 ? null : "初始资金必须大于 0"),
      currency: (value) => (value.trim() ? null : "请输入币种代码"),
      benchmark_id: (value) => (value.trim() ? null : "请输入真实基准 ID"),
      rebalancing_policy_version: (value) =>
        value.trim() ? null : "请填写版本引用",
      portfolio_rule_version: (value) =>
        value.trim() ? null : "请填写版本引用",
      return_estimate_version: (value) =>
        value.trim() ? null : "请填写版本引用",
      risk_model_version: (value) => (value.trim() ? null : "请填写版本引用"),
      eligibility_rules_version: (value) =>
        value.trim() ? null : "请填写版本引用",
      transaction_cost_model_version: (value) =>
        value.trim() ? null : "请填写版本引用",
      execution_price_rule: (value) =>
        value.trim() ? null : "请填写服务端支持的规则标识",
      cash_return_assumption: (value) =>
        value.trim() ? null : "请填写服务端支持的假设标识",
      in_sample_end: (value, values) =>
        value && !validDate(value)
          ? "请输入有效样本内结束日"
          : value && !values.parameter_freeze_date
            ? "请同时填写参数冻结日"
            : null,
      parameter_freeze_date: (value, values) =>
        value && !validDate(value)
          ? "请输入有效参数冻结日"
          : value && !values.in_sample_end
            ? "请同时填写样本内结束日"
            : value && values.in_sample_end && value < values.in_sample_end
              ? "参数冻结日不能早于样本内结束日"
              : null,
    },
  });

  const submit = (values: Values) => {
    const request: BacktestCreateRequest = {
      strategy_id: values.strategy_id.trim(),
      start_date: values.start_date,
      end_date: values.end_date,
      initial_capital: {
        amount: values.amount,
        currency: values.currency.trim().toUpperCase(),
      },
      backtest_mode: values.backtest_mode,
      benchmark_id: values.benchmark_id.trim(),
      equal_weight_baseline_enabled: values.equal_weight_baseline_enabled,
      rebalancing_policy_version: values.rebalancing_policy_version.trim(),
      portfolio_rule_version: values.portfolio_rule_version.trim(),
      return_estimate_version: values.return_estimate_version.trim(),
      risk_model_version: values.risk_model_version.trim(),
      eligibility_rules_version: values.eligibility_rules_version.trim(),
      transaction_cost_model_version:
        values.transaction_cost_model_version.trim(),
      execution_price_rule: values.execution_price_rule.trim(),
      cash_return_assumption: values.cash_return_assumption.trim(),
      infeasible_handling: values.infeasible_handling,
    };
    if (values.in_sample_end && values.parameter_freeze_date) {
      request.is_oos_split = {
        in_sample_end: values.in_sample_end,
        parameter_freeze_date: values.parameter_freeze_date,
      };
    }
    onSubmit(request);
  };

  return (
    <form aria-label="回测配置" onSubmit={form.onSubmit(submit)}>
      <Stack gap="md">
        <Fieldset legend="创建回测配置">
          <Stack gap="md">
            <Text size="sm" c="dimmed">
              创建配置不会启动回测。必填的规则和模型版本由用户指定，页面不提供虚构默认值。
            </Text>
            <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
              <TextInput
                label="策略 ID"
                required
                {...form.getInputProps("strategy_id")}
              />
              <TextInput
                type="date"
                label="开始日期"
                required
                max={form.values.end_date || undefined}
                {...form.getInputProps("start_date")}
              />
              <TextInput
                type="date"
                label="结束日期"
                required
                min={form.values.start_date || undefined}
                {...form.getInputProps("end_date")}
              />
              <NumberInput
                label="初始资金"
                required
                min={0.01}
                decimalScale={2}
                value={form.values.amount}
                onChange={(value) =>
                  form.setFieldValue("amount", String(value))
                }
                error={form.errors.amount}
              />
              <TextInput
                label="币种代码"
                required
                {...form.getInputProps("currency")}
              />
              <Select
                label="回测模式"
                data={[
                  { value: "CURRENT_RULE", label: "当前规则" },
                  { value: "HISTORICAL_FIDELITY", label: "历史规则还原" },
                ]}
                allowDeselect={false}
                value={form.values.backtest_mode}
                onChange={(value) =>
                  form.setFieldValue(
                    "backtest_mode",
                    value === "HISTORICAL_FIDELITY" ? value : "CURRENT_RULE",
                  )
                }
              />
              <TextInput
                label="基准 ID"
                required
                {...form.getInputProps("benchmark_id")}
              />
              <Select
                label="不可行处理"
                data={[
                  { value: "ABORT", label: "中止回测" },
                  { value: "SKIP_PERIOD", label: "跳过该期" },
                ]}
                allowDeselect={false}
                value={form.values.infeasible_handling}
                onChange={(value) =>
                  form.setFieldValue(
                    "infeasible_handling",
                    value === "SKIP_PERIOD" ? value : "ABORT",
                  )
                }
              />
              <TextInput
                label="再平衡政策版本"
                required
                {...form.getInputProps("rebalancing_policy_version")}
              />
              <TextInput
                label="组合规则版本"
                required
                {...form.getInputProps("portfolio_rule_version")}
              />
              <TextInput
                label="收益估计版本"
                required
                {...form.getInputProps("return_estimate_version")}
              />
              <TextInput
                label="风险模型版本"
                required
                {...form.getInputProps("risk_model_version")}
              />
              <TextInput
                label="资格规则版本"
                required
                {...form.getInputProps("eligibility_rules_version")}
              />
              <TextInput
                label="交易成本模型版本"
                required
                {...form.getInputProps("transaction_cost_model_version")}
              />
              <TextInput
                label="执行价格规则标识"
                required
                description="API 尚无可选值字典，请填写部署策略接受的标识。"
                {...form.getInputProps("execution_price_rule")}
              />
              <TextInput
                label="现金收益假设标识"
                required
                description="API 尚无可选值字典，请填写部署策略接受的标识。"
                {...form.getInputProps("cash_return_assumption")}
              />
              <TextInput
                type="date"
                label="样本内结束日（可选）"
                max={form.values.end_date || undefined}
                {...form.getInputProps("in_sample_end")}
              />
              <TextInput
                type="date"
                label="参数冻结日（可选）"
                min={form.values.in_sample_end || undefined}
                max={form.values.end_date || undefined}
                {...form.getInputProps("parameter_freeze_date")}
              />
            </SimpleGrid>
            <Checkbox
              label="启用等权基线"
              checked={form.values.equal_weight_baseline_enabled}
              onChange={(event) =>
                form.setFieldValue(
                  "equal_weight_baseline_enabled",
                  event.currentTarget.checked,
                )
              }
            />
            {(form.errors.in_sample_end ||
              form.errors.parameter_freeze_date) && (
              <Alert color="red">
                样本内结束日和参数冻结日必须同时填写，且冻结日不得早于样本内结束日。
              </Alert>
            )}
          </Stack>
        </Fieldset>
        <Button type="submit" loading={pending}>
          创建回测配置
        </Button>
      </Stack>
    </form>
  );
};
