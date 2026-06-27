import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Circle,
  Hash,
  Table2,
  AlignLeft,
  Loader2,
} from "lucide-react";
import Layout from "../components/Layout";
import { getResults } from "../api";
import type {
  AnalysisResult,
  AnalyzedStatement,
  Classification,
  SourceType,
} from "../types";

const CHIP: Record<Classification, string> = {
  REQUIREMENT: "chip-success",
  ASK: "chip-violet",
  RECOMMENDATION: "chip-warning",
  INFORMATIONAL: "chip-muted",
};

const CHIP_LABEL: Record<Classification, string> = {
  REQUIREMENT: "Requirement",
  ASK: "Ask",
  RECOMMENDATION: "Recommendation",
  INFORMATIONAL: "Info",
};

const SOURCE_ICON: Record<SourceType, React.ReactNode> = {
  text: <AlignLeft size={14} className="text-muted-2" />,
  bullet: <Circle size={8} className="text-muted-2 fill-muted-2" />,
  numbered: <Hash size={14} className="text-muted-2" />,
  table_row: <Table2 size={14} className="text-primary-ink" />,
};

const SOURCE_LABEL: Record<SourceType, string> = {
  text: "paragraph",
  bullet: "bullet",
  numbered: "list item",
  table_row: "table row",
};

export default function SectionDetail() {
  const { jobId = "", sectionName = "" } = useParams();
  const decoded = decodeURIComponent(sectionName);

  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | Classification>("all");

  useEffect(() => {
    if (!jobId) return;
    getResults(jobId).then(setResult).catch((e) => setError(e.message));
  }, [jobId]);

  if (error) {
    return (
      <Layout title={decoded}>
        <div className="panel">
          <div className="panel-body text-danger-ink">Error: {error}</div>
        </div>
      </Layout>
    );
  }

  if (!result) {
    return (
      <Layout title={decoded} subtitle="Loading…">
        <div className="panel">
          <div className="panel-body flex items-center justify-center gap-2 py-12 text-muted">
            <Loader2 size={16} className="animate-spin" />
            Fetching section…
          </div>
        </div>
      </Layout>
    );
  }

  const section = result.sections.find((s) => s.section_name === decoded);

  if (!section) {
    return (
      <Layout title={decoded} subtitle="Section not found">
        <div className="panel">
          <div className="panel-body">
            <Link to={`/jobs/${jobId}`} className="btn-ghost inline-flex">
              <ArrowLeft size={14} /> Back
            </Link>
          </div>
        </div>
      </Layout>
    );
  }

  // Group consecutive table_row statements so we can render them as one block
  const groups = groupBySource(section.statements);

  const visibleGroups = groups
    .map((g) => ({
      ...g,
      items: g.items.filter(
        (s) => filter === "all" || s.classification === filter,
      ),
    }))
    .filter((g) => g.items.length > 0);

  const back = (
    <Link to={`/jobs/${jobId}`} className="btn-ghost">
      <ArrowLeft size={14} /> Overview
    </Link>
  );

  return (
    <Layout
      title={decoded}
      subtitle={`${section.total} statements · ${section.requirements} Req · ${section.asks} Ask · ${section.recommendations} Rec · ${section.informational} Info`}
      right={back}
    >
      <div className="panel mb-4">
        <div className="panel-head">
          <h2 className="panel-title">Filter</h2>
          <div className="flex items-center gap-1.5">
            <FilterBtn active={filter === "all"} onClick={() => setFilter("all")}>
              All ({section.total})
            </FilterBtn>
            <FilterBtn
              active={filter === "REQUIREMENT"}
              onClick={() => setFilter("REQUIREMENT")}
              chip="chip-success"
            >
              Requirements ({section.requirements})
            </FilterBtn>
            <FilterBtn
              active={filter === "ASK"}
              onClick={() => setFilter("ASK")}
              chip="chip-violet"
            >
              Asks ({section.asks})
            </FilterBtn>
            <FilterBtn
              active={filter === "RECOMMENDATION"}
              onClick={() => setFilter("RECOMMENDATION")}
              chip="chip-warning"
            >
              Recommendations ({section.recommendations})
            </FilterBtn>
            <FilterBtn
              active={filter === "INFORMATIONAL"}
              onClick={() => setFilter("INFORMATIONAL")}
              chip="chip-muted"
            >
              Info ({section.informational})
            </FilterBtn>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        {visibleGroups.length === 0 ? (
          <div className="panel">
            <div className="panel-body text-center py-10 text-muted">
              No statements match this filter.
            </div>
          </div>
        ) : (
          visibleGroups.map((g, i) =>
            g.kind === "table" ? (
              <TableBlock key={i} items={g.items} />
            ) : (
              <ListBlock key={i} kind={g.kind} items={g.items} />
            ),
          )
        )}
      </div>
    </Layout>
  );
}

