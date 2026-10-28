import {
  Button,
  Checkbox,
  Group,
  Modal,
  NativeSelect,
  Stack,
  Text,
  TextInput,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
  getFund,
  listFunds,
  previewFundIngestion,
} from "../../api/generated/m17";
import type {
  FundIngestionFilters,
  FundIngestionPreview,
  FundIngestionPreviewRequest,
  FundIngestionSubmission,
} from "../../api/generated/m17.schemas";
import { ApiError, unwrapResponse } from "../../api/http";
import { useSubmitScopedIngestion } from "../../api/mutations";
import { ErrorState } from "../../components/ErrorState";

export const datasetLabels = { BASIC_INFO: "基本信息", NAV: "NAV 与分红/拆分" };
export const scopeLabels = {
  SINGLE: "单只基金",
  SELECTED: "多只基金",
  ALL: "全量基金",
};
const filterFields: {
  key: keyof FundIngestionFilters;
  label: string;
  list?: boolean;
}[] = [
  { key: "fund_name", label: "基金名称" },
  { key: "fund_type", label: "基金类型", list: true },
  { key: "lifecycle_status", label: "生命周期", list: true },
  { key: "investment_eligibility", label: "投资资格", list: true },
  { key: "asset_class", label: "资产类别" },
  { key: "strategy", label: "策略" },
  { key: "geography", label: "地域" },
  { key: "product_structure", label: "产品结构" },
  { key: "market_attributes", label: "市场属性" },
  { key: "classification_status", label: "分类状态" },
];

const PreviewSummary = ({ preview }: { preview: FundIngestionPreview }) => (
  <Stack gap="xs" aria-label="范围预览">
    <Text>
      数据集：{datasetLabels[preview.dataset]} · 范围：
      {scopeLabels[preview.scope_type]}
    </Text>
    <Text>
      匹配基金：{preview.fund_count} 只 · 可抓取：{preview.supported_fund_count}{" "}
      只
    </Text>
    <Text>缺少来源映射：{preview.unavailable_mapping_count} 只</Text>
    <Text>
      {preview.dataset === "NAV" ? "NAV 份额类别" : "基本信息目标基金"}：
      {preview.subject_count} 项
    </Text>
    <Text>来源：{preview.source}</Text>
    <Text>
      快照过期时间：{new Date(preview.expires_at).toLocaleString("zh-CN")}
    </Text>
  </Stack>
);

