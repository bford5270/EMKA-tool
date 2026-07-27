import { useState } from "react";

// Severity -> badge color (mirrors labs/engine.py SEVERITY_COLORS).
const SEV_COLOR = {
  Normal: "#16a34a",
  "Mild Low": "#60a5fa",
  "Mild High": "#60a5fa",
  "Moderate Low": "#f59e0b",
  "Moderate High": "#f59e0b",
  "Severe Low": "#ef4444",
  "Severe High": "#ef4444",
  "Critical Low": "#b91c1c",
  "Critical High": "#b91c1c",
  Unknown: "#94a3b8",
};

function SeverityBadge({ severity }) {
  const color = SEV_COLOR[severity] || "#94a3b8";
  return (
    <span
      className="inline-block rounded px-2 py-0.5 text-xs font-bold text-white"
      style={{ backgroundColor: color }}
    >
      {severity}
    </span>
  );
}

function Finding({ f }) {
  if (f.error) {
    return (
      <div className="rounded-lg border border-slate-300 bg-white px-4 py-3 text-slate-500">
        {f.lab_id}: {f.error}
      </div>
    );
  }
  const fu = f.follow_up;
  return (
    <div className="rounded-lg border border-slate-300 bg-white px-4 py-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="font-semibold">
          {f.display_name}{" "}
          <span className="text-slate-500 font-normal">
            {f.value} {f.unit}
          </span>
        </div>
        <SeverityBadge severity={f.severity} />
      </div>
      {fu && (
        <div className="text-sm space-y-2">
          {fu.category && <div className="text-slate-700">{fu.category}</div>}
          {fu.next_tests?.length > 0 && (
            <div>
              <div className="text-xs uppercase tracking-wide text-slate-400">
                Recommended workup
              </div>
              <ul className="list-disc list-inside text-slate-700">
                {fu.next_tests.map((t, i) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            </div>
          )}
          {fu.ehr_plan && (
            <div>
              <div className="text-xs uppercase tracking-wide text-slate-400">
                EHR plan (paste-ready)
              </div>
              <pre className="whitespace-pre-wrap rounded bg-slate-50 border border-slate-200 p-2 text-slate-800">
                {fu.ehr_plan}
              </pre>
            </div>
          )}
          {fu.patient_communication && (
            <div>
              <div className="text-xs uppercase tracking-wide text-slate-400">
                Patient communication
              </div>
              <pre className="whitespace-pre-wrap rounded bg-slate-50 border border-slate-200 p-2 text-slate-800">
                {fu.patient_communication}
              </pre>
            </div>
          )}
        </div>
      )}
      {f.sources?.length > 0 && (
        <div className="text-xs text-slate-400">
          Thresholds: {f.sources.join("; ")}
        </div>
      )}
    </div>
  );
}

function Derived({ d }) {
  const rows = [
    d.egfr != null && [`eGFR (${d.egfr_formula})`, `${d.egfr} mL/min/1.73m²`],
    d.ckd_ga_stage && ["KDIGO CKD stage", d.ckd_ga_stage],
    d.kdigo_aki_stage && ["KDIGO AKI stage", d.kdigo_aki_stage],
    d.anion_gap != null && ["Anion gap", d.anion_gap],
    d.bun_cr_ratio != null && ["BUN/Cr ratio", d.bun_cr_ratio],
  ].filter(Boolean);
  const prevent = d.prevent;
  if (rows.length === 0 && !prevent?.available) return null;
  return (
    <div className="rounded-lg border border-slate-300 bg-slate-50 px-4 py-3 space-y-1">
      <div className="text-xs uppercase tracking-wide text-slate-400">
        Derived values
      </div>
      {rows.map(([k, v], i) => (
        <div key={i} className="text-sm flex justify-between">
          <span className="text-slate-600">{k}</span>
          <span className="font-medium">{v}</span>
        </div>
      ))}
      {prevent?.available && (
        <div className="mt-2 border-t border-slate-200 pt-2 text-sm">
          <div className="font-semibold">
            AHA PREVENT (10-yr): ASCVD {prevent.ascvd_10y}% · CVD{" "}
            {prevent.cvd_10y}% · HF {prevent.hf_10y}% —{" "}
            <span className="uppercase">{prevent.risk_tier}</span>
          </div>
          {prevent.statin_recommendation && (
            <div className="text-slate-700">{prevent.statin_recommendation}</div>
          )}
        </div>
      )}
    </div>
  );
}

function Management({ m }) {
  if (!m) return null;
  if (m.unavailable) {
    return (
      <div className="rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm text-slate-500">
        Cited management guidance unavailable ({m.unavailable}). Interpretation
        above is unaffected.
      </div>
    );
  }
  return (
    <div className="rounded-lg border-2 border-slate-800 bg-white px-4 py-3 space-y-2">
      <div className="text-xs uppercase tracking-wide text-slate-500">
        Cited management guidance (triggered by {m.triggered_by}) — from the
        corpus
      </div>
      {m.abstained ? (
        <div className="text-slate-600">
          No adequately-supported guidance in the loaded corpus for this finding.
        </div>
      ) : (
        <>
          {(m.sources || []).slice(0, 3).map((s) => (
            <div key={s.chunk_id} className="text-sm">
              <div className="text-slate-500 text-xs">{s.citation}</div>
              <div className="text-slate-800">{s.text}</div>
            </div>
          ))}
          {m.synthesis && (
            <div className="mt-1 border-t border-slate-200 pt-2 text-sm text-slate-700">
              {m.synthesis}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function LabsPanel() {
  // In-memory only. Lab values are never written to storage, browser or server.
  const [text, setText] = useState("");
  const [sex, setSex] = useState("");
  const [age, setAge] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function interpret(e) {
    e.preventDefault();
    if (!text.trim() || busy) return;
    setBusy(true);
    setError("");
    const context = {};
    if (sex) context.sex = sex;
    if (age) context.age = Number(age);
    try {
      const r = await fetch("/labs/interpret", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          context: Object.keys(context).length ? context : null,
          include_management: true,
        }),
      });
      if (!r.ok) throw new Error(`interpret failed: HTTP ${r.status}`);
      setResult(await r.json());
    } catch (err) {
      setError(String(err.message || err));
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  const findings = result?.findings?.results ?? [];

  return (
    <div className="space-y-4">
      <form onSubmit={interpret} className="space-y-3">
        <textarea
          className="w-full h-28 rounded-lg border border-slate-300 bg-white px-4 py-3 shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-500"
          placeholder={"Paste de-identified labs, one per line:\nK 6.2\nGlucose 320\nCr 2.1"}
          value={text}
          onChange={(e) => setText(e.target.value)}
          aria-label="Lab values"
        />
        <div className="flex gap-2 items-center">
          <select
            className="rounded-lg border border-slate-300 bg-white px-2 py-2 shadow-sm"
            value={sex}
            onChange={(e) => setSex(e.target.value)}
            aria-label="Sex"
          >
            <option value="">sex (optional)</option>
            <option value="male">male</option>
            <option value="female">female</option>
          </select>
          <input
            type="number"
            className="w-28 rounded-lg border border-slate-300 bg-white px-3 py-2 shadow-sm"
            placeholder="age"
            value={age}
            onChange={(e) => setAge(e.target.value)}
            aria-label="Age"
          />
          <button
            type="submit"
            disabled={busy}
            className="ml-auto rounded-lg bg-slate-900 text-white px-6 py-2 font-semibold disabled:opacity-50"
          >
            {busy ? "Interpreting…" : "Interpret"}
          </button>
        </div>
      </form>

      {error && (
        <div className="rounded-lg bg-red-100 border border-red-300 text-red-900 px-4 py-3">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-3">
          {findings.map((f, i) => (
            <Finding key={i} f={f} />
          ))}
          <Derived d={result.findings?.derived ?? {}} />
          <Management m={result.management} />
        </div>
      )}
    </div>
  );
}
