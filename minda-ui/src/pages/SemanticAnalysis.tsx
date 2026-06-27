import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Brain,
  CheckCircle2,
  ClipboardList,
  Info,
  Lightbulb,
  Loader2,
} from "lucide-react";
import Layout from "../components/Layout";
import { getResults, getSectionSemantic } from "../api";
import type {
  AnalysisResult,
  AnalyzedStatement,
  Classification,
  SectionSemanticResponse,
} from "../types";
import { DownloadButtons, SectionRail } from "./SectionAnalysis";

const CONFIG: Record<
  Classification,
  {
    title: string;
    chip: string;
    icon: React.ReactNode;
    accent: string;
  }
> = {
  REQUIREMENT: {
    title: "Requirements",
    chip: "chip-success",
    icon: <CheckCircle2 size={16} className="text-teal-ink" />,
    accent: "border-teal",
  },
  ASK: {
    title: "Asks",
    chip: "chip-violet",
    icon: <ClipboardList size={16} className="text-violet-ink" />,
    accent: "border-violet",
  },
  RECOMMENDATION: {
    title: "Recommendations",
    chip: "chip-warning",
    icon: <Lightbulb size={16} className="text-amber-ink" />,
    accent: "border-amber",
  },
  INFORMATIONAL: {
    title: "Informational",
    chip: "chip-muted",
    icon: <Info size={16} className="text-muted" />,
    accent: "border-border",
  },
};

const ORDER: Classification[] = [
  "REQUIREMENT",
  "ASK",
  "RECOMMENDATION",
  "INFORMATIONAL",
];

export default function SemanticAnalysis() {
  const { jobId, sectionName } = useParams();
  const navigate = useNavigate();

  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [data, setData] = useState<SectionSemanticResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) {
      setResult(null);
      return;
    }
    setError(null);
    getResults(jobId).then(setResult).catch((e) => setError(e.message));
  }, [jobId]);

  useEffect(() => {
    if (!jobId || !sectionName) {
      setData(null);
      return;
    }
    getSectionSemantic(jobId, decodeURIComponent(sectionName))
      .then(setData)
      .catch((e) => setError(e.message));
  }, [jobId, sectionName]);

  useEffect(() => {
    if (jobId && result && !sectionName && result.sections[0]) {
      navigate(
        `/semantic-analysis/${jobId}/${encodeURIComponent(result.sections[0].section_name)}`,
        { replace: true },
      );
    }
  }, [result, sectionName, jobId, navigate]);

  if (!jobId) {
    return (
      <Layout title="Semantic Analysis" subtitle="Pick a job from history">
        <div className="panel">
          <div className="panel-body text-center py-12">
            <div className="text-muted mb-4">
              Pick an analysis from your history, or upload a new SOR.
            </div>
            <div className="flex items-center justify-center gap-2">
              <Link to="/jobs" className="btn-cta inline-flex">
                Open history
              </Link>
              <Link to="/upload" className="btn-ghost inline-flex">
                Upload new SOR
              </Link>
            </div>
          </div>
        </div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout title="Semantic Analysis">
        <div className="panel">
          <div className="panel-body text-danger-ink">Error: {error}</div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout
      title="Semantic Analysis"
      subtitle={
        result
          ? `${result.filename} · Ask vs Requirement classification per section`
          : "Loading…"
      }
      right={<DownloadButtons jobId={jobId} />}
    >
      <div className="grid grid-cols-12 gap-4">
        <SectionRail
          jobId={jobId}
          result={result}
          activeName={sectionName ? decodeURIComponent(sectionName) : ""}
          baseRoute="semantic-analysis"
        />
        <div className="col-span-12 lg:col-span-8 xl:col-span-9">
          {sectionName ? (
            <SemanticView
              data={data}
              decodedName={decodeURIComponent(sectionName)}
            />
          ) : (
            <div className="panel">
              <div className="panel-body text-center py-12 text-muted">
                Select a section from the left to view its semantic breakdown.
              </div>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}

function SemanticView({
  data,
  decodedName,
}: {
  data: SectionSemanticResponse | null;
  decodedName: string;
}) {
  if (!data) {
    return (
      <div className="panel">
        <div className="panel-body flex items-center justify-center gap-2 py-12 text-muted">
          <Loader2 size={16} className="animate-spin" />
          Loading section…
        </div>
      </div>
    );
  }

  const hasAny =
    data.totals.REQUIREMENT +
      data.totals.ASK +
      data.totals.RECOMMENDATION +
      data.totals.INFORMATIONAL >
    0;

  return (
    <div className="space-y-4">
      <div className="panel">
        <div className="panel-head">
          <div className="min-w-0">
            <h2 className="panel-title break-words flex items-center gap-2">
              <Brain size={16} className="text-primary-ink" />
              {data.section_name}
            </h2>
            <p className="panel-sub">Classified per INCOSE / ISO 29148</p>
          </div>
          <div className="flex items-center gap-1.5 flex-wrap justify-end">
            <span className="chip chip-success">
              {data.totals.REQUIREMENT} Req
            </span>
            <span className="chip chip-violet">{data.totals.ASK} Ask</span>
            <span className="chip chip-warning">
              {data.totals.RECOMMENDATION} Rec
            </span>
            <span className="chip chip-muted">
              {data.totals.INFORMATIONAL} Info
            </span>
          </div>
        </div>
      </div>

      {!hasAny ? (
        <div className="panel">
          <div className="panel-body text-center py-10 text-muted text-sm">
            This section has no body content to classify (heading only).
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {ORDER.map((cls) => (
            <ClassPanel
              key={cls}
              cls={cls}
              statements={data.groups[cls] ?? []}
              decodedName={decodedName}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ClassPanel({
  cls,
  statements,
  decodedName,
}: {
  cls: Classification;
  statements: AnalyzedStatement[];
  decodedName: string;
}) {
  const cfg = CONFIG[cls];
  return (
    <div className={`panel border-l-4 ${cfg.accent}`}>
      <div className="panel-head">
        <div className="flex items-center gap-2">
          {cfg.icon}
          <h3 className="panel-title">{cfg.title}</h3>
        </div>
        <span className={`chip ${cfg.chip}`}>{statements.length}</span>
      </div>
      <div className="panel-body p-0 max-h-[60vh] overflow-y-auto">
        {statements.length === 0 ? (
          <div className="px-5 py-8 text-sm text-muted text-center">
            None in "{decodedName}".
          </div>
        ) : (
          <ul className="divide-y divide-border-2">
            {statements.map((s) => (
              <li key={s.id} className="px-5 py-3.5">
                <div className="flex items-center justify-between mb-1.5 gap-2">
                  <span className="font-mono text-[11px] text-muted">
                    {s.id}
                  </span>
                  <div className="flex items-center gap-1.5">
                    {s.source_type && (
                      <span className="chip chip-muted text-[10px]">
                        {s.source_type.replace("_", " ")}
                      </span>
                    )}
                    {s.obligation_keyword &&
                      s.obligation_keyword !== "none" && (
                        <span className="chip chip-primary text-[10px]">
                          {s.obligation_keyword}
                        </span>
                      )}
                  </div>
                </div>
                <div className="text-[13.5px] text-text leading-relaxed">
                  {s.text}
                </div>
                {s.classification_reason && (
                  <div className="mt-1.5 text-[11.5px] text-muted italic">
                    Why: {s.classification_reason}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
