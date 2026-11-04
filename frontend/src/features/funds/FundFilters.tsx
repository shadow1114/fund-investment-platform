import { Button, Group, Select, Stack, Text, TextInput } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { getClassificationCatalog } from "../../api/generated/m17";
import { unwrapResponse } from "../../api/http";
import { listFundManagementCompaniesQueryOptions } from "../../api/queries";

export type FundFilterValues = {
  fund_name: string;
  fund_code: string;
  company_name: string;
  asset_class: string;
  sub_status: string;
  as_of_date: string;
  page_size: string;
  sort: string;
  order: string;
  // Retained in URL and saved-view state for links created before the new page.
  strategy: string[];
  strategy_tags: string[];
  geography: string[];
  product_structure: string[];
  market_attributes: string[];
  classification_status: string[];
  fund_type: string[];
  lifecycle_status: string[];
  investment_eligibility: string[];
};

export const emptyFundFilters = (): FundFilterValues => ({
  fund_name: "",
  fund_code: "",
  company_name: "",
  asset_class: "",
  sub_status: "",
  as_of_date: "",
  page_size: "20",
  sort: "fund_name",
  order: "asc",
  strategy: [],
  strategy_tags: [],
  geography: [],
  product_structure: [],
  market_attributes: [],
  classification_status: [],
  fund_type: [],
  lifecycle_status: [],
  investment_eligibility: [],
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
  const [values, setValues] = useState(initialValues);
  const [codeError, setCodeError] = useState("");
  const catalog = useQuery({
    queryKey: ["classification-catalog"],
    queryFn: async () => unwrapResponse(await getClassificationCatalog()),
  });
  const companies = useQuery(
    listFundManagementCompaniesQueryOptions(values.as_of_date || undefined),
  );

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (values.fund_code && !/^[0-9]{6}$/.test(values.fund_code)) {
      setCodeError("基金代码必须为 6 位半角数字");
      return;
    }
    setCodeError("");
    onSubmit({ ...values, fund_name: values.fund_name.trim() });
  };

  const set = (key: keyof FundFilterValues, value: string | null) => {
    setValues((current) => ({ ...current, [key]: value ?? "" }));
  };
  const reset = () => {
    setValues(emptyFundFilters());
    setCodeError("");
    onReset();
  };

  const categoryOptions = catalog.data?.dimensions.asset_class ?? [];
  const selectedCategory = categoryOptions.includes(values.asset_class)
    ? values.asset_class
    : null;

  return (
    <form onSubmit={submit} aria-label="基金筛选">
      <Stack gap="xs" className="fund-research-filter-form">
        <Group align="flex-end" wrap="wrap" gap="sm">
          <TextInput
            label="基金名称"
            aria-label="基金名称"
            value={values.fund_name}
            onChange={(event) => set("fund_name", event.currentTarget.value)}
            placeholder="输入基金名称"
            style={{ flex: "1 1 180px" }}
          />
          <TextInput
            label="基金代码"
            aria-label="基金代码"
            value={values.fund_code}
            onChange={(event) => {
              setCodeError("");
              set("fund_code", event.currentTarget.value);
            }}
            error={codeError || undefined}
            inputMode="numeric"
            maxLength={6}
            placeholder="6 位代码"
            style={{ flex: "0 1 140px" }}
          />
          <Select
            label="管理公司"
            aria-label="管理公司"
            data={(companies.data ?? []).map((item) => ({
              value: item.company_name,
              label: item.company_name,
            }))}
            value={values.company_name || null}
            onChange={(value) => set("company_name", value)}
            searchable
            clearable
            nothingFoundMessage="没有公司选项"
            placeholder={companies.isLoading ? "正在加载…" : "全部公司"}
            disabled={companies.isError}
            style={{ flex: "1 1 180px" }}
          />
          <Select
            label="基金类别"
            aria-label="基金类别"
            data={categoryOptions.map((value) => ({ value, label: value }))}
            value={selectedCategory}
            onChange={(value) => set("asset_class", value)}
            searchable
            clearable
            nothingFoundMessage="没有匹配类别"
            placeholder="全部类别"
            style={{ flex: "1 1 160px" }}
          />
          <Select
            label="申购状态"
            aria-label="申购状态"
            data={[{ value: "开放", label: "开放（占位）" }]}
            value={values.sub_status || null}
            onChange={(value) => set("sub_status", value)}
            clearable
            placeholder="全部状态"
            style={{ flex: "0 1 150px" }}
          />
          <TextInput
            type="date"
            label="数据截止日"
            aria-label="数据截止日"
            value={values.as_of_date}
            onChange={(event) => set("as_of_date", event.currentTarget.value)}
            style={{ flex: "0 1 160px" }}
          />
          <Button type="submit">查询基金</Button>
          <Button type="button" variant="default" onClick={reset}>
            重置
          </Button>
        </Group>
        {catalog.isError && (
          <Text role="alert" c="red" size="sm">
            基金类别加载失败，类别筛选暂不可用。
          </Text>
        )}
      </Stack>
    </form>
  );
};
