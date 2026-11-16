import { Button, Checkbox, Group, Modal, Stack, Text } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ChartLine,
  CircleCheck,
  Circle,
  FileText,
  Info,
  Layers,
  Play,
  SlidersHorizontal,
} from "lucide-react";
import { useState, type ReactNode } from "react";

import {
  getFund,
  listBenchmarkIndexes,
  listFunds,
  previewFundIngestion,
} from "../../api/generated/m17";
import type {
  FundIngestionPreview,
  FundIngestionPreviewRequest,
  FundIngestionSubmission,
} from "../../api/generated/m17.schemas";
import { ApiError, unwrapResponse } from "../../api/http";
import {
  useSubmitBenchmarkIngestion,
  useSubmitScopedIngestion,
} from "../../api/mutations";
import { ErrorState } from "../../components/ErrorState";
import styles from "./DataIngestion.module.css";
import { TargetPicker, type PickerOption } from "./TargetPicker";

export type IngestionDataset = "BASIC_INFO" | "NAV" | "BENCHMARK";

export const datasetLabels: Record<IngestionDataset, string> = {
  BASIC_INFO: "基金基本数据",
  NAV: "基金净值数据",
  BENCHMARK: "基准行情数据",
};
export const scopeLabels = {
  SINGLE: "单只基金",
  SELECTED: "多只基金",
  ALL: "全量基金",
};
export const benchmarkSourceLabels: Record<string, string> = {
  csindex: "中证指数",
  chinabond: "中债指数",
  akshare: "AKShare",
};

const typeCards: {
  value: IngestionDataset;
  icon: ReactNode;
  description: string;
}[] = [
  {
    value: "BASIC_INFO",
    icon: <FileText size={16} />,
    description:
      "基金全称、成立日期、基金经理、管理费率、托管费率及合同业绩比较基准",
  },
  {
    value: "NAV",
    icon: <ChartLine size={16} />,
    description: "单位净值、累计净值及分红、拆分历史，按已登记份额类别抓取",
  },
  {
    value: "BENCHMARK",
    icon: <Layers size={16} />,
    description: "中证、中债及港股指数的日频点位，用于基金详情页的基准对比",
  },
];

type FundPickerOption = PickerOption & { fundId?: string };

const FUND_LIMIT = 100;
const BENCHMARK_LIMIT = 200;

const today = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
};

const PreviewSummary = ({ preview }: { preview: FundIngestionPreview }) => (
  <dl className={styles.previewList} aria-label="范围预览">
    <dt>数据集</dt>
    <dd>{datasetLabels[preview.dataset as IngestionDataset]}</dd>
    <dt>范围</dt>
    <dd>{scopeLabels[preview.scope_type]}</dd>
    <dt>匹配基金</dt>
    <dd>{preview.fund_count} 只</dd>
    <dt>可抓取</dt>
    <dd>{preview.supported_fund_count} 只</dd>
    <dt>缺少来源映射</dt>
    <dd>{preview.unavailable_mapping_count} 只（保留在结果中标记为跳过）</dd>
    <dt>{preview.dataset === "NAV" ? "NAV 份额类别" : "目标基金"}</dt>
    <dd>{preview.subject_count} 项</dd>
    <dt>数据来源</dt>
    <dd>{preview.source}</dd>
    <dt>快照过期时间</dt>
    <dd>{new Date(preview.expires_at).toLocaleString("zh-CN")}</dd>
  </dl>
);

