import { EmptyState } from "@/components/empty-state";

export default function DocsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">资料</h1>
      <EmptyState
        title="资料库还没开通"
        description="导入资料要切块、向量化并写入 documentchunk，属于检索需求的范围。"
      />
    </div>
  );
}