export const IngestionScopeForm = ({
  initialSearch,
  canManageAll,
  actor,
  onSubmitted,
  onPreview,
}: {
  initialSearch: URLSearchParams;
  canManageAll: boolean;
  actor: string;
  onSubmitted: (submission: FundIngestionSubmission) => void;
  onPreview?: (preview: FundIngestionPreview | undefined) => void;
}) => {
  const [dataset, setDataset] = useState<
    FundIngestionPreviewRequest["dataset"]
  >(initialSearch.get("dataset") === "NAV" ? "NAV" : "BASIC_INFO");
  const [scopeType, setScopeType] = useState<
    FundIngestionPreviewRequest["scope"]["type"]
  >(
    initialSearch.get("scope_type") === "ALL"
      ? "ALL"
      : initialSearch.get("scope_type") === "SELECTED"
        ? "SELECTED"
        : "SINGLE",
  );
  const [singleId, setSingleId] = useState(initialSearch.get("fund_id") ?? "");
  const [selected, setSelected] = useState(() => [
    ...new Set(
      (initialSearch.get("fund_ids") ?? "")
        .split(",")
        .map((id) => id.trim())
        .filter(Boolean),
    ),
  ]);
  const [searchInput, setSearchInput] = useState("");
  const [fundSearch, setFundSearch] = useState("");
  const [page, setPage] = useState(1);
  const [searchStarted, setSearchStarted] = useState(false);
  const [filtered, setFiltered] = useState(false);
  const [filters, setFilters] = useState<FundIngestionFilters>({});
  const [revision, setRevision] = useState(0);
  const [invalidPreview, setInvalidPreview] = useState<string>();
  const [confirmation, setConfirmation] = useState<FundIngestionPreview>();
  const [now, setNow] = useState(Date.now());
  const submit = useSubmitScopedIngestion();
  const valid =
    scopeType === "SINGLE"
      ? Boolean(singleId)
      : scopeType === "SELECTED"
        ? selected.length >= 2 && selected.length <= 100
        : canManageAll;
  const request: FundIngestionPreviewRequest = {
    dataset,
    scope:
      scopeType === "SINGLE"
        ? { type: "SINGLE", fund_id: singleId }
        : scopeType === "SELECTED"
          ? { type: "SELECTED", fund_ids: selected }
          : filtered
            ? { type: "ALL", filters }
            : { type: "ALL" },
  };
  const preview = useQuery({
    queryKey: ["ingestion-preview", request, revision],
    queryFn: async () => unwrapResponse(await previewFundIngestion(request)),
    enabled: valid,
    retry: false,
    refetchOnWindowFocus: false,
  });
  const funds = useQuery({
    queryKey: ["ingestion-fund-search", fundSearch, page],
    enabled: searchStarted && scopeType !== "ALL",
    queryFn: async () => {
      if (/^\d+$/.test(fundSearch)) {
        try {
          const fund = unwrapResponse(await getFund(fundSearch));
          return {
            items: [fund],
            pagination: {
              page: 1,
              page_size: 20,
              total_items: 1,
              total_pages: 1,
            },
          };
        } catch (error) {
          if (error instanceof ApiError && error.status === 404)
            return {
              items: [],
              pagination: {
                page: 1,
                page_size: 20,
                total_items: 0,
                total_pages: 0,
              },
            };
          throw error;
        }
      }
      const response = await listFunds({
        fund_name: fundSearch || undefined,
        page,
        page_size: 20,
      });
      return {
        items: unwrapResponse(response),
        pagination: response.data.meta.pagination,
      };
    },
  });
  const currentPreview =
    valid && preview.isSuccess && preview.data.preview_id !== invalidPreview
      ? preview.data
      : undefined;
  useEffect(() => {
    onPreview?.(currentPreview);
  }, [currentPreview, onPreview]);
  const expired = currentPreview
    ? Date.parse(currentPreview.expires_at) <= now
    : false;
  useEffect(() => {
    if (!currentPreview) return;
    const timeout = window.setTimeout(
      () => setNow(Date.now()),
      Math.max(
        1,
        Math.min(
          Date.parse(currentPreview.expires_at) - Date.now() + 1,
          2147483647,
        ),
      ),
    );
    return () => window.clearTimeout(timeout);
  }, [currentPreview]);
  const start = (value: FundIngestionPreview) => {
    if (Date.parse(value.expires_at) <= Date.now()) {
      setNow(Date.now());
      setConfirmation(undefined);
      return;
    }
    submit.mutate(value.preview_id, {
      onSuccess: onSubmitted,
      onError: (error) => {
        if (error instanceof ApiError && error.status === 409) {
          setInvalidPreview(value.preview_id);
          setConfirmation(undefined);
        }
      },
    });
  };
  const refresh = () => {
    setConfirmation(undefined);
    submit.reset();
    setRevision((value) => value + 1);
  };
  return (
    <section aria-labelledby="ingestion-scope-title">
      <h2 id="ingestion-scope-title">新建抓取任务</h2>
      <Stack gap="md">
        <fieldset
          disabled={submit.isPending}
          style={{ border: 0, padding: 0, margin: 0 }}
        >
          <Stack>
            <NativeSelect
              label="数据集"
              value={dataset}
              onChange={(event) =>
                setDataset(event.currentTarget.value as typeof dataset)
              }
              data={Object.entries(datasetLabels).map(([value, label]) => ({
                value,
                label,
              }))}
            />
            <NativeSelect
              label="抓取范围"
              value={scopeType}
              onChange={(event) => {
                setScopeType(event.currentTarget.value as typeof scopeType);
                setConfirmation(undefined);
              }}
              data={Object.entries(scopeLabels).map(([value, label]) => ({
                value,
                label,
                disabled: value === "ALL" && !canManageAll,
              }))}
            />
            {dataset === "NAV" && (
              <Text size="sm">
                按已登记份额类别抓取数据源可提供的完整历史，包含分红与拆分。
              </Text>
            )}
            {scopeType === "ALL" ? (
              <>
                <Text>
                  全量范围是预览时的平台基金库快照，后续新增基金不会混入本次任务。
                </Text>
                {!canManageAll && (
                  <Text role="alert">当前身份没有全量抓取权限。</Text>
                )}
                {canManageAll && (
                  <>
                    <NativeSelect
                      label="全量范围条件"
                      value={filtered ? "FILTERED" : "LIBRARY"}
                      onChange={(event) =>
                        setFiltered(event.currentTarget.value === "FILTERED")
                      }
                      data={[
                        { value: "LIBRARY", label: "平台基金库全量" },
                        { value: "FILTERED", label: "当前筛选结果" },
                      ]}
                    />
                    {filtered && (
                      <>
                        <Text size="sm">
                          使用基金研究已有筛选值，多值以逗号分隔；空条件匹配整个基金库。
                        </Text>
                        {filterFields.map(({ key, label, list }) => (
                          <TextInput
                            key={key}
                            label={`范围筛选 · ${label}`}
                            value={
                              Array.isArray(filters[key])
                                ? (filters[key] as string[]).join(",")
                                : (filters[key] ?? "")
                            }
                            onChange={(event) => {
                              const value = event.currentTarget.value;
                              setFilters((current) => ({
                                ...current,
                                [key]: value
                                  ? list
                                    ? value
                                        .split(",")
                                        .map((part) => part.trim())
                                        .filter(Boolean)
                                    : value
                                  : undefined,
                              }));
                            }}
                          />
                        ))}
                      </>
                    )}
                  </>
                )}
              </>
            ) : (
              <>
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    setFundSearch(searchInput.trim());
                    setPage(1);
                    setSearchStarted(true);
                  }}
                >
                  <Group align="end">
                    <TextInput
                      label="搜索基金名称或代码"
                      value={searchInput}
                      onChange={(event) =>
                        setSearchInput(event.currentTarget.value)
                      }
                    />
                    <Button type="submit" variant="default">
                      搜索基金
                    </Button>
                  </Group>
                </form>
                {scopeType === "SINGLE" && (
                  <Text>已选基金：{singleId || "尚未选择"}</Text>
                )}
                {scopeType === "SELECTED" && (
                  <>
                    <Text>已选 {selected.length} / 100 只基金</Text>
                    <Group>
                      {selected.map((id) => (
                        <Button
                          key={id}
                          variant="light"
                          size="compact-sm"
                          aria-label={`移除基金 ${id}`}
                          onClick={() =>
                            setSelected((current) =>
                              current.filter((item) => item !== id),
                            )
                          }
                        >
                          {id} ×
                        </Button>
                      ))}
                    </Group>
                    {!valid && (
                      <Text role="status">
                        多只范围需要选择 2–100 只不同基金。
                      </Text>
                    )}
                  </>
                )}
                {funds.isFetching && <Text role="status">正在搜索基金…</Text>}
                {funds.isError && (
                  <ErrorState
                    error={funds.error}
                    onRetry={() => void funds.refetch()}
                  />
                )}
                {funds.data?.items.length === 0 && (
                  <Text>没有符合条件的基金。</Text>
                )}
                {funds.data && (
                  <>
                    {funds.data.items.map((fund) => (
                      <Checkbox
                        key={fund.fund_id}
                        label={`${fund.fund_name}（${fund.fund_id}）`}
                        aria-label={`选择 ${fund.fund_name}（${fund.fund_id}）`}
                        checked={
                          scopeType === "SINGLE"
                            ? singleId === fund.fund_id
                            : selected.includes(fund.fund_id)
                        }
                        disabled={
                          scopeType === "SELECTED" &&
                          selected.length >= 100 &&
                          !selected.includes(fund.fund_id)
                        }
                        onChange={(event) => {
                          if (scopeType === "SINGLE")
                            setSingleId(
                              event.currentTarget.checked ? fund.fund_id : "",
                            );
                          else {
                            const checked = event.currentTarget.checked;
                            setSelected((current) =>
                              checked
                                ? [
                                    ...new Set([...current, fund.fund_id]),
                                  ].slice(0, 100)
                                : current.filter((id) => id !== fund.fund_id),
                            );
                          }
                        }}
                      />
                    ))}
                    <Group>
                      <Button
                        variant="default"
                        disabled={page <= 1 || funds.isFetching}
                        onClick={() => setPage((value) => value - 1)}
                      >
                        搜索上一页
                      </Button>
                      <Text>
                        第 {funds.data.pagination?.page ?? page} 页 · 共{" "}
                        {funds.data.pagination?.total_items ?? "—"} 只
                      </Text>
                      <Button
                        variant="default"
                        disabled={
                          !funds.data.pagination ||
                          page >= funds.data.pagination.total_pages ||
                          funds.isFetching
                        }
                        onClick={() => setPage((value) => value + 1)}
                      >
                        搜索下一页
                      </Button>
                    </Group>
                  </>
                )}
              </>
            )}
          </Stack>
        </fieldset>
        {valid && preview.isFetching && (
          <Text role="status">正在计算范围预览…</Text>
        )}
        {valid && preview.isError && (
          <ErrorState
            error={preview.error}
            onRetry={refresh}
            retryLabel="重新预览"
          />
        )}
        {currentPreview && <PreviewSummary preview={currentPreview} />}
        {expired && <Text role="alert">快照已过期，请重新预览。</Text>}
        {invalidPreview && preview.data?.preview_id === invalidPreview && (
          <Text role="alert">预览已过期或范围发生变化，请重新预览后提交。</Text>
        )}
        {submit.isError && <ErrorState error={submit.error} />}
        {valid && (
          <Group>
            <Button
              variant="default"
              onClick={refresh}
              disabled={preview.isFetching || submit.isPending}
            >
              重新预览
            </Button>
            {currentPreview && !expired && !preview.isFetching && (
              <Button
                loading={submit.isPending}
                onClick={() =>
                  scopeType === "SINGLE"
                    ? start(currentPreview)
                    : setConfirmation(currentPreview)
                }
              >
                提交抓取
              </Button>
            )}
          </Group>
        )}
      </Stack>
      <Modal
        opened={Boolean(confirmation)}
        onClose={() => {
          if (!submit.isPending) setConfirmation(undefined);
        }}
        title="确认抓取范围"
        centered
        closeOnEscape={!submit.isPending}
        closeOnClickOutside={!submit.isPending}
      >
        {confirmation && (
          <Stack>
            <PreviewSummary preview={confirmation} />
            <Text>
              {scopeType === "ALL"
                ? filtered
                  ? "平台基金库当前筛选结果快照"
                  : "平台基金库全量快照"
                : `明确选择的 ${selected.length} 只基金`}
            </Text>
            <Text>
              不可抓取 {confirmation.unavailable_mapping_count}{" "}
              只；缺少来源映射的项会保留在结果中。
            </Text>
            <Text>
              {dataset === "NAV"
                ? "按已登记份额类别补齐数据源可提供的完整历史。"
                : "抓取当前可获得的基金基本信息。"}
              变化的数据写入新修订。
            </Text>
            <Text>提交人：{actor}</Text>
            <Group justify="flex-end">
              <Button
                variant="default"
                disabled={submit.isPending}
                onClick={() => setConfirmation(undefined)}
              >
                返回修改
              </Button>
              <Button
                loading={submit.isPending}
                onClick={() => start(confirmation)}
              >
                确认提交
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </section>
  );
};
