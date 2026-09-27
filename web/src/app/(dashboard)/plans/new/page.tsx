import { EmptyState } from "@/components/empty-state";

export default function NewPlanPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">新建计划</h1>
      <EmptyState
        title="创建计划还没开通"
        description="计划需要由 service 写库，写接口会在下一个需求里加上。"
        action={{ href: "/plans", label: "返回计划列表" }}
      />
    </div>
  );
}
