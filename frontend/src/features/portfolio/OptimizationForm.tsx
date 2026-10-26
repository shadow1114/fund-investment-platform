import {
  Alert,
  Button,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { useQuery } from "@tanstack/react-query";
import { listUniverses } from "../../api/generated/m17";
import type { OptimizationRequest } from "../../api/generated/m17.schemas";
import { unwrapResponse } from "../../api/http";

type Values = {
  decision_at: string;
  universe_id: string;
  return_estimate_version: string;
  risk_model_version: string;
};

type Props = {
  portfolioRuleVersion: string;
  pending: boolean;
  onSubmit: (request: OptimizationRequest) => void;
};

const validDate = (value: string) =>
  /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value));

export const OptimizationForm = ({
  portfolioRuleVersion,
  pending,
  onSubmit,
}: Props) => {
  const universes = useQuery({
    queryKey: ["optimization-universe-options"],
    queryFn: async () => unwrapResponse(await listUniverses()),
  });
  const form = useForm<Values>({
    initialValues: {
      decision_at: "",
      universe_id: "",
      return_estimate_version: "",
      risk_model_version: "",
    },
    validate: {
      decision_at: (value) => (validDate(value) ? null : "请输入有效决策日期"),
      universe_id: (value) => (value.trim() ? null : "请输入真实候选池 ID"),
      return_estimate_version: (value) =>
        value.trim() ? null : "请填写版本引用",
      risk_model_version: (value) => (value.trim() ? null : "请填写版本引用"),
    },
  });

  return (
    <Paper withBorder radius="sm" p="md">
      <form
        onSubmit={form.onSubmit((values) =>
          onSubmit({
            decision_at: values.decision_at,
            universe_id: values.universe_id.trim(),
            portfolio_rule_version: portfolioRuleVersion,
            return_estimate_version: values.return_estimate_version.trim(),
            risk_model_version: values.risk_model_version.trim(),
            mode: "REBALANCE",
          }),
        )}
        aria-label="优化输入"
      >
        <Stack gap="md">
          <div>
            <Text fw={600} size="lg">
              组合优化配置
            </Text>
            <Text size="sm" c="dimmed">
              引用真实候选池与服务端策略版本；PIT 校验和权重计算由服务端完成。
            </Text>
          </div>
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            <TextInput
              type="date"
              label="决策日期"
              required
              {...form.getInputProps("decision_at")}
            />
            {universes.data && universes.data.length > 0 ? (
              <Select
                label="候选池快照"
                required
                searchable
                data={universes.data.map((universe) => ({
                  value: universe.universe_id,
                  label: `${universe.universe_id} · ${universe.decision_at} · ${universe.universe_strategy}`,
                }))}
                value={form.values.universe_id || null}
                onChange={(value) => {
                  form.setFieldValue("universe_id", value ?? "");
                  const selected = universes.data?.find(
                    (universe) => universe.universe_id === value,
                  );
                  if (selected)
                    form.setFieldValue("decision_at", selected.decision_at);
                }}
                error={form.errors.universe_id}
                description={`从本次接口已返回的 ${universes.data.length} 个快照中选择；该列表接口没有分页。`}
              />
            ) : (
              <TextInput
                label="手动输入真实候选池 ID"
                required
                disabled={universes.isPending}
                description={
                  universes.isError
                    ? "候选池列表读取失败；手填 ID 仍由服务端校验。"
                    : "策略目录未提供或列表为空；服务端会校验此 ID 和访问权限。"
                }
                {...form.getInputProps("universe_id")}
              />
            )}
            <TextInput
              label="组合规则版本"
              value={portfolioRuleVersion}
              readOnly
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
          </SimpleGrid>
          {universes.isError && (
            <Alert color="yellow">
              无法读取候选池快照列表；可手动输入已存在 ID。
            </Alert>
          )}
          <Alert color="blue" variant="light">
            优化会提交后台计算任务。任务 ID 和结果会保存在此组合的 URL
            中，可刷新恢复。
          </Alert>
          <Button type="submit" loading={pending}>
            提交优化
          </Button>
        </Stack>
      </form>
    </Paper>
  );
};
