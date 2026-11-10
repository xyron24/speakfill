export default function ProgressBar({ current, total }: { current: number; total: number }) {
  const pct = Math.min(100, Math.round(((current - 1) / total) * 100));
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-sm font-bold text-slate-900">
          Field {Math.min(current, total)} of {total}
        </span>
        <span className="text-sm font-medium text-slate-600">{pct}%</span>
      </div>
      <div
        className="h-2.5 overflow-hidden rounded-full bg-slate-200"
        role="progressbar"
        aria-valuenow={current}
        aria-valuemin={1}
        aria-valuemax={total}
      >
        <div className="h-full rounded-full bg-teal-600 transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
