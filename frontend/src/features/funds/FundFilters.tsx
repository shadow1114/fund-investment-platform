import { FormEvent, useState } from "react";

export type FundFilterValues = {
  fund_name: string;
  fund_type: string;
  lifecycle_status: string;
  investment_eligibility: string;
  as_of_date: string;
  page_size: string;
  sort: string;
  order: string;
};

export const FundFilters = ({
  initialValues,
  onSubmit,
}: {
  initialValues: FundFilterValues;
  onSubmit: (values: FundFilterValues) => void;
}) => {
  const [values, setValues] = useState(initialValues);
  const update = (key: keyof FundFilterValues, value: string) =>
    setValues((current) => ({ ...current, [key]: value }));
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit(values);
  };

  return (
    <form onSubmit={submit} aria-label="基金筛选">
      <label>
        基金名称
        <input
          value={values.fund_name}
          onChange={(event) => update("fund_name", event.target.value)}
          name="fund_name"
        />
      </label>
      <label>
        基金类型（逗号分隔）
        <input
          value={values.fund_type}
          onChange={(event) => update("fund_type", event.target.value)}
          name="fund_type"
        />
      </label>
      <label>
        生命周期状态（逗号分隔）
        <input
          value={values.lifecycle_status}
          onChange={(event) => update("lifecycle_status", event.target.value)}
          name="lifecycle_status"
          placeholder="NORMAL,LIQUIDATED"
        />
      </label>
      <label>
        投资资格（逗号分隔）
        <input
          value={values.investment_eligibility}
          onChange={(event) =>
            update("investment_eligibility", event.target.value)
          }
          name="investment_eligibility"
          placeholder="FULLY_ELIGIBLE,HOLD_ONLY"
        />
      </label>
      <label>
        数据截止日
        <input
          type="date"
          value={values.as_of_date}
          onChange={(event) => update("as_of_date", event.target.value)}
          name="as_of_date"
        />
      </label>
      <label>
        每页数量
        <select
          value={values.page_size}
          onChange={(event) => update("page_size", event.target.value)}
          name="page_size"
        >
          <option value="10">10</option>
          <option value="20">20</option>
          <option value="50">50</option>
        </select>
      </label>
      <label>
        排序字段
        <select
          value={values.sort}
          onChange={(event) => update("sort", event.target.value)}
          name="sort"
        >
          <option value="fund_name">基金名称</option>
          <option value="inception_date">成立日期</option>
        </select>
      </label>
      <label>
        排序方向
        <select
          value={values.order}
          onChange={(event) => update("order", event.target.value)}
          name="order"
        >
          <option value="asc">升序</option>
          <option value="desc">降序</option>
        </select>
      </label>
      <button type="submit">查询</button>
    </form>
  );
};
