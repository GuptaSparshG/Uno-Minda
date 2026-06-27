import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  AlignLeft,
  Circle,
  Download,
  FileSpreadsheet,
  FileText,
  Hash,
  Heading2,
  Image as ImageIcon,
  ListChecks,
  ListTree,
  Loader2,
  Table2,
} from "lucide-react";
import Layout from "../components/Layout";
import { exportUrl, getResults, getSectionRaw } from "../api";
import type { AnalysisResult, RawBlock, SectionRawResponse } from "../types";

export default function SectionAnalysis() {
  const { jobId, sectionName } = useParams();
  const navigate = useNavigate();

  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [raw, setRaw] = useState<SectionRawResponse | null>(null);
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
      setRaw(null);
      return;
    }
    getSectionRaw(jobId, decodeURIComponent(sectionName))
      .then(setRaw)
      .catch((e) => setError(e.message));
  }, [jobId, sectionName]);

  // Auto-select first section if a job is loaded but no section chosen
  useEffect(() => {
    if (jobId && result && !sectionName && result.sections[0]) {
      navigate(
        `/section-analysis/${jobId}/${encodeURIComponent(result.sections[0].section_name)}`,
        { replace: true },
      );
    }
  }, [result, sectionName, jobId, navigate]);

  if (!jobId) {
    return (
      <Layout title="Section Analysis" subtitle="Pick a job from history">
        <NoJob />
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout title="Section Analysis">
        <div className="panel">
          <div className="panel-body text-danger-ink">Error: {error}</div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout
      title="Section Analysis"
      subtitle={result ? `${result.filename} · ${result.total_sections} sections (raw content, untouched)` : "Loading…"}
      right={<DownloadButtons jobId={jobId} />}
    >
      <div className="grid grid-cols-12 gap-4">
        <SectionRail
          jobId={jobId}
          result={result}
          activeName={sectionName ? decodeURIComponent(sectionName) : ""}
          baseRoute="section-analysis"
        />
        <div className="col-span-12 lg:col-span-8 xl:col-span-9">
          {sectionName ? (
            <SectionRawView
              raw={raw}
              decodedName={decodeURIComponent(sectionName)}
            />
          ) : (
            <div className="panel">
              <div className="panel-body text-center py-12 text-muted">
                Select a section from the left to view its raw content.
              </div>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}

function SectionRawView({
  raw,
  decodedName,
}: {
  raw: SectionRawResponse | null;
  decodedName: string;
}) {
  if (!raw) {
    return (
      <div className="panel">
        <div className="panel-body flex items-center justify-center gap-2 py-12 text-muted">
          <Loader2 size={16} className="animate-spin" />
          Loading section…
        </div>
      </div>
    );
  }

  const isHeadingOnly =
    raw.heading_only || (raw.blocks.length === 0);

  return (
    <div className="panel">
      <div className="panel-head">
        <div className="min-w-0">
          <h2 className="panel-title break-words">{raw.section_name}</h2>
          <p className="panel-sub">
            {isHeadingOnly
              ? "This is a heading — no body content follows it in the document."
              : `${raw.blocks.length} content block${raw.blocks.length === 1 ? "" : "s"} (untouched)`}
          </p>
        </div>
        {isHeadingOnly && (
          <span className="chip chip-muted">Heading only</span>
        )}
      </div>
      <div className="panel-body p-0">
        {isHeadingOnly ? (
          <div className="px-5 py-12 text-center">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-primary-soft text-primary-ink mb-3">
              <ListChecks size={22} />
            </div>
            <div className="text-text font-semibold mb-1">
              "{decodedName}" is a section heading
            </div>
            <div className="text-sm text-muted max-w-md mx-auto">
              The PDF places this label without any text underneath. It exists
              as a navigation marker rather than carrying its own content.
            </div>
          </div>
        ) : (
          <div className="divide-y divide-border-2">
            {raw.blocks.map((b, i) => (
              <BlockView key={i} block={b} index={i + 1} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function BlockView({ block, index }: { block: RawBlock; index: number }) {
  if (block.type === "heading") {
    return (
      <div className="px-5 py-4 bg-primary-soft/40">
        <BlockHeader
          icon={<Heading2 size={14} />}
          label="Heading"
          index={index}
        />
        <h3 className="text-[15px] font-bold text-primary-ink leading-snug">
          {block.text}
        </h3>
      </div>
    );
  }
  if (block.type === "paragraph") {
    return (
      <div className="px-5 py-4">
        <BlockHeader icon={<AlignLeft size={14} />} label="Paragraph" index={index} />
        <p className="text-[14px] text-text leading-relaxed whitespace-pre-wrap">
          {block.text}
        </p>
      </div>
    );
  }
  if (block.type === "bullet_list") {
    return (
      <div className="px-5 py-4">
        <BlockHeader
          icon={<Circle size={8} className="fill-current" />}
          label={`Bullet list (${block.items.length})`}
          index={index}
        />
        {/* Items are rendered verbatim — they already include the PDF's
            original bullet marker (➢, ·, • etc.) at the start. */}
        <ul className="space-y-1 list-none">
          {block.items.map((it, i) => (
            <li
              key={i}
              className="text-[14px] text-text leading-relaxed whitespace-pre-wrap"
            >
              {it}
            </li>
          ))}
        </ul>
      </div>
    );
  }
  if (block.type === "numbered_list") {
    return (
      <div className="px-5 py-4">
        <BlockHeader
          icon={<Hash size={14} />}
          label={`Numbered list (${block.items.length})`}
          index={index}
        />
        {/* Items are rendered verbatim — they already include their original
            number/letter prefix from the PDF (e.g. "1." or "f."). */}
        <ol className="space-y-1 list-none">
          {block.items.map((it, i) => (
            <li
              key={i}
              className="text-[14px] text-text leading-relaxed whitespace-pre-wrap"
            >
              {it}
            </li>
          ))}
        </ol>
      </div>
    );
  }
  if (block.type === "table") {
    return (
      <div className="px-5 py-4">
        <BlockHeader
          icon={<Table2 size={14} />}
          label={`Table (${block.rows.length} rows × ${block.headers.length} cols)`}
          index={index}
        />
        <div className="overflow-x-auto border border-border rounded-sm">
          <table className="w-full text-[13px]">
            <thead className="bg-tint">
              <tr>
                {block.headers.map((h, i) => (
                  <th
                    key={i}
                    className="text-left px-3 py-2 font-semibold text-text-2 border-b border-border"
                  >
                    {h || `Col ${i + 1}`}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, ri) => (
                <tr key={ri} className="border-t border-border-2">
                  {row.map((cell, ci) => (
                    <td key={ci} className="px-3 py-2 align-top text-text">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }
  if (block.type === "picture") {
    return (
      <div className="px-5 py-4">
        <BlockHeader
          icon={<ImageIcon size={14} />}
          label={block.page ? `Diagram · page ${block.page}` : "Diagram"}
          index={index}
        />
        <figure className="bg-tint border border-border rounded-sm p-3 inline-block max-w-full">
          {block.image_base64 ? (
            <img
              src={block.image_base64}
              alt={block.caption ?? "Diagram"}
              className="max-w-full h-auto rounded-xs"
            />
          ) : (
            <div className="text-sm text-muted italic">
              [diagram present, image data not available]
            </div>
          )}
          {block.caption && (
            <figcaption className="mt-2 text-[12px] text-muted italic">
              {block.caption}
            </figcaption>
          )}
        </figure>
      </div>
    );
  }
  return null;
}

function BlockHeader({
  icon,
  label,
  index,
}: {
  icon: React.ReactNode;
  label: string;
  index: number;
}) {
  return (
    <div className="flex items-center gap-2 mb-2 text-muted-2 text-[11px] uppercase tracking-[0.06em] font-bold">
      <span>{icon}</span>
      <span>{label}</span>
      <span className="ml-auto">#{index}</span>
    </div>
  );
}

function NoJob() {
  return (
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
  );
}

export function DownloadButtons({ jobId }: { jobId: string }) {
  if (!jobId) return null;
  return (
    <div className="flex items-center gap-2">
      <a
        href={exportUrl.excel(jobId)}
        className="btn-ghost"
        title="Multi-sheet Excel workbook"
      >
        <FileSpreadsheet size={14} /> Excel
      </a>
      <a
        href={exportUrl.csv(jobId)}
        className="btn-ghost"
        title="Flat CSV — one row per statement"
      >
        <FileText size={14} /> CSV
      </a>
      <a
        href={exportUrl.json(jobId)}
        className="btn-ghost"
        title="Full AnalysisResult JSON"
      >
        <Download size={14} /> JSON
      </a>
      <a
        href={exportUrl.pdf(jobId)}
        className="btn-ghost"
        title="PDF report (may 404 if weasyprint deps missing)"
      >
        <FileText size={14} /> PDF
      </a>
    </div>
  );
}

export function SectionRail({
  jobId,
  result,
  activeName,
  baseRoute,
}: {
  jobId: string;
  result: AnalysisResult | null;
  activeName: string;
  baseRoute: "section-analysis" | "semantic-analysis";
}) {
  const items = useMemo(
    () =>
      (result?.sections ?? []).map((s) => ({
        name: s.section_name,
        total: s.total,
        heading_only: s.heading_only,
        req: s.requirements,
        ask: s.asks,
      })),
    [result],
  );

  return (
    <aside className="col-span-12 lg:col-span-4 xl:col-span-3">
      <div className="panel sticky top-4">
        <div className="panel-head">
          <h2 className="panel-title flex items-center gap-2">
            <ListTree size={16} className="text-primary-ink" />
            Sections
          </h2>
          <span className="chip chip-muted">{items.length}</span>
        </div>
        <div className="panel-body p-0 max-h-[75vh] overflow-y-auto">
          {!result ? (
            <div className="flex items-center justify-center gap-2 py-10 text-muted text-sm">
              <Loader2 size={14} className="animate-spin" />
              Loading…
            </div>
          ) : (
            <ul className="divide-y divide-border-2">
              {items.map((it) => (
                <li key={it.name}>
                  <Link
                    to={`/${baseRoute}/${jobId}/${encodeURIComponent(it.name)}`}
                    className={`block px-4 py-3 transition ${
                      activeName === it.name
                        ? "bg-primary-soft border-l-4 border-primary-ink"
                        : "hover:bg-tint border-l-4 border-transparent"
                    }`}
                  >
                    <div className="text-[13px] font-medium text-text break-words leading-snug">
                      {it.name}
                    </div>
                    <div className="mt-1 flex items-center gap-1.5 flex-wrap">
                      {it.heading_only ? (
                        <span className="chip chip-muted text-[10px]">heading only</span>
                      ) : (
                        <>
                          <span className="text-[11px] text-muted">{it.total} items</span>
                          {baseRoute === "semantic-analysis" && (
                            <>
                              <span className="chip chip-success text-[10px]">
                                {it.req}
                              </span>
                              <span className="chip chip-violet text-[10px]">
                                {it.ask}
                              </span>
                            </>
                          )}
                        </>
                      )}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </aside>
  );
}
