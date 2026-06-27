import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  CheckCircle2,
  ClipboardList,
  Download,
  FileSpreadsheet,
  FileText,
  Layers,
  Loader2,
  ChevronRight,
} from "lucide-react";
import Layout from "../components/Layout";
import StatCard from "../components/StatCard";
import { exportUrl, getResults } from "../api";
import type { AnalysisResult, SectionResult } from "../types";

export default function Dashboard() {
  const { jobId: paramId } = useParams();
  const jobId = paramId ?? localStorage.getItem("lastJobId") ?? "";

  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;
    setError(null);
    getResults(jobId).then(setResult).catch((e) => setError(e.message));
  }, [jobId]);

  if (!jobId) {
    return (
      <Layout title="Overview" subtitle="No analysis yet">
        <div className="panel">
          <div className="panel-body text-center py-12">
            <div className="text-muted mb-4">
              Upload a Statement of Requirement PDF to get started.
            </div>
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
      <Layout title="Overview">
        <div className="panel">
          <div className="panel-body text-danger-ink">Error: {error}</div>
        </div>
      </Layout>
    );
  }

  if (!result) {
    return (
      <Layout title="Overview" subtitle="Loading…">
        <div className="panel">
          <div className="panel-body flex items-center justify-center gap-2 py-12 text-muted">
            <Loader2 size={16} className="animate-spin" />
            Fetching analysis…
          </div>
        </div>
      </Layout>
    );
  }

  const totalReqs = result.sections.reduce((s, x) => s + x.requirements, 0);
  const totalAsks = result.sections.reduce((s, x) => s + x.asks, 0);

  const sorted = result.sections
    .slice()
    .sort((a, b) => b.requirements + b.asks - (a.requirements + a.asks));

  const headerRight = (
    <div className="flex items-center gap-2">
      <a href={exportUrl.excel(jobId)} className="btn-ghost">
        <FileSpreadsheet size={14} /> Excel
      </a>
      <a href={exportUrl.csv(jobId)} className="btn-ghost">
        <FileText size={14} /> CSV
      </a>
      <a href={exportUrl.json(jobId)} className="btn-ghost">
        <Download size={14} /> JSON
      </a>
    </div>
  );

  return (
    <Layout
      title="Overview"
      subtitle={`${result.filename} · ${result.total_sections} sections`}
      right={headerRight}
    >
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
        <StatCard
          icon={<Layers size={18} />}
          label="Sections"
          value={result.total_sections}
          variant="blue"
        />
        <StatCard
          icon={<CheckCircle2 size={18} />}
          label="Requirements"
          value={totalReqs}
          variant="green"
        />
        <StatCard
          icon={<ClipboardList size={18} />}
          label="Asks"
          value={totalAsks}
          variant="violet"
        />
      </div>

      <div className="panel mt-4">
        <div className="panel-head">
          <div>
            <h2 className="panel-title">Sections — Requirements vs Asks</h2>
            <p className="panel-sub">
              Counts per section. Click any row to view its statements.
            </p>
          </div>
        </div>
        <div className="panel-body p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left">
                <Th>Section</Th>
                <Th align="right">Requirements</Th>
                <Th align="right">Asks</Th>
                <Th>Balance</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {sorted.map((s) => (
                <SectionRow key={s.section_name} s={s} jobId={jobId} />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Layout>
  );
}

function SectionRow({ s, jobId }: { s: SectionResult; jobId: string }) {
  const total = s.requirements + s.asks;
  const reqPct = total === 0 ? 0 : Math.round((s.requirements / total) * 100);
  const askPct = total === 0 ? 0 : 100 - reqPct;

  return (
    <tr className="border-t border-border-2 hover:bg-tint group">
      <td className="px-5 py-3.5 font-medium text-text">{s.section_name}</td>
      <td className="px-5 py-3.5 text-right">
        <span className="chip chip-success">{s.requirements}</span>
      </td>
      <td className="px-5 py-3.5 text-right">
        <span className="chip chip-violet">{s.asks}</span>
      </td>
      <td className="px-5 py-3.5 min-w-[220px]">
        {total > 0 ? (
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 rounded-full bg-border overflow-hidden flex">
              <div
                className="h-full bg-teal"
                style={{ width: `${reqPct}%` }}
                title={`${s.requirements} requirements`}
              />
              <div
                className="h-full bg-violet"
                style={{ width: `${askPct}%` }}
                title={`${s.asks} asks`}
              />
            </div>
            <span className="text-[11px] text-muted font-medium tabular-nums w-16 text-right">
              {reqPct}% / {askPct}%
            </span>
          </div>
        ) : (
          <span className="text-[12px] text-muted">—</span>
        )}
      </td>
      <td className="px-5 py-3.5">
        <Link
          to={`/jobs/${jobId}/sections/${encodeURIComponent(s.section_name)}`}
          className="text-muted hover:text-text inline-flex items-center"
        >
          <ChevronRight size={16} />
        </Link>
      </td>
    </tr>
  );
}

function Th({
  children,
  align = "left",
}: {
  children?: React.ReactNode;
  align?: "left" | "right";
}) {
  return (
    <th
      className={`text-[11px] font-bold uppercase tracking-[0.04em] text-muted px-5 py-3 ${
        align === "right" ? "text-right" : "text-left"
      }`}
    >
      {children}
    </th>
  );
}
