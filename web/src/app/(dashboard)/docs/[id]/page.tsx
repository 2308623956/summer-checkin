import { EmptyState } from "@/components/empty-state";

export default async function DocumentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">文档</h1>
      <EmptyState
        title="文档编辑还没开通"
        description={`文档 ${id} 的读写接口属于后续需求。`}
        action={{ href: "/docs", label: "返回资料列表" }}
      />
    </div>
  );
}
