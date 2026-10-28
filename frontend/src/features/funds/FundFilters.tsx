import {
  Button,
  Group,
  MultiSelect,
  Select,
  SimpleGrid,
  Stack,
  TagsInput,
  TextInput,
} from "@mantine/core";
import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";

import { getClassificationCatalog } from "../../api/generated/m17";
import {
  InvestmentEligibility,
  LifecycleStatus,
} from "../../api/generated/m17.schemas";
import { unwrapResponse } from "../../api/http";
import {
  activeDimensions,
  dimensionLabels,
} from "../classifications/ClassificationView";

export type FundFilterValues = {
  asset_class: string[];
  strategy: string[];
  strategy_tags: string[];
  geography: string[];
  product_structure: string[];
  market_attributes: string[];
  classification_status: string[];
  fund_name: string;
  fund_type: string[];
  lifecycle_status: string[];
  investment_eligibility: string[];
  as_of_date: string;
  page_size: string;
  sort: string;
  order: string;
};

const lifecycleLabels: Record<string, string> = {
  NORMAL: "正常",
  SUSPENDED_SUBSCRIPTION: "暂停申购",
  LIQUIDATED: "已清算",
  MERGED: "已合并",
  TRANSFORMED: "已转型",
  UNKNOWN: "未知",
};
const eligibilityLabels: Record<string, string> = {
  FULLY_ELIGIBLE: "可新建仓",
  HOLD_ONLY: "仅可持有",
  LIMITED: "受限",
  EXIT_ONLY: "仅可退出",
  NOT_TRADABLE: "不可交易",
  UNKNOWN: "未知",
};

export const emptyFundFilters = (): FundFilterValues => ({
  asset_class: [],
  strategy: [],
  strategy_tags: [],
  geography: [],
  product_structure: [],
  market_attributes: [],
  classification_status: [],
  fund_name: "",
  fund_type: [],
  lifecycle_status: [],
  investment_eligibility: [],
  as_of_date: "",
  page_size: "20",
  sort: "fund_name",
  order: "asc",
});

export const FundFilters = ({
  initialValues,
  onSubmit,
  onReset,
}: {
  initialValues: FundFilterValues;
  onSubmit: (values: FundFilterValues) => void;
  onReset: () => void;
}) => {
  const catalog = useQuery({
    queryKey: ["classification-catalog"],
    queryFn: async () => unwrapResponse(await getClassificationCatalog()),
  });
  const [values, setValues] = useState(initialValues);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit(values);
  };

  const multiSelect = (
    key: keyof FundFilterValues,
    label: string,
    data: string[],
    valueLabels?: Record<string, string>,
  ) => (
    <MultiSelect
      key={key}
      label={label}
      aria-label={label}
      data={data.map((value) => ({
        value,
        label: valueLabels?.[value] ?? value,
      }))}
      value={values[key] as string[]}
      onChange={(selected) =>
        setValues((current) => ({ ...current, [key]: selected }))
      }
      searchable
      clearable
      hidePickedOptions
      nothingFoundMessage="没有可选项"
    />
  );

  return (
    <form onSubmit={submit} aria-label="基金筛选">
      <Stack gap="md">
        <Group align="flex-end" wrap="wrap">
          <TextInput
            label="基金名称"
            aria-label="基金名称"
            value={values.fund_name}
            onChange={(event) =>
              setValues((current) => ({
                ...current,
                fund_name: event.currentTarget.value,
              }))
            }
            placeholder="搜索基金名称"
            style={{ flex: "1 1 240px" }}
          />
          <TextInput
            type="date"
            label="数据截止日"
            aria-label="数据截止日"
            value={values.as_of_date}
            onChange={(event) =>
              setValues((current) => ({
                ...current,
                as_of_date: event.currentTarget.value,
              }))
            }
          />
          <Button type="submit">查询基金</Button>
          <Button type="button" variant="default" onClick={onReset}>
            重置
          </Button>
        </Group>

        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
          {activeDimensions.map((dimension) =>
            multiSelect(
              dimension,
              dimensionLabels[dimension],
              catalog.data?.dimensions[dimension] ?? [],
            ),
          )}
          {multiSelect(
            "strategy_tags",
            "策略标签（仅已确认）",
            catalog.data?.strategy_tags ?? [],
          )}
          {multiSelect(
            "classification_status",
            dimensionLabels.classification_status,
            catalog.data?.statuses ?? [],
          )}
          {multiSelect(
            "lifecycle_status",
            "生命周期状态",
            Object.values(LifecycleStatus),
            lifecycleLabels,
          )}
          {multiSelect(
            "investment_eligibility",
            "投资资格",
            Object.values(InvestmentEligibility),
            eligibilityLabels,
          )}
          <TagsInput
            label="基金类型代码"
            aria-label="基金类型代码"
            description="该查询当前没有服务端字典；逐项输入代码并按回车添加。"
            value={values.fund_type}
            onChange={(fund_type) =>
              setValues((current) => ({ ...current, fund_type }))
            }
            splitChars={["Enter"]}
            clearable
          />
          <Select
            label="每页数量"
            aria-label="每页数量"
            data={["10", "20", "50"].map((value) => ({ value, label: value }))}
            value={values.page_size}
            onChange={(page_size) =>
              setValues((current) => ({
                ...current,
                page_size: page_size ?? "20",
              }))
            }
            allowDeselect={false}
          />
          <Select
            label="排序字段"
            aria-label="排序字段"
            data={[
              { value: "fund_name", label: "基金名称" },
              { value: "inception_date", label: "成立日期" },
            ]}
            value={values.sort}
            onChange={(sort) =>
              setValues((current) => ({
                ...current,
                sort: sort ?? "fund_name",
              }))
            }
            allowDeselect={false}
          />
          <Select
            label="排序方向"
            aria-label="排序方向"
            data={[
              { value: "asc", label: "升序" },
              { value: "desc", label: "降序" },
            ]}
            value={values.order}
            onChange={(order) =>
              setValues((current) => ({ ...current, order: order ?? "asc" }))
            }
            allowDeselect={false}
          />
        </SimpleGrid>
        <section aria-label="历史维度筛选说明">
          <strong>历史维度（只读）</strong>
          <p>
            投资地域、产品结构和市场属性保留在历史修订中展示；本轮不将其作为当前分类筛选条件。
          </p>
          {(values.geography.length > 0 ||
            values.product_structure.length > 0 ||
            values.market_attributes.length > 0) && (
            <p>
              历史链接条件：地域 {values.geography.join("、") || "无"}；结构{" "}
              {values.product_structure.join("、") || "无"}；属性{" "}
              {values.market_attributes.join("、") || "无"}
            </p>
          )}
        </section>
        {catalog.isError && (
          <p role="alert">分类字典加载失败，分类筛选暂不可用。</p>
        )}
      </Stack>
    </form>
  );
};