type Group =
  | { kind: "text"; items: AnalyzedStatement[] }
  | { kind: "bullet"; items: AnalyzedStatement[] }
  | { kind: "numbered"; items: AnalyzedStatement[] }
  | { kind: "table"; items: AnalyzedStatement[] };

function groupBySource(statements: AnalyzedStatement[]): Group[] {
  const groups: Group[] = [];
  for (const s of statements) {
    const kind: Group["kind"] =
      s.source_type === "table_row"
        ? "table"
        : s.source_type === "bullet"
        ? "bullet"
        : s.source_type === "numbered"
        ? "numbered"
        : "text";
    const last = groups[groups.length - 1];
    if (last && last.kind === kind) {
      last.items.push(s);
    } else {
      groups.push({ kind, items: [s] } as Group);
    }
  }
  return groups;
}

function TableBlock({ items }: { items: AnalyzedStatement[] }) {
  return (
    <div className="panel">
      <div className="panel-head">
        <div className="flex items-center gap-2">
          <Table2 size={16} className="text-primary-ink" />
          <h2 className="panel-title">Table data ({items.length} rows)</h2>
        </div>
      </div>
      <div className="panel-body p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left">
              <th className="text-[11px] font-bold uppercase tracking-[0.04em] text-muted px-5 py-3 w-16">
                ID
              </th>
              <th className="text-[11px] font-bold uppercase tracking-[0.04em] text-muted px-5 py-3">
                Row
              </th>
              <th className="text-[11px] font-bold uppercase tracking-[0.04em] text-muted px-5 py-3 w-44">
                Class
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((s) => (
              <tr key={s.id} className="border-t border-border-2 align-top">
                <td className="px-5 py-3 font-mono text-[11px] text-muted">
                  {s.id}
                </td>
                <td className="px-5 py-3 text-text-2 text-[13.5px]">
                  {s.text}
                  {s.classification_reason && (
                    <div className="text-[11.5px] text-muted italic mt-1">
                      {s.classification_reason}
                    </div>
                  )}
                </td>
                <td className="px-5 py-3">
                  <div className="flex flex-col items-start gap-1">
                    <span className={`chip ${CHIP[s.classification]}`}>
                      {CHIP_LABEL[s.classification]}
                    </span>
                    {s.iso_category && (
                      <span className="chip chip-primary text-[10.5px]">
                        {s.iso_category}
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ListBlock({
  kind,
  items,
}: {
  kind: "text" | "bullet" | "numbered";
  items: AnalyzedStatement[];
}) {
  const title =
    kind === "bullet"
      ? `Bullet points (${items.length})`
      : kind === "numbered"
      ? `Numbered items (${items.length})`
      : `Paragraph statements (${items.length})`;

  return (
    <div className="panel">
      <div className="panel-head">
        <div className="flex items-center gap-2">
          {SOURCE_ICON[kind]}
          <h2 className="panel-title">{title}</h2>
        </div>
      </div>
      <div className="panel-body p-0">
        <ul className="divide-y divide-border-2">
          {items.map((s, idx) => (
            <li
              key={s.id}
              className="px-5 py-3.5 flex gap-3 items-start"
            >
              <span className="shrink-0 mt-1 text-muted-2 text-[12px] w-6 text-right tabular-nums">
                {kind === "numbered" ? `${idx + 1}.` : kind === "bullet" ? "•" : ""}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-3 mb-1">
                  <span className="font-mono text-[11px] text-muted">
                    {s.id} · {SOURCE_LABEL[s.source_type ?? "text"]}
                  </span>
                  <div className="flex items-center gap-1.5">
                    {s.obligation_keyword &&
                      s.obligation_keyword !== "none" && (
                        <span className="chip chip-muted text-[10.5px]">
                          {s.obligation_keyword}
                        </span>
                      )}
                    <span className={`chip ${CHIP[s.classification]}`}>
                      {CHIP_LABEL[s.classification]}
                    </span>
                  </div>
                </div>
                <div className="text-[13.5px] text-text leading-relaxed">
                  {s.text}
                </div>
                {s.classification_reason && (
                  <div className="text-[11.5px] text-muted italic mt-1.5">
                    Why: {s.classification_reason}
                  </div>
                )}
                {s.iso_category && (
                  <div className="mt-1.5">
                    <span className="chip chip-primary text-[10.5px]">
                      {s.iso_category}
                    </span>
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function FilterBtn({
  active,
  onClick,
  children,
  chip,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  chip?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`text-[12.5px] font-semibold px-3 py-1.5 rounded-full border transition ${
        active
          ? chip
            ? `${chip} border-transparent`
            : "bg-text text-white border-transparent"
          : "bg-surface text-text-2 border-border hover:bg-tint"
      }`}
    >
      {children}
    </button>
  );
}
