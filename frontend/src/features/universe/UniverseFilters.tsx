import { type FormEvent, useState } from "react";

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

  return (
    <form aria-label="候选池快照查询" onSubmit={submit}>
      <label>
        策略 ID
        <input
          value={values.strategy_id}
          onChange={(event) => update("strategy_id", event.target.value)}
        />
      </label>
      <label>
        决策时间
        <input
          type="datetime-local"
          value={values.decision_at}
          onChange={(event) => update("decision_at", event.target.value)}
        />
      </label>
      <label>
        资格规则版本
        <input
          value={values.eligibility_rules_version}
          onChange={(event) =>
            update("eligibility_rules_version", event.target.value)
          }
        />
      </label>
      <button type="submit">查询快照</button>
    </form>
  );
};
