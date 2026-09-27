import { EmptyState } from "@/components/empty-state";

/**
 * 打卡页。R000 **没有写接口**，所以表单是禁用的——并明确说明原因，
 * 而不是做一个点了没反应的按钮（`implement.md` S4：不伪造成功）。
 */
export default function CheckinPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">打卡</h1>

      <EmptyState
        title="打卡功能还没开通"
        description="当前版本只搭好了骨架，写接口会在下一个需求里加上。在那之前，记录不会被保存。"
      />

      <fieldset disabled className="space-y-4 rounded-lg border border-border bg-card p-6 opacity-60">
        <legend className="px-2 text-sm font-medium">打卡表单（暂不可用）</legend>

        <label className="block">
          <span className="text-sm font-medium">今天做了什么</span>
          <textarea
            rows={3}
            placeholder="例如：复习了并发控制的三种加锁方式"
            className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
          />
        </label>

        <label className="block">
          <span className="text-sm font-medium">时长（小时）</span>
          <input
            type="number"
            step="0.5"
            min="0"
            placeholder="1.5"
            className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
          />
        </label>

        <button
          type="button"
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-foreground"
        >
          提交打卡
        </button>
        <p className="text-xs text-muted">按钮当前不可用：写接口尚未实现。</p>
      </fieldset>
    </div>
  );
}
