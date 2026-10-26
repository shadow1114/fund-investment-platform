import { Button, Group, TextInput } from "@mantine/core";
import { useState, type FormEvent } from "react";

export type UniverseFilterValues = {
  strategy_id: string;
  decision_at: string;
  eligibility_rules_version: string;
};

type Props = {
  initialValues: UniverseFilterValues;
  onSubmit: (values: UniverseFilterValues) => void;
};

export const UniverseFilters = ({ initialValues, onSubmit }: Props) => {
  const [values, setValues] = useState(initialValues);
  const update = (key: keyof UniverseFilterValues, value: string) =>
    setValues((current) => ({ ...current, [key]: value }));
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit(values);
  };
  const reset = () => {
    const empty = {
      strategy_id: "",
      decision_at: "",
      eligibility_rules_version: "",
    };
    setValues(empty);
    onSubmit(empty);
  };

  return (
    <form aria-label="候选池快照查询" onSubmit={submit}>
      <Group align="flex-end" wrap="wrap">
        <TextInput
          label="策略 ID"
          value={values.strategy_id}
          onChange={(event) => update("strategy_id", event.currentTarget.value)}
        />
        <TextInput
          type="date"
          label="决策日期"
          value={values.decision_at}
          onChange={(event) => update("decision_at", event.currentTarget.value)}
        />
        <TextInput
          label="资格规则版本"
          value={values.eligibility_rules_version}
          onChange={(event) =>
            update("eligibility_rules_version", event.currentTarget.value)
          }
        />
        <Button type="submit">查询快照</Button>
        <Button type="button" variant="default" onClick={reset}>
          重置
        </Button>
      </Group>
      <p>策略目录接口未提供；按已有策略 ID 查询，不生成虚构选项。</p>
    </form>
  );
};
