"use client";

import Link from "next/link";

import { ApiSection } from "@/components/api-section";
import { EmptyState } from "@/components/empty-state";

type Plan = { id: string; name: string };

export default function PlansPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">学习计划</h1>
        <Link
          href="/plans/new"
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-foreground"
        >
          新建计划
        </Link>
      </div>

      <ApiSection<Plan[]>
        path="/plans"
        isEmpty={(plans) => plans.length === 0}
        empty={
          <EmptyState
            title="还没有学习计划"
            description="一个计划包含目标、时间安排和一组任务。先建一个，巡检才有东西可看。"
            action={{ href: "/plans/new", label: "新建计划" }}
          />
        }
      >
        {(plans) => (
          <ul className="space-y-3">
            {plans.map((plan) => (
              <li key={plan.id} className="rounded-lg border border-border bg-card p-4">
                <Link href={`/plans/${plan.id}`} className="font-medium hover:underline">
                  {plan.name}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </ApiSection>
    </div>
  );
}
