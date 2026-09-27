"use client";

import { ApiSection } from "@/components/api-section";
import { EmptyState } from "@/components/empty-state";

type Run = { id: string; status: string; goal: string };

export default function AgentPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">每日巡检</h1>
      <p className="text-sm text-muted">
        巡检会看你的打卡与任务情况，给出建议。写库类建议需要你点批准才会执行。
      </p>

      <ApiSection<Run[]>
        path="/runs"
        isEmpty={(runs) => runs.length === 0}
        empty={
          <EmptyState
            title="还没有巡检记录"
            description="巡检运行时还没接上（R000 只做到排队）。接上之后每晚 21:00 会自动跑一次。"
          />
        }
      >
        {(runs) => (
          <ul className="space-y-3">
            {runs.map((run) => (
              <li key={run.id} className="rounded-lg border border-border bg-card p-4">
                <p className="font-medium">{run.goal}</p>
                <p className="mt-1 text-sm text-muted">{run.status}</p>
              </li>
            ))}
          </ul>
        )}
      </ApiSection>
    </div>
  );
}
