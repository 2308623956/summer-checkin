"use client";

import { ApiSection } from "@/components/api-section";
import { EmptyState } from "@/components/empty-state";

type Notification = { id: string; title: string; content: string };

export default function NotificationsSection() {
  return (
    <ApiSection<Notification[]>
      path="/notifications"
      isEmpty={(items) => items.length === 0}
      empty={
        <EmptyState
          title="没有新通知"
          description="巡检给出建议或你设的提醒到点时，通知会出现在这里。"
        />
      }
    >
      {(items) => (
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={item.id} className="rounded-lg border border-border bg-card p-4">
              <p className="font-medium">{item.title}</p>
              <p className="mt-1 text-sm text-muted">{item.content}</p>
            </li>
          ))}
        </ul>
      )}
    </ApiSection>
  );
}
