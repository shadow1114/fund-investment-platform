import { ApiError } from "../api/http";
export const ErrorState = ({ error }: { error: unknown }) => {
  const e = error instanceof ApiError ? error : undefined;
  return (
    <section role="alert">
      <strong>{e ? `HTTP ${e.status} · ${e.code}` : "请求失败"}</strong>
      <div>
        {e?.message ?? (error instanceof Error ? error.message : "未知错误")}
      </div>
    </section>
  );
};
