import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Loader2, Search } from "lucide-react";
import Layout from "../components/Layout";
import { getResults } from "../api";
import type {
  AnalysisResult,
  AnalyzedStatement,
  Classification,
} from "../types";

const CHIP: Record<Classification, string> = {
  REQUIREMENT: "chip-primary",
  RECOMMENDATION: "chip-warning",
  ASK: "chip-violet",
  INFORMATIONAL: "chip-muted",
};

export default function Statements() {
  const { jobId: paramId } = useParams();
  const jobId = paramId ?? localStorage.getItem("lastJobId") ?? "";
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [classFilter, setClassFilter] = useState<"" | Classification>("");
  const [section, setSection] = useState<string>("");
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;
    getResults(jobId).then(setResult).catch((e) => setError(e.message));
  }, [jobId]);

  const all = useMemo<AnalyzedStatement[]>(
    () => result?.sections.flatMap((s) => s.statements) ?? [],
    [result],
  );

  const filtered = useMemo(
    () =>
      all.filter((s) => {
        if (classFilter && s.classification !== classFilter) return false;
        if (section && s.section !== section) return false;
        if (query && !s.text.toLowerCase().includes(query.toLowerCase()))
          return false;
        return true;
      }),
    [all, classFilter, section, query],
  );

  if (!jobId) {
    return (
      <Layout title="Statements" subtitle="Upload an SOR to get started">
        <div className="panel">
          <div className="panel-body text-center py-12">
            <Link to="/upload" className="btn-cta inline-flex">
              Upload SOR
            </Link>
          </div>
        </div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout title="Statements">
        <div className="panel">
          <div className="panel-body text-danger-ink">Error: {error}</div>
        </div>
      </Layout>
    );
  }

  if (!result) {
    return (
      <Layout title="Statements" subtitle="Loading…">
        <div className="panel">
          <div className="panel-body flex items-center justify-center gap-2 py-12 text-muted">
            <Loader2 size={16} className="animate-spin" />
            Fetching results…
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout
      title="Statements"
      subtitle={`${result.filename} · ${result.total_statements} total`}
    >
      <div className="panel">
        <div className="panel-head">
          <div className="flex items-center gap-3 flex-1">
            <div className="relative flex-1 max-w-md">
              <Search
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-muted"
              />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search statement text…"
                className="input pl-9"
              />
            </div>
            <select
              value={classFilter}
              onChange={(e) =>
                setClassFilter(e.target.value as "" | Classification)
              }
              className="select max-w-[200px]"
            >
              <option value="">All classifications</option>
              <option value="REQUIREMENT">Requirement</option>
              <option value="RECOMMENDATION">Recommendation</option>
              <option value="ASK">Ask</option>
              <option value="INFORMATIONAL">Informational</option>
            </select>
            <select
              value={section}
              onChange={(e) => setSection(e.target.value)}
              className="select max-w-[260px]"
            >
              <option value="">All sections</option>
              {result.sections.map((s) => (
                <option key={s.section_name} value={s.section_name}>
                  {s.section_name}
                </option>
              ))}
            </select>
          </div>
          <span className="chip chip-muted shrink-0">
            {filtered.length} / {all.length}
          </span>
        </div>

        <div className="panel-body p-0 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left">
                <Th>ID</Th>
                <Th>Section</Th>
                <Th>Statement</Th>
                <Th>Class</Th>
                <Th>Score</Th>
                <Th>Rules</Th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="px-5 py-10 text-center text-muted"
                  >
                    No statements match your filters.
                  </td>
                </tr>
              )}
              {filtered.map((s) => {
                const open = expanded === s.id;
                const scoreChip =
                  s.quality_score >= 80
                    ? "chip-success"
                    : s.quality_score >= 50
                    ? "chip-warning"
                    : "chip-danger";
                return (
                  <FragmentRow
                    key={s.id}
                    s={s}
                    open={open}
                    onToggle={() => setExpanded(open ? null : s.id)}
                    scoreChip={scoreChip}
                  />
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </Layout>
  );
}

function FragmentRow({
  s,
  open,
  onToggle,
  scoreChip,
}: {
  s: AnalyzedStatement;
  open: boolean;
  onToggle: () => void;
  scoreChip: string;
}) {
  return (
    <>
      <tr
        onClick={onToggle}
        className="border-t border-border-2 hover:bg-tint cursor-pointer"
      >
        <Td className="font-mono text-[11.5px] text-muted">{s.id}</Td>
        <Td className="text-text-2">{s.section}</Td>
        <Td className="max-w-2xl">
          <div className={open ? "" : "line-clamp-2"}>{s.text}</div>
        </Td>
        <Td>
          <span className={`chip ${CHIP[s.classification]}`}>
            {s.classification.toLowerCase()}
          </span>
        </Td>
        <Td>
          <span className={`chip ${scoreChip}`}>{s.quality_score}</span>
        </Td>
        <Td className="text-[12px] text-muted">
          {s.violated_rules.join(", ") || "—"}
        </Td>
      </tr>
      {open && (
        <tr className="bg-tint">
          <td colSpan={6} className="px-5 py-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Field label="ISO category" value={s.iso_category} />
              <Field
                label="Obligation"
                value={s.obligation_keyword || "none"}
              />
              <Field label="Verifiability" value={s.verifiability} />
              <Field
                label="Style flags"
                value={`${s.is_atomic ? "Atomic" : "Multi"} · ${
                  s.is_passive_voice ? "Passive" : "Active"
                } · ${s.is_negative ? "Negative" : "Positive"}`}
              />
              {s.ambiguous_words.length > 0 && (
                <Field
                  label="Ambiguous"
                  value={s.ambiguous_words.join(", ")}
                />
              )}
              {s.escape_clauses.length > 0 && (
                <Field
                  label="Escape clauses"
                  value={s.escape_clauses.join("; ")}
                />
              )}
              {s.placeholders.length > 0 && (
                <Field
                  label="Placeholders"
                  value={s.placeholders.join(", ")}
                />
              )}
              <Field
                label="Suggested action"
                value={s.suggested_action}
                wide
              />
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="text-[11px] font-bold uppercase tracking-[0.04em] text-muted px-5 py-3">
      {children}
    </th>
  );
}

function Td({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <td className={`px-5 py-3 text-text-2 ${className}`}>{children}</td>;
}

function Field({
  label,
  value,
  wide,
}: {
  label: string;
  value: string;
  wide?: boolean;
}) {
  return (
    <div className={wide ? "col-span-2 md:col-span-4" : ""}>
      <div className="text-[10.5px] uppercase tracking-[0.06em] text-muted font-bold">
        {label}
      </div>
      <div className="font-medium text-text-2 mt-1 text-[13px]">{value}</div>
    </div>
  );
}
