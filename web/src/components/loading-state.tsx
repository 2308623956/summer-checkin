/** 骨架屏。加载态不该是空白，也不该是转圈挡住布局。 */
export function LoadingState({ rows = 3, label = "加载中" }: { rows?: number; label?: string }) {
  return (
    <div className="space-y-3" role="status" aria-label={label}>
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="h-16 animate-pulse rounded-lg bg-border/60" />
      ))}
    </div>
  );
}
