import { EmptyState } from "@/components/empty-state";

export default async function PlanDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">计划详情</h1>
      <EmptyState
        title="计划详情还没开通"
        description={`读取计划 ${id} 的接口属于后续需求。列表页已经能取数，这里先留空。`}
        action={{ href: "/plans", label: "返回计划列表" }}
      />
    </div>
  );
}
