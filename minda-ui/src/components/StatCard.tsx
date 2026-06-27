import type { ReactNode } from "react";

type Variant = "blue" | "green" | "amber" | "violet";

interface Props {
  icon: ReactNode;
  label: string;
  value: string | number;
  variant?: Variant;
  hint?: string;
}

export default function StatCard({
  icon,
  label,
  value,
  variant = "blue",
  hint,
}: Props) {
  return (
    <div className="bg-surface border border-border rounded-xl p-[18px] shadow-card transition duration-150 hover:-translate-y-[1px] hover:shadow-soft">
      <div className="flex items-center gap-3">
        <span className={`stat-icon stat-icon-${variant}`}>{icon}</span>
        <div className="min-w-0">
          <div className="text-[11.5px] text-muted font-medium tracking-wide uppercase">
            {label}
          </div>
          <div className="text-2xl font-extrabold tracking-tight mt-0.5">
            {value}
          </div>
        </div>
      </div>
      {hint && <div className="mt-2 text-[12px] text-muted">{hint}</div>}
    </div>
  );
}