type Confirmation =
  { kind: "fund"; preview: FundIngestionPreview } | { kind: "benchmark" };

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
  const initialDataset = initialSearch.get("dataset");
  const [dataset, setDataset] = useState<IngestionDataset>(
    initialDataset === "NAV" || initialDataset === "BENCHMARK"
      ? initialDataset
      : "BASIC_INFO",
  );
  const initialFundIds = [
    ...new Set(
      [
        initialSearch.get("fund_id") ?? "",
        ...(initialSearch.get("fund_ids") ?? "").split(","),
      ]
        .map((value) => value.trim())
        .filter(Boolean),
    ),
  ].slice(0, FUND_LIMIT);
  const [funds, setFunds] = useState<FundPickerOption[]>(() =>
    initialFundIds.map((fundId) => ({
      id: fundId,
      code: fundId,
      name: "",
      fundId,
    })),
  );
  const [fullScope, setFullScope] = useState(
    initialSearch.get("scope_type") === "ALL" && canManageAll,
  );
  const [benchmarks, setBenchmarks] = useState<PickerOption[]>([]);
  const [query, setQuery] = useState("");
  const [debounced] = useDebouncedValue(query.trim(), 250);
  const [source, setSource] = useState("ALL");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState(today);
  const [feedback, setFeedback] = useState<string>();
  const [confirmation, setConfirmation] = useState<Confirmation>();
  const isBenchmark = dataset === "BENCHMARK";

  // 预选基金只有代码，补齐名称以便在标签中识别。
  useQuery({
    queryKey: ["ingestion-preselected-funds", initialFundIds],
    enabled: initialFundIds.length > 0,
    staleTime: Infinity,
    queryFn: async () => {
      const resolved = await Promise.all(
        initialFundIds.map(async (fundId) => {
          try {
            return unwrapResponse(await getFund(fundId));
          } catch {
            return undefined;
          }
        }),
      );
      setFunds((current) =>
        current.map((item) => {
          const fund = resolved.find(
            (value) => value?.fund_id === (item.fundId ?? item.id),
          );
          return fund ? { ...item, name: fund.fund_name } : item;
        }),
      );
      return resolved;
    },
  });

  const fundSearch = useQuery({
    queryKey: ["ingestion-fund-search", debounced],
    enabled: !isBenchmark && !fullScope,
    queryFn: async () => {
      // 六位行情代码不同于平台基金 ID，必须通过列表的代码筛选解析。
      const isFundCode = /^[0-9]{6}$/.test(debounced);
      const response = await listFunds({
        fund_code: isFundCode ? debounced : undefined,
        fund_name: isFundCode ? undefined : debounced || undefined,
        sort: "fund_code",
        order: "asc",
        page: 1,
        page_size: 20,
      });
      return {
        items: unwrapResponse(response),
        total: response.data.meta.pagination?.total_items,
      };
    },
  });
  const benchmarkSearch = useQuery({
    queryKey: ["ingestion-benchmark-search", debounced, source],
    enabled: isBenchmark,
    queryFn: async () =>
      unwrapResponse(
        await listBenchmarkIndexes({
          q: debounced || undefined,
          source: source === "ALL" ? undefined : (source as never),
          page: 1,
          page_size: BENCHMARK_LIMIT,
        }),
      ),
  });

  const preview = useMutation({
    mutationFn: async (request: FundIngestionPreviewRequest) =>
      unwrapResponse(await previewFundIngestion(request)),
  });
  const submitFunds = useSubmitScopedIngestion();
  const submitBenchmarks = useSubmitBenchmarkIngestion();
  const pending =
    preview.isPending || submitFunds.isPending || submitBenchmarks.isPending;

  const changeDataset = (next: IngestionDataset) => {
    if (next === dataset) return;
    // 基金与基准是不同的标的域：已选项分别保留，切换时只清空检索词与来源筛选。
    if ((next === "BENCHMARK") !== isBenchmark) {
      setQuery("");
      setSource("ALL");
    }
    setDataset(next);
    setFeedback(undefined);
    onPreview?.(undefined);
  };

  const fundOptions: FundPickerOption[] = (fundSearch.data?.items ?? []).map(
    (fund) => ({
      // 勾选按六位代码区分份额，提交所需的产品 ID 单独保留。
      id: fund.fund_code ?? fund.fund_id,
      fundId: fund.fund_id,
      code: fund.fund_code ?? fund.fund_id,
      name: fund.fund_name,
    }),
  );
  const benchmarkPage = benchmarkSearch.data;
  const benchmarkOptions: PickerOption[] = (benchmarkPage?.items ?? []).map(
    (item) => ({
      id: item.benchmark_index_id,
      code: item.provider_code,
      name: item.display_name,
      // 来源列可空：未登记来源显示“来源未知”，提交时后端会把这类指数标记为跳过。
      tags: [
        item.source
          ? (benchmarkSourceLabels[item.source] ?? item.source)
          : "来源未知",
      ],
      meta: item.latest_value_date
        ? `已入库至 ${item.latest_value_date}`
        : "尚未入库行情",
    }),
  );
  const counts = (benchmarkPage?.source_counts ?? {}) as Record<string, number>;
  const allCount = Object.values(counts).reduce((sum, value) => sum + value, 0);

  const selectedCount = isBenchmark ? benchmarks.length : funds.length;
  const invalidDates =
    isBenchmark && Boolean(startDate && endDate && startDate > endDate);

  const start = () => {
    setFeedback(undefined);
    if (isBenchmark) {
      if (!benchmarks.length)
        return setFeedback("请至少选择一个基准指数后再启动抓取。");
      if (!endDate) return setFeedback("请选择抓取结束日期。");
      if (invalidDates) return setFeedback("开始日期不能晚于结束日期。");
      setConfirmation({ kind: "benchmark" });
      return;
    }
    if (!fullScope && !funds.length)
      return setFeedback("请至少选择一只基金后再启动抓取。");
    // 抓取接口仍按产品接收范围，同产品的多个代码在提交时去重。
    const fundIds = [...new Set(funds.map((item) => item.fundId ?? item.id))];
    const request: FundIngestionPreviewRequest = {
      dataset,
      scope: fullScope
        ? { type: "ALL" }
        : fundIds.length === 1
          ? { type: "SINGLE", fund_id: fundIds[0] }
          : { type: "SELECTED", fund_ids: fundIds },
    };
    preview.mutate(request, {
      onSuccess: (value) => {
        onPreview?.(value);
        setConfirmation({ kind: "fund", preview: value });
      },
    });
  };

  const done = (submission: FundIngestionSubmission) => {
    setConfirmation(undefined);
    setFeedback(undefined);
    onSubmitted(submission);
  };
  const confirm = () => {
    if (confirmation?.kind === "fund") {
      if (Date.parse(confirmation.preview.expires_at) <= Date.now()) {
        setConfirmation(undefined);
        setFeedback("预览快照已过期，请重新提交。");
        return;
      }
      submitFunds.mutate(confirmation.preview.preview_id, {
        onSuccess: done,
        onError: (error) => {
          if (error instanceof ApiError && error.status === 409) {
            setConfirmation(undefined);
            setFeedback("预览已过期或范围发生变化，请重新提交。");
          }
        },
      });
    } else if (confirmation?.kind === "benchmark") {
      submitBenchmarks.mutate(
        {
          benchmark_index_ids: benchmarks.map((item) => item.id),
          start_date: startDate || null,
          end_date: endDate,
        },
        { onSuccess: done },
      );
    }
  };

  return (
    <section className={styles.card} aria-labelledby="ingestion-scope-title">
      <div className={styles.cardHeader}>
        <h2 className={styles.cardTitle} id="ingestion-scope-title">
          <SlidersHorizontal size={16} />
          新建数据抓取任务
        </h2>
        <span className={styles.cardHint}>
          配置抓取类型与目标标的，支持模糊检索与批量选择
        </span>
      </div>
      <div className={styles.cardBody}>
        <div>
          <span className={styles.fieldLabel} id="ingestion-type-label">
            选择抓取数据类型 <span className={styles.required}>*</span>
          </span>
          <div
            className={styles.typeGrid}
            role="radiogroup"
            aria-labelledby="ingestion-type-label"
          >
            {typeCards.map((card) => {
              const checked = card.value === dataset;
              return (
                <button
                  key={card.value}
                  type="button"
                  role="radio"
                  aria-checked={checked}
                  className={styles.typeCard}
                  disabled={pending}
                  onClick={() => changeDataset(card.value)}
                >
                  <span className={styles.typeIcon}>{card.icon}</span>
                  <span className={styles.typeText}>
                    <span className={styles.typeName}>
                      {datasetLabels[card.value]}
                      {checked ? (
                        <CircleCheck size={15} aria-hidden="true" />
                      ) : (
                        <Circle size={15} aria-hidden="true" />
                      )}
                    </span>
                    <span className={styles.typeDescription}>
                      {card.description}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <div className={styles.configRow}>
          <div>
            {isBenchmark ? (
              <TargetPicker
                label="选择目标基准指数"
                placeholder="输入基准代码或名称模糊查询（如：000300 / 中证 / 中债 / 恒生）…"
                query={query}
                onQueryChange={setQuery}
                options={benchmarkOptions}
                selected={benchmarks}
                onChange={setBenchmarks}
                loading={benchmarkSearch.isFetching}
                error={
                  benchmarkSearch.isError
                    ? "基准列表读取失败，请稍后重试。"
                    : undefined
                }
                emptyText={`未找到匹配“${query}”的基准记录`}
                maxSelected={BENCHMARK_LIMIT}
                disabled={pending}
                sources={[
                  {
                    value: "ALL",
                    label: "全部基准",
                    count: benchmarkPage ? allCount : undefined,
                  },
                  ...Object.entries(benchmarkSourceLabels).map(
                    ([value, label]) => ({
                      value,
                      label,
                      count: benchmarkPage ? (counts[value] ?? 0) : undefined,
                    }),
                  ),
                ]}
                source={source}
                onSourceChange={setSource}
                footer={
                  <>
                    <span>
                      匹配 {benchmarkPage?.total ?? 0} 条
                      {benchmarkPage &&
                      benchmarkPage.total > benchmarkOptions.length
                        ? `，显示前 ${benchmarkOptions.length} 条`
                        : ""}
                    </span>
                    <span>单次最多 {BENCHMARK_LIMIT} 个</span>
                  </>
                }
              />
            ) : (
              <>
                <TargetPicker
                  label="选择目标基金"
                  placeholder="输入基金代码或名称模糊查询（如：000001 / 华夏）…"
                  query={query}
                  onQueryChange={setQuery}
                  options={fundOptions}
                  selected={funds}
                  onChange={setFunds}
                  loading={fundSearch.isFetching}
                  error={
                    fundSearch.isError
                      ? "基金检索失败，请稍后重试。"
                      : undefined
                  }
                  total={fundSearch.data?.total}
                  emptyText={`未找到匹配“${query}”的基金记录`}
                  maxSelected={FUND_LIMIT}
                  disabled={pending || fullScope}
                  footer={
                    <>
                      <span>
                        按名称检索时显示前 20 条，输入 6 位代码可精确定位
                      </span>
                      <span>单次最多 {FUND_LIMIT} 只</span>
                    </>
                  }
                />
                {canManageAll && (
                  <Checkbox
                    className={styles.fullScope}
                    size="xs"
                    label="改为抓取平台基金库全量（提交时生成快照，后续新增基金不会混入本次任务）"
                    checked={fullScope}
                    disabled={pending}
                    onChange={(event) =>
                      setFullScope(event.currentTarget.checked)
                    }
                  />
                )}
              </>
            )}
          </div>
          <div>
            <span className={styles.fieldLabel} id="ingestion-range-label">
              抓取时间区间
            </span>
            <div
              className={styles.dateRange}
              role="group"
              aria-labelledby="ingestion-range-label"
            >
              <input
                type="date"
                aria-label="开始日期"
                value={isBenchmark ? startDate : ""}
                max={endDate || undefined}
                disabled={!isBenchmark || pending}
                onChange={(event) => setStartDate(event.currentTarget.value)}
              />
              <span>至</span>
              <input
                type="date"
                aria-label="结束日期"
                value={isBenchmark ? endDate : ""}
                disabled={!isBenchmark || pending}
                onChange={(event) => setEndDate(event.currentTarget.value)}
              />
            </div>
            <p className={styles.fieldNote}>
              {isBenchmark
                ? "开始日期留空表示抓取数据源可提供的全部历史；同一日期的值有变化时写入新版本，未变化则不重复写入。"
                : dataset === "NAV"
                  ? "基金净值按已登记份额类别抓取数据源可提供的完整历史（含分红与拆分），不按区间截取。"
                  : "基金基本数据抓取当前可获得的最新快照，不涉及时间区间。"}
            </p>
          </div>
        </div>

        <div className={styles.footer}>
          <div className={styles.summary}>
            <Info size={14} aria-hidden="true" />
            <span role="status">
              {!isBenchmark && fullScope ? (
                "当前已选：平台基金库全量"
              ) : (
                <>
                  当前已选：<strong>{selectedCount}</strong>{" "}
                  {isBenchmark ? "个基准指数" : "只基金"}
                </>
              )}
            </span>
          </div>
          <div className={styles.footerActions}>
            {feedback && (
              <span className={styles.feedback} role="alert">
                {feedback}
              </span>
            )}
            <Button
              size="xs"
              leftSection={<Play size={14} />}
              loading={preview.isPending}
              disabled={pending && !preview.isPending}
              onClick={start}
            >
              立即执行抓取任务
            </Button>
          </div>
        </div>
        {preview.isError && (
          <ErrorState
            error={preview.error}
            onRetry={start}
            retryLabel="重新预览"
          />
        )}
        {submitFunds.isError && <ErrorState error={submitFunds.error} />}
        {submitBenchmarks.isError && (
          <ErrorState error={submitBenchmarks.error} />
        )}
      </div>

      <Modal
        opened={Boolean(confirmation)}
        onClose={() => {
          if (!pending) setConfirmation(undefined);
        }}
        title="确认抓取任务"
        centered
        closeOnEscape={!pending}
        closeOnClickOutside={!pending}
      >
        <Stack>
          {confirmation?.kind === "fund" && (
            <>
              <PreviewSummary preview={confirmation.preview} />
              <Text size="sm">
                {fullScope
                  ? "平台基金库全量快照。"
                  : `明确选择的 ${funds.length} 只基金。`}
                变化的数据写入新修订。
              </Text>
            </>
          )}
          {confirmation?.kind === "benchmark" && (
            <dl className={styles.previewList} aria-label="基准抓取范围">
              <dt>数据集</dt>
              <dd>{datasetLabels.BENCHMARK}</dd>
              <dt>基准指数</dt>
              <dd>
                {benchmarks.length} 个：
                {benchmarks
                  .slice(0, 5)
                  .map((item) => item.name)
                  .join("、")}
                {benchmarks.length > 5 ? ` 等` : ""}
              </dd>
              <dt>时间区间</dt>
              <dd>
                {startDate || "全部可得历史"} 至 {endDate}
              </dd>
            </dl>
          )}
          <Text size="sm" c="dimmed">
            提交人：{actor}
          </Text>
          <Group justify="flex-end">
            <Button
              variant="default"
              disabled={pending}
              onClick={() => setConfirmation(undefined)}
            >
              返回修改
            </Button>
            <Button
              loading={submitFunds.isPending || submitBenchmarks.isPending}
              onClick={confirm}
            >
              确认提交
            </Button>
          </Group>
        </Stack>
      </Modal>
    </section>
  );
};
