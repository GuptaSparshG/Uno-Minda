import { NavLink } from "react-router-dom";
import {
  Upload,
  FolderClock,
  ListTree,
  Brain,
  HelpCircle,
  Settings,
  Plug,
  Cpu,
} from "lucide-react";

interface Item {
  label: string;
  to: string;
  Icon: typeof Upload;
}

const MENU: Item[] = [
  { label: "Upload", to: "/upload", Icon: Upload },
  { label: "Jobs (history)", to: "/jobs", Icon: FolderClock },
  { label: "Section Analysis", to: "/section-analysis", Icon: ListTree },
  { label: "Semantic Analysis", to: "/semantic-analysis", Icon: Brain },
];

const SYSTEM: Item[] = [
  { label: "Get help", to: "/help", Icon: HelpCircle },
  { label: "Settings", to: "/setting", Icon: Settings },
  { label: "Integrations", to: "/integration", Icon: Plug },
];

export default function Sidebar() {
  return (
    <aside
      className="shrink-0 h-screen sticky top-0 bg-surface border-r border-border flex flex-col"
      style={{ width: 240 }}
    >
      <div className="px-5 pt-5">
        <div className="flex items-center gap-2.5 pb-4 border-b border-border-2">
          <div
            className="w-[38px] h-[38px] rounded-[10px] grid place-items-center text-white shadow-brand shrink-0"
            style={{ background: "linear-gradient(135deg, #10b981, #0891b2)" }}
          >
            <Cpu size={18} />
          </div>
          <div className="leading-tight">
            <div className="font-extrabold tracking-tight text-[15px]">
              Minda SOR
            </div>
            <div className="text-[11px] text-muted">Requirements Analyzer</div>
          </div>
        </div>
      </div>

      <Section title="MENU" items={MENU} />
      <Section title="SYSTEM" items={SYSTEM} />
    </aside>
  );
}

function Section({ title, items }: { title: string; items: Item[] }) {
  return (
    <div className="px-3 mt-4">
      <div className="px-3 mb-1.5 text-[10.5px] font-bold tracking-[0.08em] text-muted-2 uppercase">
        {title}
      </div>
      <nav className="flex flex-col gap-0.5">
        {items.map(({ label, to, Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              [
                "flex items-center gap-2.5 px-3 py-2 rounded-sm text-[13.5px] font-medium transition duration-150",
                isActive
                  ? "bg-teal-soft text-teal-ink"
                  : "text-muted hover:bg-tint hover:text-text",
              ].join(" ")
            }
          >
            {({ isActive }) => (
              <>
                <Icon
                  size={16}
                  className={isActive ? "text-teal opacity-100" : "opacity-80"}
                />
                <span>{label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
