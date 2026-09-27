"use client";

import { ApiSection } from "@/components/api-section";
import { EmptyState } from "@/components/empty-state";

type Checkin = { id: string; content: string; hours: number };

export default function StatisticsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">统计</h1>

      <ApiSection<Checkin[]>
        path="/checkins"
        isEmpty={(checkins) => checkins.length === 0}
        empty={
          <EmptyState
            title="还没有可统计的数据"
            description="打卡记录积累起来之后，这里会显示时长与主题分布。"
            action={{ href: "/checkin", label: "去打卡" }}
          />
        }
      >
        {(checkins) => (
          <ul className="space-y-3">
            {checkins.map((checkin) => (
              <li key={checkin.id} className="rounded-lg border border-border bg-card p-4">
                <p>{checkin.content}</p>
                <p className="mt-1 text-sm text-muted">{checkin.hours} 小时</p>
              </li>
            ))}
          </ul>
        )}
      </ApiSection>
    </div>
  );
}
