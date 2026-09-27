import { EmptyState } from "@/components/empty-state";

export default async function PlanStudioPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">计划工作室</h1>
      <EmptyState
        title="工作室还没开通"
        description={`文档工作室要调模型池写计划文档（计划 ${id}），属于后续需求。`}
        action={{ href: `/plans/${id}`, label: "返回计划详情" }}
      />
    </div>
  );
}
