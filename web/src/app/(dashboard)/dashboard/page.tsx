"use client";

import { ApiSection } from "@/components/api-section";
import { EmptyState } from "@/components/empty-state";

type StatsOverview = {
  streakDays: number;
  checkinCount: number;
  totalMinutes: number;
  completedTasks: number;
  pendingTasks: number;
  unreadNotifications: number;
};

const CARDS: { key: keyof StatsOverview; label: string; unit?: string }[] = [
  { key: "streakDays", label: "连续打卡", unit: "天" },
  { key: "checkinCount", label: "累计打卡", unit: "次" },
  { key: "totalMinutes", label: "学习时长", unit: "分钟" },
  { key: "pendingTasks", label: "待完成任务", unit: "个" },
];

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">概览</h1>

      <ApiSection<StatsOverview>
        path="/stats/overview"
        loadingRows={1}
        isEmpty={(data) => data.checkinCount === 0 && data.streakDays === 0}
        empty={
          <EmptyState
            title="还没有打卡记录"
            description="打第一次卡之后，这里会显示连续天数和学习时长。"
            action={{ href: "/checkin", label: "去打卡" }}
          />
        }
      >
        {(stats) => (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {CARDS.map((card) => (
              <div key={card.key} className="rounded-lg border border-border bg-card p-4">
                <p className="text-sm text-muted">{card.label}</p>
                <p className="mt-1 text-2xl font-semibold">
                  {stats[card.key]}
                  {card.unit ? <span className="ml-1 text-sm font-normal text-muted">{card.unit}</span> : null}
                </p>
              </div>
            ))}
          </div>
        )}
      </ApiSection>
    </div>
  );
}
