"use client";

import NotificationsSection from "@/components/notifications-section";
import { useApi } from "@/lib/use-api";

type Meta = {
  version: string;
  env: string;
  api_version: string;
  features: { chatroom: boolean; resume_review: boolean; quiz_import: boolean; eval: boolean };
  limits: { checkin_max_hours: number; quiz_size_max: number; agent_daily_tokens: number };
  quota: { used_tokens_today: number; limit_tokens: number; resets_at: string } | null;
};

/** 个人页同时证明两件事：`/meta` 取数通了，通知接口也通了。 */
export default function ProfilePage() {
  const { data, error, loading } = useApi<Meta>("/meta");

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">我的</h1>

      <section className="rounded-lg border border-border bg-card p-4">
        <h2 className="text-sm font-medium text-muted">服务状态</h2>
        {loading ? <p className="mt-2 text-sm text-muted">加载中…</p> : null}
        {error ? <p className="mt-2 text-sm text-danger">服务信息取不到，稍后重试。</p> : null}
        {data ? (
          <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <dt className="text-muted">版本</dt>
            <dd>{data.version}</dd>
            <dt className="text-muted">环境</dt>
            <dd>{data.env}</dd>
            <dt className="text-muted">接口版本</dt>
            <dd>{data.api_version}</dd>
            <dt className="text-muted">巡检日额度</dt>
            <dd>{data.limits.agent_daily_tokens.toLocaleString()} tokens</dd>
            <dt className="text-muted">今日已用</dt>
            {/* R000 还没有用量统计：如实说"暂不显示"，不要拿 0 冒充。 */}
            <dd>{data.quota ? `${data.quota.used_tokens_today}` : "暂不显示"}</dd>
          </dl>
        ) : null}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted">通知</h2>
        <NotificationsSection />
      </section>
    </div>
  );
}
