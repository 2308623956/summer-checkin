import { EmptyState } from "@/components/empty-state";

export default async function KnowledgeSourcePage({
  params,
}: {
  params: Promise<{ sourceName: string }>;
}) {
  const { sourceName } = await params;
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">知识库</h1>
      <EmptyState
        title="知识库查看还没开通"
        description={`资料「${decodeURIComponent(sourceName)}」的切块与向量还没入库，检索属于后续需求。`}
        action={{ href: "/docs", label: "返回资料列表" }}
      />
    </div>
  );
}
