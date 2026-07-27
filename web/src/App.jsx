import { useState } from "react";
import SourceCard from "./components/SourceCard.jsx";
import ConflictGroup from "./components/ConflictGroup.jsx";
import AnswerPanel from "./components/AnswerPanel.jsx";
import CapabilityNotes from "./components/CapabilityNotes.jsx";
import FlagControl from "./components/FlagControl.jsx";
import LabsPanel from "./components/LabsPanel.jsx";

const ROLES = [
  { value: "role1", label: "Role 1 / BAS" },
  { value: "role2", label: "Role 2" },
  { value: "role3", label: "Role 3" },
];

export default function App() {
  // All state is in memory only — nothing is written to browser storage.
  const [tab, setTab] = useState("reference");
  const [question, setQuestion] = useState("");
  const [role, setRole] = useState("role2");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    if (question.trim().length < 3 || busy) return;
    setBusy(true);
    setError("");
    try {
      const r = await fetch("/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, context: { role } }),
      });
      if (!r.ok) throw new Error(`query failed: HTTP ${r.status}`);
      setResult(await r.json());
    } catch (err) {
      setError(String(err.message || err));
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  const conflictIds = new Set(
    (result?.conflicts ?? []).flatMap((c) => c.chunk_ids)
  );
  const plainSources = (result?.sources ?? []).filter(
    (s) => !conflictIds.has(s.chunk_id)
  );

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      {/* Persistent no-PHI banner — always visible, never dismissible */}
      <div className="sticky top-0 z-50 bg-amber-400 text-amber-950 text-center text-sm font-semibold px-4 py-2 shadow">
        NO PHI — reference system only. Do not enter patient-identifying
        information. Nothing you type is a medical record.
      </div>

      <header className="bg-slate-900 text-slate-100 px-6 py-4">
        <h1 className="text-xl font-bold tracking-wide">EMKA</h1>
        <p className="text-slate-400 text-sm">
          Expeditionary Medical Knowledge Assistant — offline, cited, verified
        </p>
        <nav className="mt-3 flex gap-1">
          {[
            ["reference", "Reference"],
            ["labs", "Labs"],
          ].map(([id, label]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`rounded-t-md px-4 py-1.5 text-sm font-semibold ${
                tab === id
                  ? "bg-slate-100 text-slate-900"
                  : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              {label}
            </button>
          ))}
        </nav>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        {tab === "labs" && <LabsPanel />}
        {tab === "reference" && (
        <>
        <form onSubmit={submit} className="flex gap-2">
          <input
            className="flex-1 rounded-lg border border-slate-300 bg-white px-4 py-3 shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-500"
            placeholder="Ask a doctrine or clinical reference question…"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            aria-label="Question"
          />
          <select
            className="rounded-lg border border-slate-300 bg-white px-2 shadow-sm"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            aria-label="Echelon"
          >
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-slate-900 text-white px-6 py-3 font-semibold disabled:opacity-50"
          >
            {busy ? "Searching…" : "Ask"}
          </button>
        </form>

        {error && (
          <div className="rounded-lg bg-red-100 border border-red-300 text-red-900 px-4 py-3">
            {error}
          </div>
        )}

        {result && (
          <>
            {result.abstained && (
              <div className="rounded-lg bg-slate-200 border border-slate-400 px-4 py-3 font-medium">
                Insufficient corpus support — {result.abstain_reason || "the"}
                {" "}loaded corpus does not adequately answer this question. No
                answer was improvised.
              </div>
            )}

            {result.mode === "raw_passages" && (
              <div className="rounded-lg bg-red-100 border-2 border-red-400 px-4 py-3 font-semibold text-red-900">
                Verification failed — the synthesized answer could not be
                verified against its sources and was withheld. The raw
                retrieved passages are shown below instead.
              </div>
            )}

            {/* SOURCES FIRST — verbatim passages are the primary content */}
            {result.conflicts?.length > 0 && (
              <ConflictGroup
                conflicts={result.conflicts}
                sources={result.sources}
              />
            )}

            {plainSources.length > 0 && (
              <section aria-label="Sources">
                <h2 className="text-lg font-bold mb-2">
                  Sources{" "}
                  <span className="text-sm font-normal text-slate-500">
                    (verbatim, ordered by authority tier)
                  </span>
                </h2>
                <div className="space-y-3">
                  {plainSources.map((s) => (
                    <SourceCard key={s.chunk_id} source={s} />
                  ))}
                </div>
              </section>
            )}

            <CapabilityNotes notes={result.capability_notes ?? []} />

            {/* Synthesized answer SECOND and visibly subordinate */}
            {result.mode === "synthesized" && (
              <AnswerPanel result={result} />
            )}

            <FlagControl result={result} />
          </>
        )}
        </>
        )}
      </main>
    </div>
  );
}
