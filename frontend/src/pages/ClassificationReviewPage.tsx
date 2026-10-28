import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  getClassificationCatalog,
  getClassificationReview,
  getSession,
  listClassificationReviews,
  reviewClassification,
} from "../api/generated/m17";
import type {
  Evidence,
  ClassificationSnapshot,
  ReviewDecisionAction,
  ReviewSubmission,
  StrategyTagDecisionAction,
} from "../api/generated/m17.schemas";
import { ApiError, unwrapResponse } from "../api/http";
import { ErrorState } from "../components/ErrorState";
import {
  ClassificationView,
  activeDimensions,
  dimensionLabels,
} from "../features/classifications/ClassificationView";

const changedStrategyTags = (
  incoming?: ClassificationSnapshot | null,
  baseline?: ClassificationSnapshot | null,
) =>
  Object.keys(incoming?.strategy_tag_results ?? {}).filter(
    (tag) =>
      JSON.stringify(incoming?.strategy_tag_results?.[tag]) !==
      JSON.stringify(baseline?.strategy_tag_results?.[tag]),
  );

export const ClassificationReviewPage = () => {
  const [search, setSearch] = useSearchParams();
  const page = Number(search.get("page") || 1);
  const caseId = Number(search.get("case") || 0);
  const client = useQueryClient();
  const session = useQuery({
    queryKey: ["api", "session"],
    queryFn: async () => unwrapResponse(await getSession()),
  });
  const queue = useQuery({
    queryKey: ["classification-reviews", page],
    queryFn: async () => {
      const response = await listClassificationReviews({
        page,
        page_size: 20,
        status: "PENDING",
      });
      return {
        items: unwrapResponse(response),
        pagination: response.data.meta.pagination,
      };
    },
  });
  const detail = useQuery({
    queryKey: ["classification-review", caseId],
    enabled: caseId > 0,
    queryFn: async () => unwrapResponse(await getClassificationReview(caseId)),
  });
  const catalog = useQuery({
    queryKey: ["classification-catalog"],
    queryFn: async () => unwrapResponse(await getClassificationCatalog()),
  });
  const [dimension, setDimension] = useState<string>(activeDimensions[0]);
  const [action, setAction] = useState<ReviewDecisionAction>("CONFIRM");
  const [values, setValues] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [rawValue, setRawValue] = useState("");
  const [locator, setLocator] = useState("");
  const [activeValues, setActiveValues] = useState<Record<string, string>>({});
  const [tagActions, setTagActions] = useState<
    Record<string, StrategyTagDecisionAction | "">
  >({});
  const [notice, setNotice] = useState("");
  const mutation = useMutation({
    mutationFn: async (body: ReviewSubmission) =>
      unwrapResponse(await reviewClassification(caseId, body)),
    onSuccess: async () => {
      setNotice("复核已保存，请选择下一条待复核记录。");
      setReason("");
      setRawValue("");
      await client.invalidateQueries({ queryKey: ["classification-reviews"] });
      await client.invalidateQueries({
        queryKey: ["classification-review", caseId],
      });
      await client.invalidateQueries({ queryKey: ["fund-research"] });
      await client.invalidateQueries({ queryKey: ["fund-detail"] });
      await client.invalidateQueries({ queryKey: ["classification-history"] });
    },
    onError: async (error) => {
      if (error instanceof ApiError && error.status === 409) {
        setNotice("基线已变化，已重新加载。请重新比较证据后提交。");
        setValues([]);
        setActiveValues({});
        setTagActions({});
        setReason("");
        setRawValue("");
        await detail.refetch();
        await queue.refetch();
      }
    },
  });
  const navigate = (key: string, value: number) => {
    const next = new URLSearchParams(search);
    next.set(key, String(value));
    setSearch(next);
    setNotice("");
    setValues([]);
    setActiveValues({});
    setTagActions({});
    setReason("");
    setRawValue("");
    mutation.reset();
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!detail.data || !reason.trim() || !rawValue.trim() || !locator.trim())
      return;
    const evidence: Evidence = {
      source: "OFFICIAL",
      confidence: "OFFICIAL_DOCUMENT",
      rule_id: "MANUAL_REVIEW",
      classified_at: new Date().toISOString(),
      raw_field: dimension,
      raw_value: rawValue.trim(),
      locator: locator.trim(),
    };
    const incomingSnapshot = detail.data.incoming;
    const isCurrentReview = incomingSnapshot?.scheme === "FIP_CLASSIFICATION";
    if (isCurrentReview) {
      const scope = detail.data.active_scope.filter((name) =>
        activeDimensions.includes(name as (typeof activeDimensions)[number]),
      );
      const decisions = Object.fromEntries(
        scope.map((name) => [
          name,
          {
            action: "CONFIRM" as ReviewDecisionAction,
            value: activeValues[name] || "UNKNOWN",
            evidence: [{ ...evidence, raw_field: name }],
          },
        ]),
      );
      const tag_decisions = Object.fromEntries(
        Object.entries(tagActions)
          .filter((entry): entry is [string, StrategyTagDecisionAction] =>
            Boolean(entry[1]),
          )
          .map(([tag, tagAction]) => [
            tag,
            {
              action: tagAction,
              evidence: [{ ...evidence, raw_field: "strategy" }],
            },
          ]),
      );
      const requiredTags = changedStrategyTags(
        incomingSnapshot,
        detail.data.baseline,
      );
      if (
        scope.some((name) => !activeValues[name]) ||
        requiredTags.some((tag) => !tagActions[tag])
      )
        return;
      mutation.mutate({
        expected_revision: detail.data.expected_revision,
        reason: reason.trim(),
        decisions,
        tag_decisions,
      });
      return;
    }
    mutation.mutate({
      expected_revision: detail.data.expected_revision,
      reason: reason.trim(),
      decisions: {
        [dimension]: {
          action,
          value: values[0] || "UNKNOWN",
          evidence: [evidence],
        },
      },
    });
  };
  const incoming = detail.data?.incoming;
  const baseline = detail.data?.baseline;
  const isCurrentReview = incoming?.scheme === "FIP_CLASSIFICATION";
  const reviewScope = isCurrentReview
    ? (detail.data?.active_scope.filter((name) =>
        activeDimensions.includes(name as (typeof activeDimensions)[number]),
      ) ?? [])
    : [];
  const requiredTags = isCurrentReview
    ? changedStrategyTags(incoming, baseline)
    : [];
  const activeLegacyScope = (detail.data?.active_scope ?? []).filter((name) =>
    activeDimensions.includes(name as (typeof activeDimensions)[number]),
  );
  const isReadOnlyHistoricalCase =
    detail.data?.evaluation_state === "PAUSED" ||
    ((detail.data?.historical_scope?.length ?? 0) > 0 &&
      activeLegacyScope.length === 0);
  return (
    <section>
      <h1>分类待复核</h1>
      {queue.isError && <ErrorState error={queue.error} />}
      <ul>
        {queue.data?.items.map((item) => (
          <li key={item.case_id}>
            <button onClick={() => navigate("case", item.case_id)}>
              基金 {item.fund_id} · {item.issue_type} · 修订{" "}
              {item.expected_revision}
            </button>
          </li>
        ))}
      </ul>
      <nav aria-label="复核分页">
        <button disabled={page <= 1} onClick={() => navigate("page", page - 1)}>
          上一页
        </button>
        <span>第 {page} 页</span>
        <button
          disabled={
            !queue.data?.pagination || page >= queue.data.pagination.total_pages
          }
          onClick={() => navigate("page", page + 1)}
        >
          下一页
        </button>
      </nav>
      {detail.isError && <ErrorState error={detail.error} />}{" "}
      {detail.data && (
        <article>
          <h2>
            复核 #{detail.data.case_id} · 基线 {detail.data.expected_revision}
          </h2>
          <p>{detail.data.status}</p>
          {(detail.data.active_scope?.length > 0 ||
            detail.data.historical_scope?.length > 0) && (
            <p>
              当前复核范围：
              {(detail.data.active_scope ?? [])
                .map((name) => dimensionLabels[name] ?? name)
                .join("、") || "无"}
              。只读历史维度：
              {(detail.data.historical_scope ?? [])
                .map((name) => dimensionLabels[name] ?? name)
                .join("、") || "无"}
              {detail.data.evaluation_state
                ? ` · 评估状态 ${detail.data.evaluation_state}`
                : ""}
            </p>
          )}
          <h3>维度证据比较</h3>
          <h4>当前基线</h4>
          <ClassificationView classification={detail.data.baseline} evidence />
          {detail.data.incoming && (
            <>
              <h4>新到资料</h4>
              <ClassificationView
                classification={detail.data.incoming}
                evidence
              />
            </>
          )}
          <details>
            <summary>复核上下文</summary>
            <pre>{JSON.stringify(detail.data.details, null, 2)}</pre>
          </details>
          {session.data?.capabilities.can_review_classifications === true &&
          detail.data.status === "PENDING" ? (
            isReadOnlyHistoricalCase && !isCurrentReview ? (
              <p>
                此案件只涉及暂停维度的历史分类，为保护历史记录，当前不接受分类决定。
              </p>
            ) : (
              <form aria-label="分类复核" onSubmit={submit}>
                {isCurrentReview ? (
                  <>
                    <fieldset>
                      <legend>本次需要确认的活跃维度</legend>
                      {reviewScope.map((name) => {
                        const candidates =
                          incoming?.[name as (typeof activeDimensions)[number]]
                            .candidates ?? [];
                        const options = [
                          ...new Set([
                            ...candidates,
                            ...(catalog.data?.dimensions[name] ?? []),
                          ]),
                        ];
                        return (
                          <label key={name}>
                            {dimensionLabels[name]}决定值
                            {candidates.length > 0 && (
                              <span> · 候选：{candidates.join("、")}</span>
                            )}
                            <select
                              required
                              aria-label={`${dimensionLabels[name]}决定值`}
                              value={activeValues[name] ?? ""}
                              onChange={(event) =>
                                setActiveValues((current) => ({
                                  ...current,
                                  [name]: event.target.value,
                                }))
                              }
                            >
                              <option value="">请选择</option>
                              {options.map((value) => (
                                <option key={value} value={value}>
                                  {value}
                                </option>
                              ))}
                            </select>
                          </label>
                        );
                      })}
                    </fieldset>
                    {requiredTags.length > 0 && (
                      <fieldset>
                        <legend>发生变化的策略标签决定</legend>
                        {requiredTags.map((tag) => (
                          <label key={tag}>
                            {tag} 标签决定
                            <select
                              required
                              aria-label={`${tag} 标签决定`}
                              value={tagActions[tag] ?? ""}
                              onChange={(event) =>
                                setTagActions((current) => ({
                                  ...current,
                                  [tag]: event.target.value as
                                    StrategyTagDecisionAction | "",
                                }))
                              }
                            >
                              <option value="">请选择</option>
                              <option value="CONFIRM">确认标签</option>
                              <option value="REJECT">拒绝标签</option>
                            </select>
                          </label>
                        ))}
                      </fieldset>
                    )}
                  </>
                ) : (
                  <>
                    <label>
                      复核维度
                      <select
                        value={dimension}
                        onChange={(e) => {
                          setDimension(e.target.value);
                          setValues([]);
                        }}
                      >
                        {activeDimensions.map((name) => (
                          <option key={name} value={name}>
                            {dimensionLabels[name]}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      复核操作
                      <select
                        value={action}
                        onChange={(e) =>
                          setAction(e.target.value as ReviewDecisionAction)
                        }
                      >
                        <option value="CONFIRM">确认候选</option>
                        <option value="OVERRIDE">覆盖分类</option>
                        <option value="REJECT">驳回候选（保留 UNKNOWN）</option>
                      </select>
                    </label>
                    <label>
                      决定值
                      <select
                        required={action !== "REJECT"}
                        value={values[0] || ""}
                        onChange={(e) =>
                          setValues(
                            Array.from(
                              e.target.selectedOptions,
                              (o) => o.value,
                            ),
                          )
                        }
                      >
                        <option value="">请选择</option>
                        {(action === "CONFIRM" && detail.data.baseline
                          ? detail.data.baseline[
                              dimension as (typeof activeDimensions)[number]
                            ].candidates || []
                          : catalog.data?.dimensions[dimension]
                        )?.map((value) => (
                          <option key={value} value={value}>
                            {value}
                          </option>
                        ))}
                      </select>
                    </label>
                  </>
                )}
                <label>
                  复核理由
                  <textarea
                    required
                    maxLength={1024}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                </label>
                <label>
                  证据原文
                  <textarea
                    required
                    value={rawValue}
                    onChange={(e) => setRawValue(e.target.value)}
                  />
                </label>
                <label>
                  资料定位
                  <input
                    required
                    value={locator}
                    onChange={(e) => setLocator(e.target.value)}
                  />
                </label>
                <button
                  disabled={
                    mutation.isPending ||
                    (isCurrentReview &&
                      (reviewScope.some((name) => !activeValues[name]) ||
                        requiredTags.some((tag) => !tagActions[tag])))
                  }
                >
                  提交复核
                </button>
              </form>
            )
          ) : (
            <p>当前会话无分类复核权限，或案件已结束。</p>
          )}
        </article>
      )}
      {notice && <p role="status">{notice}</p>}
      {mutation.isError && <ErrorState error={mutation.error} />}
    </section>
  );
};
