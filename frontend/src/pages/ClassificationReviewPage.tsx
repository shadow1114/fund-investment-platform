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
  ReviewDecisionAction,
  ReviewSubmission,
} from "../api/generated/m17.schemas";
import { ApiError, unwrapResponse } from "../api/http";
import { ErrorState } from "../components/ErrorState";
import {
  ClassificationView,
  dimensions,
  dimensionLabels,
} from "../features/classifications/ClassificationView";

export const ClassificationReviewPage = () => {
  const [search, setSearch] = useSearchParams();
  const page = Number(search.get("page") || 1);
  const caseId = Number(search.get("case") || 0);
  const client = useQueryClient();
  const session = useQuery({
    queryKey: ["api", "session"],
    queryFn: async () => unwrapResponse(await getSession()),
  });
  const catalog = useQuery({
    queryKey: ["classification-catalog"],
    queryFn: async () => unwrapResponse(await getClassificationCatalog()),
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
  const [dimension, setDimension] = useState<string>(dimensions[0]);
  const [action, setAction] = useState<ReviewDecisionAction>("CONFIRM");
  const [values, setValues] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [rawValue, setRawValue] = useState("");
  const [locator, setLocator] = useState("");
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
    mutation.mutate({
      expected_revision: detail.data.expected_revision,
      reason: reason.trim(),
      decisions: {
        [dimension]: {
          action,
          value:
            dimension === "geography" || dimension === "market_attributes"
              ? values
              : values[0] || "UNKNOWN",
          evidence: [evidence],
        },
      },
    });
  };
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
            <form aria-label="分类复核" onSubmit={submit}>
              <label>
                复核维度
                <select
                  value={dimension}
                  onChange={(e) => {
                    setDimension(e.target.value);
                    setValues([]);
                  }}
                >
                  {dimensions.map((name) => (
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
                  multiple={
                    dimension === "geography" ||
                    dimension === "market_attributes"
                  }
                  value={
                    dimension === "geography" ||
                    dimension === "market_attributes"
                      ? values
                      : values[0] || ""
                  }
                  onChange={(e) =>
                    setValues(
                      Array.from(e.target.selectedOptions, (o) => o.value),
                    )
                  }
                >
                  <option value="">请选择</option>
                  {(action === "CONFIRM" && detail.data.baseline
                    ? detail.data.baseline[
                        dimension as (typeof dimensions)[number]
                      ].candidates || []
                    : catalog.data?.dimensions[dimension]
                  )?.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
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
              <button disabled={mutation.isPending}>提交复核</button>
            </form>
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
