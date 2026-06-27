import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  CheckCircle2,
  ClipboardList,
  Clock,
  FileText,
  Loader2,
  RefreshCcw,
  Upload,
} from "lucide-react";
import Layout from "../components/Layout";
import { listJobs } from "../api";
import type { JobListItem } from "../types";

export default function Jobs() {
  const [jobs, setJobs] = useState<JobListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloading, setReloading] = useState(false);

  const fetchJobs = () => {
    setReloading(true);
    listJobs()
      .then((r) => {
        // Backend already sorts newest-first; show all returned (capped on the server).
        setJobs(r.jobs);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setReloading(false));
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  const headerRight = (
    <>
      <button onClick={fetchJobs} className="btn-ghost" disabled={reloading}>
        <RefreshCcw size={14} className={reloading ? "animate-spin" : ""} />
        Refresh
      </button>
      <Link to="/upload" className="btn-cta">
        <Upload size={14} /> New analysis
      </Link>
    </>
  );

  if (error) {
    return (
      <Layout title="Jobs" right={headerRight}>
        <div className="panel">
          <div className="panel-body text-danger-ink">Error: {error}</div>
        </div>
      </Layout>
    );
  }

  if (!jobs) {
    return (
      <Layout title="Jobs" subtitle="Loading…">
        <div className="panel">
          <div className="panel-body flex items-center justify-center gap-2 py-12 text-muted">
            <Loader2 size={16} className="animate-spin" />
            Fetching history…
          </div>
        </div>
      </Layout>
    );
  }

  if (jobs.length === 0) {
    return (
      <Layout title="Jobs" subtitle="No analyses yet" right={headerRight}>
        <div className="panel">
          <div className="panel-body text-center py-12">
            <div className="text-muted mb-4">
              You haven't analyzed any SOR documents yet.
            </div>
            <Link to="/upload" className="btn-cta inline-flex">
              <Upload size={14} /> Upload your first PDF
            </Link>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout
      title="Jobs"
      subtitle={`${jobs.length} ${jobs.length === 1 ? "analysis" : "analyses"} on disk`}
      right={headerRight}
    >
      <div className="panel">
        <div className="panel-body p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left">
                <Th>File</Th>
                <Th align="right">Sections</Th>
                <Th align="right">Statements</Th>
                <Th align="right">Requirements</Th>
                <Th align="right">Asks</Th>
                <Th>Created</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr
                  key={j.job_id}
                  className="border-t border-border-2 hover:bg-tint"
                >
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2.5">
                      <span className="w-8 h-8 grid place-items-center rounded-[8px] bg-primary-soft text-primary-ink shrink-0">
                        <FileText size={14} />
                      </span>
                      <div className="min-w-0">
                        <div className="font-medium text-text truncate max-w-[280px]">
                          {j.filename}
                        </div>
                        <div className="font-mono text-[11px] text-muted">
                          {j.job_id.slice(0, 8)}…
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-right tabular-nums text-text-2">
                    {j.total_sections}
                  </td>
                  <td className="px-5 py-3.5 text-right tabular-nums text-text-2">
                    {j.total_statements}
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <span className="chip chip-success">
                      <CheckCircle2 size={11} /> {j.requirements_count}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <span className="chip chip-violet">
                      <ClipboardList size={11} /> {j.asks_count}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-muted">
                    <span className="inline-flex items-center gap-1.5 text-[12.5px]">
                      <Clock size={12} />
                      {formatDate(j.created_at)}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <Link
                        to={`/section-analysis/${j.job_id}`}
                        className="btn-ghost text-[12px]"
                        title="Raw content per section"
                      >
                        Sections
                      </Link>
                      <Link
                        to={`/semantic-analysis/${j.job_id}`}
                        className="btn-cta text-[12px]"
                        style={{ padding: "6px 10px" }}
                        title="Ask vs Requirement classification"
                      >
                        Semantic
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Layout>
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

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
