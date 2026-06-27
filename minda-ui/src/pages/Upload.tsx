import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  FileText,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Cloud,
} from "lucide-react";
import Layout from "../components/Layout";
import { uploadPdf } from "../api";

export default function UploadPage() {
  const nav = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const handleFiles = (files: FileList | null) => {
    if (!files?.length) return;
    const f = files[0];
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      setError("Only PDF files are accepted.");
      return;
    }
    if (f.size > 50 * 1024 * 1024) {
      setError("File exceeds 50 MB limit.");
      return;
    }
    setError(null);
    setFile(f);
  };

  const submit = async () => {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await uploadPdf(file);
      nav(`/semantic-analysis/${res.job_id}`);
    } catch (e: any) {
      setError(e.message || "Upload failed");
      setBusy(false);
    }
  };

  return (
    <Layout
      title="Upload SOR"
      subtitle="Drop a Statement of Requirement PDF — we extract sections, classify against INCOSE / ISO 29148, and produce reports."
    >
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-8">
          <div className="panel">
            <div className="panel-head">
              <div>
                <h2 className="panel-title">Document upload</h2>
                <p className="panel-sub">PDF only · max 50 MB</p>
              </div>
              <span className="chip chip-muted">
                <Cloud size={12} /> Local storage
              </span>
            </div>
            <div className="panel-body">
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragging(false);
                  handleFiles(e.dataTransfer.files);
                }}
                onClick={() => inputRef.current?.click()}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    inputRef.current?.click();
                  }
                }}
                className={[
                  "cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition duration-150",
                  dragging
                    ? "border-primary bg-primary-soft"
                    : file
                    ? "border-teal bg-teal-soft"
                    : "border-border bg-tint hover:bg-surface hover:border-primary",
                ].join(" ")}
              >
                <input
                  ref={inputRef}
                  type="file"
                  accept="application/pdf,.pdf"
                  className="hidden"
                  onChange={(e) => {
                    handleFiles(e.target.files);
                    e.target.value = "";
                  }}
                />
                <div
                  className={[
                    "w-14 h-14 mx-auto mb-3 rounded-xl grid place-items-center",
                    file ? "bg-white text-teal-ink" : "bg-white text-primary-ink",
                  ].join(" ")}
                  style={{
                    boxShadow:
                      "0 1px 3px rgba(15,23,42,0.04), 0 4px 12px rgba(15,23,42,0.04)",
                  }}
                >
                  {file ? <CheckCircle2 size={26} /> : <FileText size={26} />}
                </div>
                <div className="font-semibold text-text">
                  {file ? file.name : "Drop your PDF here, or click to browse"}
                </div>
                <div className="text-sm text-muted mt-1">
                  {file
                    ? `${(file.size / 1024 / 1024).toFixed(2)} MB · ready to analyze`
                    : "Bullets, numbered lists and table rows are all picked up."}
                </div>
              </div>

              {error && (
                <div className="mt-4 flex items-start gap-2 text-sm text-danger-ink bg-danger-soft border border-danger/20 rounded-sm px-3 py-2.5">
                  <AlertCircle size={16} className="mt-0.5 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <div className="mt-5 flex items-center gap-3">
                <button
                  disabled={!file || busy}
                  onClick={submit}
                  className="btn-cta"
                >
                  {busy ? (
                    <>
                      <Loader2 size={15} className="animate-spin" />
                      Analyzing… this can take 30s–5m
                    </>
                  ) : (
                    "Start analysis"
                  )}
                </button>
                {file && !busy && (
                  <button
                    onClick={() => setFile(null)}
                    className="btn-ghost"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-4">
          <div className="panel">
            <div className="panel-head">
              <h2 className="panel-title">What you get</h2>
            </div>
            <div className="panel-body space-y-3 text-sm text-text-2">
              <Step n={1} label="Section + statement extraction" />
              <Step n={2} label="Ask vs Requirement classification (LLM + RAG)" />
              <Step n={3} label="INCOSE quality score per statement (R2–R14)" />
              <Step n={4} label="Excel + PDF + JSON downloadable reports" />
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}

function Step({ n, label }: { n: number; label: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-6 h-6 rounded-full bg-primary-soft text-primary-ink text-[11px] font-bold grid place-items-center shrink-0">
        {n}
      </span>
      <span>{label}</span>
    </div>
  );
}
